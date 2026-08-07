"""Fault-injection tests for atomic Windows process ownership."""

from __future__ import annotations

from pathlib import Path

import pytest
from toqraq.core.errors import LaunchError, ProcessTerminationError
from toqraq.core.process_tree import ProcessTree, ProcessTreeLauncher

from _windows_process_fakes import BOOTSTRAP_BYTES, FakeNative, make_command, make_launcher

pytestmark = pytest.mark.windows


@pytest.mark.parametrize(
    "failure",
    [
        "lifetime_job",
        "configure_lifetime",
        "create_helper",
        "session_job",
        "configure_session",
        "stdout_pipe",
        "stderr_pipe",
        "output_start",
        "bootstrap_pipe",
        "bootstrap_write",
        "duplicate_stdin",
        "duplicate_stdout",
        "duplicate_stderr",
        "parent_attribute",
        "handle_attribute",
        "job_attribute",
        "create_child",
        "session_membership",
        "lifetime_membership",
        "close_remote",
        "close_once",
        "bootstrap_writer_close_once",
        "child_thread_close_once",
        "inheritable_pipe",
    ],
)
def test_every_launch_fault_releases_all_ownership(
    tmp_path: Path,
    failure: str,
) -> None:
    native = FakeNative(failure)
    launcher = make_launcher(native, tmp_path)

    with pytest.raises(LaunchError):
        launcher.launch(make_command(tmp_path))

    native.failure = None
    launcher.close()
    assert native.handles == set()
    assert native.remote_handles == set()


def test_launch_order_has_no_suspended_assignment_or_resume(tmp_path: Path) -> None:
    native = FakeNative()
    launcher = make_launcher(native, tmp_path)
    tree = launcher.launch(make_command(tmp_path))

    assert isinstance(launcher, ProcessTreeLauncher)
    assert isinstance(tree, ProcessTree)
    assert native.payload == BOOTSTRAP_BYTES
    assert native.calls.index("output_start") < native.calls.index("bootstrap_write")
    assert native.calls.index("bootstrap_write") < native.calls.index("create_child_atomic")
    assert not any("assign" in call or "resume" in call for call in native.calls)
    assert native.remote_handles == set()

    tree.close(graceful_timeout=0, forced_timeout=1)
    assert "output_close_drain" in native.calls
    launcher.close()
    assert native.handles == set()


def test_base_exception_remains_in_launcher_ledger_for_cleanup(tmp_path: Path) -> None:
    native = FakeNative("base_create_child")
    launcher = make_launcher(native, tmp_path)

    with pytest.raises(KeyboardInterrupt):
        launcher.launch(make_command(tmp_path))

    assert native.handles
    native.failure = None
    launcher.close()
    assert native.handles == set()
    assert native.remote_handles == set()


def test_failed_launch_aborts_output_until_process_termination_succeeds(
    tmp_path: Path,
) -> None:
    native = FakeNative("lifetime_membership")
    native.termination_stalls = True
    launcher = make_launcher(native, tmp_path)

    with pytest.raises(LaunchError):
        launcher.launch(make_command(tmp_path))

    assert "output_close_abort" in native.calls
    native.failure = None
    native.termination_stalls = False
    launcher.close()
    assert "output_close_drain" in native.calls
    assert native.handles == set()


def test_persistent_release_failure_remains_owned_until_close_retry(tmp_path: Path) -> None:
    native = FakeNative("bootstrap_writer_close_always")
    launcher = make_launcher(native, tmp_path)

    with pytest.raises(LaunchError):
        launcher.launch(make_command(tmp_path))
    with pytest.raises(ProcessTerminationError):
        launcher.close()

    assert native.handles
    native.failure = None
    launcher.close()
    assert native.handles == set()


def test_unexpected_helper_exit_blocks_launch_until_child_cleanup(tmp_path: Path) -> None:
    native = FakeNative()
    launcher = make_launcher(native, tmp_path)
    tree = launcher.launch(make_command(tmp_path))
    native.crash_helper()

    with pytest.raises(LaunchError):
        launcher.launch(make_command(tmp_path))

    tree.close(graceful_timeout=0, forced_timeout=1)
    replacement = launcher.launch(make_command(tmp_path))
    replacement.close(graceful_timeout=0, forced_timeout=1)
    launcher.close()
    assert native.handles == set()


def test_window_close_verifies_current_job_membership_and_pid(tmp_path: Path) -> None:
    native = FakeNative("graceful_exit")
    launcher = make_launcher(native, tmp_path)
    tree = launcher.launch(make_command(tmp_path))

    tree.close(graceful_timeout=1, forced_timeout=1)

    verification = [
        "collect_windows",
        "window_pid",
        "open_window_process",
        "is_process_in_job",
        "window_pid",
        "post_close",
    ]
    start = native.calls.index("collect_windows")
    assert native.calls[start : start + len(verification)] == verification
    launcher.close()


def test_window_from_unrelated_process_never_receives_close(tmp_path: Path) -> None:
    native = FakeNative()
    native.window_pid = 777
    launcher = make_launcher(native, tmp_path)
    tree = launcher.launch(make_command(tmp_path))

    tree.close(graceful_timeout=0, forced_timeout=1)

    assert "is_process_in_job" in native.calls
    assert "post_close" not in native.calls
    launcher.close()


def test_failed_tree_handle_close_is_retryable(tmp_path: Path) -> None:
    native = FakeNative()
    launcher = make_launcher(native, tmp_path)
    tree = launcher.launch(make_command(tmp_path))
    process_handle = next(
        handle for handle, process_id in native.process_by_handle.items() if process_id == 501
    )
    native.close_failure_handle = process_handle

    with pytest.raises(ProcessTerminationError):
        tree.close(graceful_timeout=0, forced_timeout=1)

    native.close_failure_handle = None
    tree.close(graceful_timeout=0, forced_timeout=1)
    tree.close(graceful_timeout=0, forced_timeout=1)
    launcher.close()
    assert native.handles == set()


def test_failed_forced_termination_retains_tree_until_retry(tmp_path: Path) -> None:
    native = FakeNative()
    launcher = make_launcher(native, tmp_path)
    tree = launcher.launch(make_command(tmp_path))
    native.termination_stalls = True

    with pytest.raises(ProcessTerminationError):
        tree.close(graceful_timeout=0, forced_timeout=0)

    assert "output_close_abort" in native.calls
    assert tree.poll() is None
    native.termination_stalls = False
    tree.close(graceful_timeout=0, forced_timeout=1)
    launcher.close()
    assert native.handles == set()
