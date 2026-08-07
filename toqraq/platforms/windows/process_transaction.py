"""Typed acquisition ledger for one atomic Windows process launch."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Protocol

from ...core.process_tree import ProcessLaunch, ProcessOutputSnapshot
from .process_ownership import OwnedHandle
from .process_parent import ParentChildLease, RemoteHandleLease, WindowsLaunchParent
from .process_tree import WindowsProcessTree
from .process_types import (
    NativeCommand,
    NativeHandle,
    NativePipe,
    NativeProcess,
)


class _HandleApi(Protocol):
    def duplicate_into(
        self,
        source: NativeHandle,
        target_process: NativeHandle,
    ) -> NativeHandle: ...

    def close_remote(self, source_process: NativeHandle, source: NativeHandle) -> None: ...

    def open_process_for_job_query(self, process_id: int) -> NativeHandle: ...

    def wait_process_exit(self, process: NativeHandle, timeout: float) -> bool: ...

    def root_exit_code(self, process: NativeHandle) -> int | None: ...

    def is_inheritable(self, handle: NativeHandle) -> bool: ...

    def close_handle(self, handle: NativeHandle) -> None: ...


class _JobApi(Protocol):
    def create_job(self) -> NativeHandle: ...

    def configure_kill_on_close(self, handle: NativeHandle) -> None: ...

    def terminate_job(self, job: NativeHandle) -> None: ...

    def wait_job_empty(self, job: NativeHandle, timeout: float) -> bool: ...

    def contains_process(self, job: NativeHandle, process: NativeHandle) -> bool: ...


class _PipeApi(Protocol):
    def create_pipe(self) -> NativePipe: ...

    def write_pipe(self, handle: NativeHandle, payload: bytes) -> None: ...

    def read_pipe(self, handle: NativeHandle, maximum_bytes: int) -> bytes | None: ...


class _CreationApi(Protocol):
    def create_helper(
        self,
        command: NativeCommand,
        *,
        lifetime_job: NativeHandle,
    ) -> NativeProcess: ...

    def create_child(
        self,
        command: ProcessLaunch,
        *,
        parent_process: NativeHandle,
        session_job: NativeHandle,
        stdin_read: NativeHandle,
        stdout_write: NativeHandle,
        stderr_write: NativeHandle,
    ) -> NativeProcess: ...


class _WindowApi(Protocol):
    def collect_top_level(self) -> tuple[int, ...]: ...

    def process_id(self, window: int) -> int: ...

    def post_close(self, window: int) -> None: ...


class _OutputOwner(Protocol):
    def start(self) -> None: ...

    def snapshot(self) -> ProcessOutputSnapshot: ...

    def close(self, timeout: float, *, drain: bool) -> None: ...


class _OutputFactory(Protocol):
    def __call__(
        self,
        pipes: _PipeApi,
        *,
        stdout_read: OwnedHandle,
        stderr_read: OwnedHandle,
        character_limit: int,
        read_size: int,
        idle_interval: float,
    ) -> _OutputOwner: ...


class LaunchTransaction:
    """Retain every pre-commit acquisition in explicit typed slots."""

    def __init__(
        self,
        handles: _HandleApi,
        jobs: _JobApi,
        pipes: _PipeApi,
        creation: _CreationApi,
        parent: WindowsLaunchParent,
        *,
        rollback_timeout: float,
    ) -> None:
        """Create an empty ledger before the first fallible acquisition."""
        self._handles = handles
        self._jobs = jobs
        self._pipes = pipes
        self._creation = creation
        self._parent = parent
        self._rollback_timeout = rollback_timeout
        self.job: OwnedHandle | None = None
        self.stdout_read: OwnedHandle | None = None
        self.stdout_write: OwnedHandle | None = None
        self.stderr_read: OwnedHandle | None = None
        self.stderr_write: OwnedHandle | None = None
        self.bootstrap_read: OwnedHandle | None = None
        self.bootstrap_write: OwnedHandle | None = None
        self.stdin_remote: RemoteHandleLease | None = None
        self.stdout_remote: RemoteHandleLease | None = None
        self.stderr_remote: RemoteHandleLease | None = None
        self.process: OwnedHandle | None = None
        self.thread: OwnedHandle | None = None
        self.output: _OutputOwner | None = None
        self.child_lease: ParentChildLease | None = None
        self.root_pid: int | None = None
        self.transferred = False

    def prepare(
        self,
        command: ProcessLaunch,
        *,
        output_factory: _OutputFactory,
        output_character_limit: int,
        output_read_size: int,
        output_idle_interval: float,
    ) -> None:
        """Acquire, launch, and close every temporary inheritance lease."""
        self.job = OwnedHandle(self._handles, self._jobs.create_job())
        self._require_private(self.job)
        self._jobs.configure_kill_on_close(self.job.value)
        stdout = self._pipes.create_pipe()
        self.stdout_read = OwnedHandle(self._handles, stdout.read)
        self.stdout_write = OwnedHandle(self._handles, stdout.write)
        self._require_private(self.stdout_read)
        self._require_private(self.stdout_write)
        stderr = self._pipes.create_pipe()
        self.stderr_read = OwnedHandle(self._handles, stderr.read)
        self.stderr_write = OwnedHandle(self._handles, stderr.write)
        self._require_private(self.stderr_read)
        self._require_private(self.stderr_write)
        self.output = output_factory(
            self._pipes,
            stdout_read=self.stdout_read,
            stderr_read=self.stderr_read,
            character_limit=output_character_limit,
            read_size=output_read_size,
            idle_interval=output_idle_interval,
        )
        self.output.start()
        bootstrap = self._pipes.create_pipe()
        self.bootstrap_read = OwnedHandle(self._handles, bootstrap.read)
        self.bootstrap_write = OwnedHandle(self._handles, bootstrap.write)
        self._require_private(self.bootstrap_read)
        self._require_private(self.bootstrap_write)
        self._pipes.write_pipe(self.bootstrap_write.value, command.bootstrap.payload)
        self.bootstrap_write.close()
        self.stdin_remote = self._parent.duplicate(self.bootstrap_read.value)
        self.stdout_remote = self._parent.duplicate(self.stdout_write.value)
        self.stderr_remote = self._parent.duplicate(self.stderr_write.value)
        self.bootstrap_read.close()
        self.stdout_write.close()
        self.stderr_write.close()
        parent_process = self._parent.process_handle
        native = self._creation.create_child(
            command,
            parent_process=parent_process,
            session_job=self.job.value,
            stdin_read=self.stdin_remote.value,
            stdout_write=self.stdout_remote.value,
            stderr_write=self.stderr_remote.value,
        )
        self.process = OwnedHandle(self._handles, native.process)
        self.thread = OwnedHandle(self._handles, native.thread)
        self._require_private(self.process)
        self._require_private(self.thread)
        if not self._jobs.contains_process(self.job.value, self.process.value):
            raise OSError("root process is absent from its session job")
        if not self._parent.contains_process(self.process.value):
            raise OSError("root process is absent from its lifetime job")
        self.root_pid = native.pid
        self.child_lease = self._parent.acquire_child(parent_process)
        self.thread.close()
        self._close_remote_leases()

    def commit(
        self,
        windows: _WindowApi,
        *,
        on_released: Callable[[WindowsProcessTree], None],
    ) -> WindowsProcessTree:
        """Create the durable tree owner without copying any native handle."""
        if (
            self.job is None
            or self.process is None
            or self.output is None
            or self.child_lease is None
            or self.root_pid is None
        ):
            raise RuntimeError("process launch transaction is incomplete")
        return WindowsProcessTree(
            self._handles,
            self._jobs,
            windows,
            job=self.job,
            process=self.process,
            root_pid=self.root_pid,
            output=self.output,
            child_lease=self.child_lease,
            on_released=on_released,
        )

    def mark_transferred(self) -> None:
        """Prevent the pre-commit ledger from cleaning a committed tree."""
        self.transferred = True

    @property
    def empty(self) -> bool:
        """Return whether no local, remote, output, or child owner remains."""
        return self._resources_empty() and (self.child_lease is None or self.child_lease.closed)

    def rollback(self) -> None:
        """Boundedly release all slots while retaining every failed close."""
        if self.transferred:
            return
        self._close_remote_leases_safely()
        _close_safely(self.bootstrap_write)
        _close_safely(self.bootstrap_read)
        _close_safely(self.stdout_write)
        _close_safely(self.stderr_write)
        ended = self.process is None
        if self.job is not None and not self.job.closed:
            try:
                if not self._jobs.wait_job_empty(self.job.value, 0):
                    self._jobs.terminate_job(self.job.value)
                ended = self._jobs.wait_job_empty(self.job.value, self._rollback_timeout)
            except OSError:
                ended = False
        if self.output is not None:
            with contextlib.suppress(OSError, TimeoutError):
                self.output.close(self._rollback_timeout, drain=ended)
        else:
            _close_safely(self.stdout_read)
            _close_safely(self.stderr_read)
        _close_safely(self.thread)
        if ended and self.process is not None:
            with contextlib.suppress(OSError):
                if self._handles.wait_process_exit(self.process.value, self._rollback_timeout):
                    self.process.close()
        if ended:
            _close_safely(self.job)
        if self._resources_empty() and self.child_lease is not None:
            self.child_lease.close()

    def _resources_empty(self) -> bool:
        owners = (
            self.job,
            self.stdout_read,
            self.stdout_write,
            self.stderr_read,
            self.stderr_write,
            self.bootstrap_read,
            self.bootstrap_write,
            self.process,
            self.thread,
        )
        local_empty = all(owner is None or owner.closed for owner in owners)
        remotes = (self.stdin_remote, self.stdout_remote, self.stderr_remote)
        remote_empty = all(owner is None or owner.closed for owner in remotes)
        output_empty = self.output is None or (
            self.stdout_read is not None
            and self.stderr_read is not None
            and self.stdout_read.closed
            and self.stderr_read.closed
        )
        return local_empty and remote_empty and output_empty

    def _require_private(self, owner: OwnedHandle) -> None:
        if self._handles.is_inheritable(owner.value):
            raise OSError("main-process handle unexpectedly inheritable")

    def _close_remote_leases(self) -> None:
        for lease in (self.stdin_remote, self.stdout_remote, self.stderr_remote):
            if lease is not None:
                lease.close()

    def _close_remote_leases_safely(self) -> None:
        for lease in (self.stdin_remote, self.stdout_remote, self.stderr_remote):
            if lease is not None:
                with contextlib.suppress(OSError):
                    lease.close()


def _close_safely(owner: OwnedHandle | None) -> None:
    if owner is not None:
        with contextlib.suppress(OSError):
            owner.close()
