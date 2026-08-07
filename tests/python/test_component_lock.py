from __future__ import annotations

import multiprocessing
import os
import queue
import stat
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from toqraq.components import lock as component_lock
from toqraq.components.lock import (
    ComponentFileLock,
    ComponentLockCancelledError,
    ComponentLockFileError,
    ComponentLockFileMode,
    ComponentLockPolicy,
    ComponentLockTimeoutError,
)

_POLICY = ComponentLockPolicy(timeout_seconds=1.0, poll_seconds=0.01)
_SHORT_POLICY = ComponentLockPolicy(timeout_seconds=0.1, poll_seconds=0.01)


def _process_lock(path: str, timeout: float, result: Any) -> None:
    policy = ComponentLockPolicy(timeout_seconds=timeout, poll_seconds=0.01)
    try:
        with ComponentFileLock(Path(path), policy):
            result.put("acquired")
    except ComponentLockTimeoutError:
        result.put("timeout")
    except BaseException as exc:
        result.put(f"error:{type(exc).__name__}")


def test_lock_file_is_private_reusable_and_release_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "component.lock"
    lock = ComponentFileLock(path, _POLICY)

    with lock:
        pass

    lock.release()
    assert path.read_bytes() == b"\0"
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with ComponentFileLock(path, _POLICY):
        pass


def test_lock_rejects_double_acquire_by_the_same_owner(tmp_path: Path) -> None:
    lock = ComponentFileLock(tmp_path / "component.lock", _POLICY).acquire()
    try:
        with pytest.raises(RuntimeError, match="already acquired"):
            lock.acquire()
    finally:
        lock.release()


def test_failed_native_unlock_retains_lock_for_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "component.lock"
    lock = ComponentFileLock(path, _POLICY).acquire()
    original_unlock = component_lock._unlock
    calls = 0

    def fail_once(descriptor: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("native unlock failed")
        original_unlock(descriptor)

    monkeypatch.setattr(component_lock, "_unlock", fail_once)

    with pytest.raises(OSError):
        lock.release()
    with pytest.raises(ComponentLockTimeoutError):
        ComponentFileLock(path, _SHORT_POLICY).acquire()

    lock.release()
    lock.release()
    assert calls == 2
    with ComponentFileLock(path, _POLICY):
        pass


def test_second_owner_in_same_process_times_out(tmp_path: Path) -> None:
    path = tmp_path / "component.lock"
    with ComponentFileLock(path, _POLICY):
        started = time.monotonic()
        with pytest.raises(ComponentLockTimeoutError):
            ComponentFileLock(path, _SHORT_POLICY).acquire()
        assert time.monotonic() - started >= 0.08


def test_nonblocking_attempt_reports_contention_and_can_be_reused(tmp_path: Path) -> None:
    path = tmp_path / "component.lock"
    contender = ComponentFileLock(path, _POLICY)
    with ComponentFileLock(path, _POLICY):
        assert contender.try_acquire() is False

    assert contender.try_acquire() is True
    contender.release()


def test_existing_only_probe_never_creates_a_missing_receipt(tmp_path: Path) -> None:
    path = tmp_path / "missing.lock"
    probe = ComponentFileLock(
        path,
        _POLICY,
        file_mode=ComponentLockFileMode.EXISTING,
    )

    with pytest.raises(FileNotFoundError):
        probe.try_acquire()

    assert not path.exists()


def test_wait_can_be_cancelled_without_waiting_for_timeout(tmp_path: Path) -> None:
    path = tmp_path / "component.lock"
    cancellation = threading.Event()
    outcome: list[type[BaseException]] = []

    def wait() -> None:
        try:
            ComponentFileLock(path, _POLICY, cancellation=cancellation).acquire()
        except BaseException as exc:
            outcome.append(type(exc))

    with ComponentFileLock(path, _POLICY):
        thread = threading.Thread(target=wait)
        thread.start()
        time.sleep(0.05)
        cancellation.set()
        thread.join(timeout=1)

    assert not thread.is_alive()
    assert outcome == [ComponentLockCancelledError]


def test_cross_process_lock_excludes_then_releases(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    path = tmp_path / "component.lock"

    with ComponentFileLock(path, _POLICY):
        result = context.Queue()
        process = context.Process(target=_process_lock, args=(str(path), 0.2, result))
        process.start()
        assert result.get(timeout=5) == "timeout"
        process.join(timeout=5)
        assert process.exitcode == 0

    result = context.Queue()
    process = context.Process(target=_process_lock, args=(str(path), 1.0, result))
    process.start()
    assert result.get(timeout=5) == "acquired"
    process.join(timeout=5)
    assert process.exitcode == 0


def test_cancellation_before_first_native_attempt(tmp_path: Path) -> None:
    cancellation = threading.Event()
    cancellation.set()

    with pytest.raises(ComponentLockCancelledError):
        ComponentFileLock(
            tmp_path / "component.lock",
            _POLICY,
            cancellation=cancellation,
        ).acquire()


def test_rejects_directory_and_malformed_lock_file(tmp_path: Path) -> None:
    directory = tmp_path / "directory.lock"
    directory.mkdir()
    with pytest.raises((ComponentLockFileError, PermissionError)):
        ComponentFileLock(directory, _POLICY).acquire()

    malformed = tmp_path / "malformed.lock"
    malformed.write_bytes(b"too long")
    with pytest.raises(ComponentLockFileError):
        ComponentFileLock(malformed, _POLICY).acquire()


def test_rejects_hard_linked_lock_file(tmp_path: Path) -> None:
    original = tmp_path / "original"
    original.write_bytes(b"\0")
    link = tmp_path / "component.lock"
    try:
        os.link(original, link)
    except OSError as exc:
        pytest.skip(f"hard links unavailable: {type(exc).__name__}")

    with pytest.raises(ComponentLockFileError):
        ComponentFileLock(link, _POLICY).acquire()


def test_rejects_symbolic_lock_file(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_bytes(b"\0")
    link = tmp_path / "component.lock"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symbolic links unavailable: {type(exc).__name__}")

    with pytest.raises((ComponentLockFileError, OSError)):
        ComponentFileLock(link, _POLICY).acquire()


@pytest.mark.parametrize(
    ("timeout", "poll"),
    [
        (0, 0.1),
        (True, 0.1),
        (float("inf"), 0.1),
        (1, 0),
        (1, 2),
    ],
)
def test_lock_policy_rejects_unbounded_or_invalid_waits(timeout: float, poll: float) -> None:
    with pytest.raises(ValueError):
        ComponentLockPolicy(timeout_seconds=timeout, poll_seconds=poll)


def test_child_result_queue_does_not_hide_worker_failure(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    result = context.Queue()
    process = context.Process(
        target=_process_lock,
        args=(str(tmp_path / "missing-parent" / "lock"), 0.1, result),
    )
    process.start()
    try:
        assert result.get(timeout=5).startswith("error:")
    except queue.Empty:
        pytest.fail("lock worker produced no observed outcome")
    finally:
        process.join(timeout=5)
