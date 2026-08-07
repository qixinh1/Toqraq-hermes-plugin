"""Dedicated helper-parent lifecycle and remote-handle leases."""

from __future__ import annotations

import contextlib
import threading
from typing import Protocol

from .process_ownership import OwnedHandle
from .process_types import NativeCommand, NativeHandle, NativeProcess


class _ParentHandleApi(Protocol):
    def duplicate_into(
        self,
        source: NativeHandle,
        target_process: NativeHandle,
    ) -> NativeHandle: ...

    def close_remote(self, source_process: NativeHandle, source: NativeHandle) -> None: ...

    def wait_process_exit(self, process: NativeHandle, timeout: float) -> bool: ...

    def is_inheritable(self, handle: NativeHandle) -> bool: ...

    def close_handle(self, handle: NativeHandle) -> None: ...


class _ParentJobApi(Protocol):
    def create_job(self) -> NativeHandle: ...

    def configure_kill_on_close(self, handle: NativeHandle) -> None: ...

    def terminate_job(self, job: NativeHandle) -> None: ...

    def wait_job_empty(self, job: NativeHandle, timeout: float) -> bool: ...

    def contains_process(self, job: NativeHandle, process: NativeHandle) -> bool: ...


class _ParentCreationApi(Protocol):
    def create_helper(
        self,
        command: NativeCommand,
        *,
        lifetime_job: NativeHandle,
    ) -> NativeProcess: ...


class WindowsLaunchParent:
    """Own one helper and the process-lifetime Job Object it parents from."""

    def __init__(
        self,
        handles: _ParentHandleApi,
        jobs: _ParentJobApi,
        creation: _ParentCreationApi,
        *,
        command: NativeCommand,
        cleanup_timeout: float,
    ) -> None:
        """Receive the helper command and every native ownership capability."""
        self._handles = handles
        self._jobs = jobs
        self._creation = creation
        self._command = command
        self._cleanup_timeout = cleanup_timeout
        self._job: OwnedHandle | None = None
        self._process: OwnedHandle | None = None
        self._thread: OwnedHandle | None = None
        self._pid: int | None = None
        self._remote_leases = 0
        self._child_leases = 0
        self._lock = threading.RLock()

    @property
    def pid(self) -> int | None:
        """Return the current helper PID for bounded diagnostics."""
        with self._lock:
            return self._pid

    @property
    def process_handle(self) -> NativeHandle:
        """Return the current helper process handle after a readiness check."""
        with self._lock:
            self._ensure_ready_locked()
            if self._process is None:
                raise RuntimeError("launch parent has no process")
            return self._process.value

    def ensure_ready(self) -> None:
        """Create or verify the one helper available for launch."""
        with self._lock:
            self._ensure_ready_locked()

    def duplicate(self, source: NativeHandle) -> RemoteHandleLease:
        """Duplicate a private main handle into the helper as inheritable."""
        with self._lock:
            self._ensure_ready_locked()
            if self._process is None:
                raise RuntimeError("launch parent has no process")
            parent_process = self._process.value
            remote = self._handles.duplicate_into(source, parent_process)
            self._remote_leases += 1
            return RemoteHandleLease(self, parent_process, remote)

    def acquire_child(self, parent_process: NativeHandle) -> ParentChildLease:
        """Keep the helper lifetime job until one committed child is gone."""
        with self._lock:
            if self._process is None or self._process.value != parent_process:
                raise OSError("launch parent changed during process creation")
            self._child_leases += 1
            return ParentChildLease(self)

    def contains_process(self, process: NativeHandle) -> bool:
        """Verify that one created child inherited the exact lifetime job."""
        with self._lock:
            if self._job is None:
                return False
            return self._jobs.contains_process(self._job.value, process)

    def close(self) -> None:
        """Release the helper only when no remote or child lease remains."""
        with self._lock:
            if self._remote_leases or self._child_leases:
                raise OSError("launch parent still owns active leases")
            self._cleanup_locked()

    def _ensure_ready_locked(self) -> None:
        if self._process is not None:
            if not self._handles.wait_process_exit(self._process.value, 0):
                return
            if self._remote_leases or self._child_leases:
                raise OSError("launch parent exited while child ownership remains")
            self._cleanup_locked()
        elif self._job is not None or self._thread is not None:
            self._cleanup_locked()
        try:
            self._job = OwnedHandle(self._handles, self._jobs.create_job())
            self._require_private(self._job.value)
            self._jobs.configure_kill_on_close(self._job.value)
            native = self._creation.create_helper(
                self._command,
                lifetime_job=self._job.value,
            )
            self._process = OwnedHandle(self._handles, native.process)
            self._thread = OwnedHandle(self._handles, native.thread)
            self._pid = native.pid
            self._require_private(self._process.value)
            self._require_private(self._thread.value)
            self._thread.close()
            self._thread = None
            if self._handles.wait_process_exit(self._process.value, 0):
                raise OSError("launch parent exited during startup")
        except Exception:
            with contextlib.suppress(Exception):
                self._cleanup_locked()
            raise

    def _cleanup_locked(self) -> None:
        if self._job is not None and not self._jobs.wait_job_empty(self._job.value, 0):
            self._jobs.terminate_job(self._job.value)
            if not self._jobs.wait_job_empty(self._job.value, self._cleanup_timeout):
                raise TimeoutError("launch parent survived forced termination")
        if self._thread is not None:
            self._thread.close()
            self._thread = None
        if self._process is not None:
            self._process.close()
            self._process = None
            self._pid = None
        if self._job is not None:
            self._job.close()
            self._job = None

    def _require_private(self, handle: NativeHandle) -> None:
        if self._handles.is_inheritable(handle):
            raise OSError("main-process handle unexpectedly inheritable")

    def _close_remote(self, parent_process: NativeHandle, remote: NativeHandle) -> None:
        try:
            self._handles.close_remote(parent_process, remote)
        finally:
            with self._lock:
                self._remote_leases -= 1

    def _release_child(self) -> None:
        with self._lock:
            if self._child_leases < 1:
                raise RuntimeError("launch parent child lease released twice")
            self._child_leases -= 1


class RemoteHandleLease:
    """Own one inheritable handle value in the helper's handle table."""

    __slots__ = ("_owner", "_parent_process", "_remote")

    def __init__(
        self,
        owner: WindowsLaunchParent,
        parent_process: NativeHandle,
        remote: NativeHandle,
    ) -> None:
        """Receive the remote value and its fixed helper generation."""
        self._owner = owner
        self._parent_process = parent_process
        self._remote: NativeHandle | None = remote

    @property
    def value(self) -> NativeHandle:
        """Return the live helper-table handle value."""
        if self._remote is None:
            raise RuntimeError("remote handle lease is already closed")
        return self._remote

    @property
    def closed(self) -> bool:
        """Return whether remote close has been attempted exactly once."""
        return self._remote is None

    def close(self) -> None:
        """Forget the lease even if Windows reports CLOSE_SOURCE failure."""
        if self._remote is None:
            return
        remote = self._remote
        self._remote = None
        self._owner._close_remote(self._parent_process, remote)


class ParentChildLease:
    """Keep the helper generation while one session process may remain."""

    __slots__ = ("_owner",)

    def __init__(self, owner: WindowsLaunchParent) -> None:
        """Retain one child count in the helper owner."""
        self._owner: WindowsLaunchParent | None = owner

    @property
    def closed(self) -> bool:
        """Return whether the child count has been released."""
        return self._owner is None

    def close(self) -> None:
        """Release exactly once after session process ownership is empty."""
        if self._owner is None:
            return
        owner = self._owner
        self._owner = None
        owner._release_child()
