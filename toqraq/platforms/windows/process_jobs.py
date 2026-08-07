"""Win32 Job Object ownership and bounded observation."""

from __future__ import annotations

import ctypes
import math
import time
from ctypes import wintypes

from . import process_abi as abi
from .process_errors import handle_value, raise_last_error
from .process_types import NativeHandle

_JOB_POLL_INTERVAL_SECONDS = 0.01


class WindowsJobApi:
    """Own operations whose authority is one Job Object handle."""

    def __init__(self) -> None:
        """Bind Job Object creation, query, membership, and termination."""
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._create = kernel32.CreateJobObjectW
        self._create.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        self._create.restype = wintypes.HANDLE
        self._set_information = kernel32.SetInformationJobObject
        self._set_information.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        self._set_information.restype = wintypes.BOOL
        self._query_information = kernel32.QueryInformationJobObject
        self._query_information.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._query_information.restype = wintypes.BOOL
        self._terminate = kernel32.TerminateJobObject
        self._terminate.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self._terminate.restype = wintypes.BOOL
        self._contains = kernel32.IsProcessInJob
        self._contains.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.BOOL),
        ]
        self._contains.restype = wintypes.BOOL

    def create_job(self) -> NativeHandle:
        """Create one unnamed, non-inheritable Job Object."""
        handle = handle_value(self._create(None, None))
        if not handle:
            raise_last_error()
        return handle

    def configure_kill_on_close(self, handle: NativeHandle) -> None:
        """Make handle closure terminate all current job members."""
        information = abi.JobExtendedLimitInformation()
        information.BasicLimitInformation.LimitFlags = abi.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self._set_information(
            handle,
            abi.JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(information),
            ctypes.sizeof(information),
        ):
            raise_last_error()

    def terminate_job(self, job: NativeHandle) -> None:
        """Force every current process in one job to exit."""
        if not self._terminate(job, abi.FORCED_EXIT_CODE):
            raise_last_error()

    def wait_job_empty(self, job: NativeHandle, timeout: float) -> bool:
        """Wait a bounded duration for a job to contain no live process."""
        _require_timeout(timeout)
        deadline = time.monotonic() + timeout
        while self._active_process_count(job):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(_JOB_POLL_INTERVAL_SECONDS, remaining))
        return True

    def contains_process(self, job: NativeHandle, process: NativeHandle) -> bool:
        """Check current membership using an open process handle, not a stale PID."""
        result = wintypes.BOOL()
        if not self._contains(process, job, ctypes.byref(result)):
            raise_last_error()
        return bool(result.value)

    def _active_process_count(self, job: NativeHandle) -> int:
        information = abi.JobBasicAccountingInformation()
        if not self._query_information(
            job,
            abi.JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION,
            ctypes.byref(information),
            ctypes.sizeof(information),
            None,
        ):
            raise_last_error()
        return int(information.ActiveProcesses)


def _require_timeout(timeout: float) -> None:
    """Reject invalid job wait bounds."""
    if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout < 0:
        raise ValueError("job wait timeout is invalid")
