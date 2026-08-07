"""Windows Job Object implementation of the process-tree port."""

from __future__ import annotations

import math
import threading
from collections.abc import Callable
from typing import Protocol

from ...core.errors import ProcessTerminationError
from ...core.process_tree import ProcessOutputSnapshot
from .process_ownership import OwnedHandle
from .process_types import NativeHandle, NativeWindow


class _TreeHandleApi(Protocol):
    def open_process_for_job_query(self, process_id: int) -> NativeHandle: ...

    def root_exit_code(self, process: NativeHandle) -> int | None: ...

    def wait_process_exit(self, process: NativeHandle, timeout: float) -> bool: ...

    def close_handle(self, handle: NativeHandle) -> None: ...


class _TreeJobApi(Protocol):
    def terminate_job(self, job: NativeHandle) -> None: ...

    def wait_job_empty(self, job: NativeHandle, timeout: float) -> bool: ...

    def contains_process(self, job: NativeHandle, process: NativeHandle) -> bool: ...


class _TreeWindowApi(Protocol):
    def collect_top_level(self) -> tuple[NativeWindow, ...]: ...

    def process_id(self, window: NativeWindow) -> int: ...

    def post_close(self, window: NativeWindow) -> None: ...


class _ProcessOutputOwner(Protocol):
    def snapshot(self) -> ProcessOutputSnapshot: ...

    def close(self, timeout: float, *, drain: bool) -> None: ...


class _ChildLease(Protocol):
    @property
    def closed(self) -> bool: ...

    def close(self) -> None: ...


class WindowsProcessTree:
    """Own one exact session job and every dependent native resource."""

    def __init__(
        self,
        handles: _TreeHandleApi,
        jobs: _TreeJobApi,
        windows: _TreeWindowApi,
        *,
        job: OwnedHandle,
        process: OwnedHandle,
        root_pid: int,
        output: _ProcessOutputOwner,
        child_lease: _ChildLease,
        on_released: Callable[[WindowsProcessTree], None],
    ) -> None:
        """Receive the complete committed process ownership ledger."""
        self._handles = handles
        self._jobs = jobs
        self._windows = windows
        self._job = job
        self._process = process
        self._root_pid = root_pid
        self._output = output
        self._child_lease = child_lease
        self._on_released = on_released
        self._verification_handles: list[OwnedHandle] = []
        self._output_closed = False
        self._exit_code: int | None = None
        self._released = False
        self._close_lock = threading.RLock()

    @property
    def root_pid(self) -> int:
        """Return the root process ID even after cleanup."""
        return self._root_pid

    def poll(self) -> int | None:
        """Return root exit only after the complete session job is empty."""
        with self._close_lock:
            if self._job.closed:
                return self._exit_code
            if not self._jobs.wait_job_empty(self._job.value, 0):
                return None
            return self._capture_exit_code()

    def wait(self, timeout: float) -> int:
        """Wait a bounded duration for all session processes to exit."""
        _require_timeout(timeout)
        with self._close_lock:
            if not self._job.closed and not self._jobs.wait_job_empty(self._job.value, timeout):
                raise TimeoutError(f"process tree {self._root_pid} did not exit")
            if not self._process.closed and not self._handles.wait_process_exit(
                self._process.value, timeout
            ):
                raise TimeoutError(f"process tree {self._root_pid} root did not exit")
            exit_code = self._capture_exit_code()
            if exit_code is None:
                raise TimeoutError(f"process tree {self._root_pid} exit is not observable")
            return exit_code

    def output(self) -> ProcessOutputSnapshot:
        """Return retained output without waiting for process exit."""
        return self._output.snapshot()

    def close(self, *, graceful_timeout: float, forced_timeout: float) -> None:
        """Gracefully request, forcibly terminate, and release with retries."""
        _require_timeout(graceful_timeout)
        _require_timeout(forced_timeout)
        with self._close_lock:
            if self._released:
                return
            failures: list[Exception] = []
            ended = self._job.closed
            if not self._job.closed:
                ended = self._end_processes(graceful_timeout, forced_timeout, failures)
            if ended:
                try:
                    root_ended = self._process.closed or self._handles.wait_process_exit(
                        self._process.value,
                        forced_timeout,
                    )
                    if not root_ended or self._capture_exit_code() is None:
                        failures.append(OSError("root process exit is not observable"))
                except OSError as exc:
                    failures.append(exc)
            self._close_output(forced_timeout, drain=ended, failures=failures)
            self._close_verification_handles(failures)
            if ended and self._exit_code is not None:
                _close_owned(self._process, failures)
            if ended:
                _close_owned(self._job, failures)
            if self._resources_released():
                try:
                    self._child_lease.close()
                except Exception as exc:
                    failures.append(exc)
                if self._child_lease.closed:
                    self._released = True
                    self._on_released(self)
            if failures or not self._released:
                cause = failures[0] if failures else OSError("process resources remain owned")
                raise ProcessTerminationError(
                    details={"reason": "windows_process_tree_cleanup_failed", "retryable": True},
                    cause=cause,
                ) from cause

    def _end_processes(
        self,
        graceful_timeout: float,
        forced_timeout: float,
        failures: list[Exception],
    ) -> bool:
        job = self._job.value
        try:
            if self._jobs.wait_job_empty(job, 0):
                return True
        except OSError as exc:
            failures.append(exc)
        self._request_graceful(job)
        try:
            if self._jobs.wait_job_empty(job, graceful_timeout):
                return True
        except OSError as exc:
            failures.append(exc)
        try:
            self._jobs.terminate_job(job)
        except OSError as exc:
            failures.append(exc)
        try:
            if self._jobs.wait_job_empty(job, forced_timeout):
                return True
            failures.append(TimeoutError(f"process tree {self._root_pid} survived termination"))
        except OSError as exc:
            failures.append(exc)
        return False

    def _request_graceful(self, job: NativeHandle) -> None:
        try:
            candidates = self._windows.collect_top_level()
        except OSError:
            return
        for window in candidates:
            try:
                first_pid = self._windows.process_id(window)
                process = OwnedHandle(
                    self._handles,
                    self._handles.open_process_for_job_query(first_pid),
                )
            except OSError:
                continue
            self._verification_handles.append(process)
            try:
                current_member = self._jobs.contains_process(job, process.value)
                second_pid = self._windows.process_id(window)
                if current_member and first_pid == second_pid:
                    self._windows.post_close(window)
            except OSError:
                pass
            try:
                process.close()
            except OSError:
                pass
            else:
                self._verification_handles.remove(process)

    def _capture_exit_code(self) -> int | None:
        if self._exit_code is None and not self._process.closed:
            self._exit_code = self._handles.root_exit_code(self._process.value)
        return self._exit_code

    def _close_output(
        self,
        timeout: float,
        *,
        drain: bool,
        failures: list[Exception],
    ) -> None:
        if self._output_closed:
            return
        try:
            self._output.close(timeout, drain=drain)
        except (OSError, TimeoutError) as exc:
            failures.append(exc)
        else:
            self._output_closed = True

    def _close_verification_handles(self, failures: list[Exception]) -> None:
        for handle in tuple(self._verification_handles):
            try:
                handle.close()
            except OSError as exc:
                failures.append(exc)
            else:
                self._verification_handles.remove(handle)

    def _resources_released(self) -> bool:
        return (
            self._job.closed
            and self._process.closed
            and self._output_closed
            and not self._verification_handles
        )


def _close_owned(handle: OwnedHandle, failures: list[Exception]) -> None:
    try:
        handle.close()
    except OSError as exc:
        failures.append(exc)


def _require_timeout(timeout: float, *, allow_zero: bool = True) -> None:
    """Reject unbounded waits at the platform boundary."""
    if (
        isinstance(timeout, bool)
        or not math.isfinite(timeout)
        or timeout < 0
        or (not allow_zero and timeout == 0)
    ):
        raise ValueError("process timeout is invalid")
