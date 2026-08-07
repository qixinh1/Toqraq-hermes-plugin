"""Failure ownership tests for bounded Windows process output."""

from __future__ import annotations

import threading

import pytest
from toqraq.core.process_tree import ProcessOutputStream
from toqraq.platforms.windows.process_output import WindowsProcessOutput
from toqraq.platforms.windows.process_ownership import OwnedHandle


class _PipeHarness:
    """Fail stderr reads and observe that both exact handles close."""

    def __init__(self) -> None:
        self.open_handles = {101, 102}
        self.stderr = 102
        self.read_attempted = threading.Event()

    def read_pipe(self, handle: int, maximum_bytes: int) -> bytes | None:
        del maximum_bytes
        self.read_attempted.set()
        if handle == self.stderr:
            raise OSError("reader failed")
        return None

    def close_handle(self, handle: int) -> None:
        if handle not in self.open_handles:
            raise OSError("double close")
        self.open_handles.remove(handle)


class _TailHarness:
    """Expose one tail only after the test declares both writers ended."""

    def __init__(self) -> None:
        self.open_handles = {201, 202}
        self.stdout = 201
        self.read_attempted = threading.Event()
        self.writers_ended = threading.Event()
        self.stdout_delivered = False

    def read_pipe(self, handle: int, maximum_bytes: int) -> bytes | None:
        del maximum_bytes
        self.read_attempted.set()
        if not self.writers_ended.is_set():
            return b""
        if handle == self.stdout and not self.stdout_delivered:
            self.stdout_delivered = True
            return b"tail-evidence"
        return None

    def close_handle(self, handle: int) -> None:
        if handle not in self.open_handles:
            raise OSError("double close")
        self.open_handles.remove(handle)


def _tail_output(harness: _TailHarness) -> WindowsProcessOutput:
    return WindowsProcessOutput(
        harness,
        stdout_read=OwnedHandle(harness, 201),
        stderr_read=OwnedHandle(harness, 202),
        character_limit=128,
        read_size=16,
        idle_interval=0.001,
    )


def test_output_reader_failure_closes_unread_pipe() -> None:
    harness = _PipeHarness()
    stdout = OwnedHandle(harness, 101)
    stderr = OwnedHandle(harness, 102)
    output = WindowsProcessOutput(
        harness,
        stdout_read=stdout,
        stderr_read=stderr,
        character_limit=128,
        read_size=16,
        idle_interval=0.001,
    )

    output.start()
    assert harness.read_attempted.wait(1)
    output.close(1, drain=True)

    assert stderr.closed
    assert ProcessOutputStream.STDERR in output.snapshot().failed_streams
    assert harness.open_handles == set()


def test_drain_close_preserves_tail_published_after_an_idle_read() -> None:
    harness = _TailHarness()
    output = _tail_output(harness)
    output.start()
    assert harness.read_attempted.wait(1)

    harness.writers_ended.set()
    output.close(1, drain=True)

    snapshot = output.snapshot()
    assert tuple(chunk.text for chunk in snapshot.chunks) == ("tail-evidence",)
    assert snapshot.failed_streams == frozenset()
    assert harness.open_handles == set()


def test_drain_timeout_retains_collector_and_pipes_for_retry() -> None:
    harness = _TailHarness()
    output = _tail_output(harness)
    output.start()
    assert harness.read_attempted.wait(1)

    with pytest.raises(TimeoutError):
        output.close(0, drain=True)

    assert harness.open_handles == {201, 202}
    harness.writers_ended.set()
    output.close(1, drain=True)
    assert harness.open_handles == set()


def test_abort_close_stops_an_idle_collector_and_closes_pipes() -> None:
    harness = _TailHarness()
    output = _tail_output(harness)
    output.start()
    assert harness.read_attempted.wait(1)

    output.close(1, drain=False)

    assert output.snapshot().chunks == ()
    assert harness.open_handles == set()
