"""Deterministic native ownership seams for Windows process tests."""

from __future__ import annotations

import sys
from pathlib import Path

from toqraq.core.process_tree import (
    ProcessBootstrap,
    ProcessEnvironment,
    ProcessLaunch,
    ProcessOutputSnapshot,
)
from toqraq.platforms.windows.process_launcher import WindowsProcessTreeLauncher
from toqraq.platforms.windows.process_ownership import OwnedHandle
from toqraq.platforms.windows.process_types import (
    NativeCommand,
    NativePipe,
    NativeProcess,
)

BOOTSTRAP_BYTES = b"one-shot-bridge-bootstrap"
_ENVIRONMENT = ProcessEnvironment(variables=())


class FakeNative:
    """Implement every narrow native port with observable ownership."""

    def __init__(self, failure: str | None = None) -> None:
        """Create empty main, remote, process, and Job Object tables."""
        self.failure = failure
        self.calls: list[str] = []
        self.handles: set[int] = set()
        self.remote_handles: set[int] = set()
        self.inheritable: set[int] = set()
        self.process_by_handle: dict[int, int] = {}
        self.exited: set[int] = set()
        self.jobs: dict[int, set[int]] = {}
        self.windows = (901,)
        self.window_pid = 501
        self.payload: bytes | None = None
        self.child_standard_handles: tuple[int, int, int] | None = None
        self.bootstrap_writer: int | None = None
        self.child_thread: int | None = None
        self._next_handle = 10
        self._job_count = 0
        self._pipe_count = 0
        self._duplicate_count = 0
        self._close_failed = False
        self.close_failure_handle: int | None = None
        self.termination_stalls = False

    def create_job(self) -> int:
        self._job_count += 1
        operation = "lifetime_job" if self._job_count == 1 else "session_job"
        self.calls.append(operation)
        self._fail(operation)
        handle = self._new()
        self.jobs[handle] = set()
        return handle

    def configure_kill_on_close(self, handle: int) -> None:
        operation = "configure_lifetime" if not self.jobs[handle] else "configure_session"
        if self._job_count > 1 and handle == max(self.jobs):
            operation = "configure_session"
        self.calls.append(operation)
        self._fail(operation)

    def create_helper(self, command: NativeCommand, *, lifetime_job: int) -> NativeProcess:
        del command
        self.calls.append("create_helper")
        self._fail("create_helper")
        process = self._new_process(401)
        thread = self._new()
        self.jobs[lifetime_job].add(401)
        return NativeProcess(process=process, thread=thread, pid=401)

    def create_pipe(self) -> NativePipe:
        self._pipe_count += 1
        operation = ("stdout_pipe", "stderr_pipe", "bootstrap_pipe")[(self._pipe_count - 1) % 3]
        self.calls.append(operation)
        self._fail(operation)
        read = self._new()
        write = self._new()
        if operation == "bootstrap_pipe":
            self.bootstrap_writer = write
        if self.failure == "inheritable_pipe" and self._pipe_count == 1:
            self.inheritable.add(read)
        return NativePipe(read=read, write=write)

    def write_pipe(self, handle: int, payload: bytes) -> None:
        assert handle in self.handles
        self.calls.append("bootstrap_write")
        self._fail("bootstrap_write")
        self.payload = payload

    def read_pipe(self, handle: int, maximum_bytes: int) -> bytes | None:
        del handle, maximum_bytes
        return b""

    def duplicate_into(self, source: int, target_process: int) -> int:
        assert source in self.handles
        assert self.process_by_handle[target_process] == 401
        self._duplicate_count += 1
        operation = ("duplicate_stdin", "duplicate_stdout", "duplicate_stderr")[
            (self._duplicate_count - 1) % 3
        ]
        self.calls.append(operation)
        self._fail(operation)
        remote = 10_000 + self._duplicate_count
        self.remote_handles.add(remote)
        return remote

    def close_remote(self, source_process: int, source: int) -> None:
        assert self.process_by_handle[source_process] == 401
        self.calls.append(f"close_remote_{source}")
        self.remote_handles.discard(source)
        self._fail("close_remote")

    def create_child(
        self,
        command: ProcessLaunch,
        *,
        parent_process: int,
        session_job: int,
        stdin_read: int,
        stdout_write: int,
        stderr_write: int,
    ) -> NativeProcess:
        del command
        assert self.process_by_handle[parent_process] == 401
        assert {stdin_read, stdout_write, stderr_write} <= self.remote_handles
        for operation in (
            "parent_attribute",
            "handle_attribute",
            "job_attribute",
            "create_child",
        ):
            self.calls.append(operation)
            self._fail(operation)
        self.calls.append("create_child_atomic")
        self.child_standard_handles = (stdin_read, stdout_write, stderr_write)
        process = self._new_process(501)
        thread = self._new()
        self.child_thread = thread
        self.jobs[session_job].add(501)
        for members in self.jobs.values():
            if 401 in members:
                members.add(501)
        return NativeProcess(process=process, thread=thread, pid=501)

    def terminate_job(self, job: int) -> None:
        self.calls.append(f"terminate_job_{job}")
        self._fail("terminate_job")
        if self.termination_stalls:
            return
        exiting = tuple(self.jobs[job])
        for process_id in exiting:
            self._mark_pid_exited(process_id)
            for members in self.jobs.values():
                members.discard(process_id)

    def wait_job_empty(self, job: int, timeout: float) -> bool:
        del timeout
        self.calls.append(f"wait_job_{job}")
        return not self.jobs[job]

    def contains_process(self, job: int, process: int) -> bool:
        self.calls.append("is_process_in_job")
        membership = "lifetime_membership" if 401 in self.jobs[job] else "session_membership"
        if self.failure == membership:
            return False
        return self.process_by_handle[process] in self.jobs[job]

    def collect_top_level(self) -> tuple[int, ...]:
        self.calls.append("collect_windows")
        return self.windows

    def process_id(self, window: int) -> int:
        assert window == 901
        self.calls.append("window_pid")
        return self.window_pid

    def post_close(self, window: int) -> None:
        assert window == 901
        self.calls.append("post_close")
        if self.failure == "graceful_exit":
            self._mark_pid_exited(501)
            for members in self.jobs.values():
                members.discard(501)

    def open_process_for_job_query(self, process_id: int) -> int:
        self.calls.append("open_window_process")
        return self._new_process(process_id)

    def wait_process_exit(self, process: int, timeout: float) -> bool:
        del timeout
        return process in self.exited

    def root_exit_code(self, process: int) -> int | None:
        return 0 if process in self.exited else None

    def is_inheritable(self, handle: int) -> bool:
        assert handle in self.handles
        return handle in self.inheritable

    def close_handle(self, handle: int) -> None:
        self.calls.append(f"close_{handle}")
        if self.failure == "close_always":
            raise OSError("injected persistent close failure")
        if self.failure == "bootstrap_writer_close_always" and handle == self.bootstrap_writer:
            raise OSError("injected persistent bootstrap writer close failure")
        target_close_once = (
            self.failure == "bootstrap_writer_close_once" and handle == self.bootstrap_writer
        ) or (self.failure == "child_thread_close_once" and handle == self.child_thread)
        if target_close_once and not self._close_failed:
            self._close_failed = True
            raise OSError("injected selected close failure")
        if self.failure == "close_once" and not self._close_failed:
            self._close_failed = True
            raise OSError("injected close failure")
        if handle == self.close_failure_handle:
            raise OSError("injected selected close failure")
        if handle not in self.handles:
            raise OSError("double close")
        self.handles.remove(handle)
        self.inheritable.discard(handle)

    def crash_helper(self) -> None:
        """Simulate an unexpected helper exit without touching active games."""
        self._mark_pid_exited(401)
        for members in self.jobs.values():
            members.discard(401)
        self.remote_handles.clear()

    def _new(self) -> int:
        handle = self._next_handle
        self._next_handle += 1
        self.handles.add(handle)
        return handle

    def _new_process(self, process_id: int) -> int:
        handle = self._new()
        self.process_by_handle[handle] = process_id
        return handle

    def _mark_pid_exited(self, process_id: int) -> None:
        self.exited.update(
            handle for handle, current in self.process_by_handle.items() if current == process_id
        )

    def _fail(self, operation: str) -> None:
        if self.failure == operation:
            raise OSError(f"injected {operation} failure")
        if self.failure == f"base_{operation}":
            raise KeyboardInterrupt(operation)


class FakeOutput:
    """Share the exact output handle owners with the launch ledger."""

    def __init__(self, native: FakeNative, stdout: OwnedHandle, stderr: OwnedHandle) -> None:
        """Receive the two existing owners without copying their values."""
        self.native = native
        self.stdout = stdout
        self.stderr = stderr

    def start(self) -> None:
        self.native.calls.append("output_start")
        self.native._fail("output_start")

    def snapshot(self) -> ProcessOutputSnapshot:
        return ProcessOutputSnapshot(
            chunks=(),
            next_sequence=1,
            truncated=False,
            failed_streams=frozenset(),
        )

    def close(self, timeout: float, *, drain: bool) -> None:
        del timeout
        mode = "drain" if drain else "abort"
        self.native.calls.append(f"output_close_{mode}")
        self.stdout.close()
        self.stderr.close()


class FakeOutputFactory:
    """Construct the output owner through the production contract."""

    def __init__(self, native: FakeNative) -> None:
        """Retain only the fake native observation table."""
        self._native = native

    def __call__(
        self,
        pipes: object,
        *,
        stdout_read: OwnedHandle,
        stderr_read: OwnedHandle,
        character_limit: int,
        read_size: int,
        idle_interval: float,
    ) -> FakeOutput:
        del pipes, character_limit, read_size, idle_interval
        return FakeOutput(self._native, stdout_read, stderr_read)


def make_command(tmp_path: Path) -> ProcessLaunch:
    """Build one valid fake-platform command."""
    return ProcessLaunch(
        executable=Path(sys.executable),
        arguments=("-c", "pass"),
        working_directory=tmp_path,
        environment=_ENVIRONMENT,
        bootstrap=ProcessBootstrap(payload=BOOTSTRAP_BYTES),
    )


def make_launcher(native: FakeNative, tmp_path: Path) -> WindowsProcessTreeLauncher:
    """Compose one launcher from the single observable fake."""
    helper_command = NativeCommand(
        executable=Path(sys.executable),
        arguments=("helper",),
        working_directory=tmp_path,
        environment=_ENVIRONMENT,
    )
    return WindowsProcessTreeLauncher(
        handles=native,
        jobs=native,
        pipes=native,
        creation=native,
        windows=native,
        helper_command=helper_command,
        output_factory=FakeOutputFactory(native),
    )
