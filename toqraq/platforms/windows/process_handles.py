"""Win32 operations for local and remote process handles."""

from __future__ import annotations

import ctypes
import math
from ctypes import wintypes

from . import process_abi as abi
from .process_errors import handle_value, raise_last_error
from .process_types import NativeHandle


class WindowsHandleApi:
    """Bind handle duplication, observation, and release operations."""

    def __init__(self) -> None:
        """Bind only the Kernel32 functions used by handle owners."""
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._current_process = kernel32.GetCurrentProcess
        self._current_process.argtypes = []
        self._current_process.restype = wintypes.HANDLE
        self._duplicate = kernel32.DuplicateHandle
        self._duplicate.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.HANDLE),
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        self._duplicate.restype = wintypes.BOOL
        self._close = kernel32.CloseHandle
        self._close.argtypes = [wintypes.HANDLE]
        self._close.restype = wintypes.BOOL
        self._open_process = kernel32.OpenProcess
        self._open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self._open_process.restype = wintypes.HANDLE
        self._wait = kernel32.WaitForSingleObject
        self._wait.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self._wait.restype = wintypes.DWORD
        self._exit_code = kernel32.GetExitCodeProcess
        self._exit_code.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self._exit_code.restype = wintypes.BOOL
        self._handle_information = kernel32.GetHandleInformation
        self._handle_information.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self._handle_information.restype = wintypes.BOOL

    def duplicate_into(
        self,
        source: NativeHandle,
        target_process: NativeHandle,
    ) -> NativeHandle:
        """Create one inheritable remote copy without changing the local handle."""
        target = wintypes.HANDLE()
        if not self._duplicate(
            self._current_process(),
            source,
            target_process,
            ctypes.byref(target),
            0,
            True,
            abi.DUPLICATE_SAME_ACCESS,
        ):
            raise_last_error()
        value = handle_value(target)
        if not value:
            raise OSError("DuplicateHandle returned an empty remote handle")
        return value

    def close_remote(self, source_process: NativeHandle, source: NativeHandle) -> None:
        """Close one remote handle using DUPLICATE_CLOSE_SOURCE.

        Windows closes the source even when this call reports failure. Callers
        must therefore forget their remote lease in a finally block.
        """
        ctypes.set_last_error(0)
        if not self._duplicate(
            source_process,
            source,
            None,
            None,
            0,
            False,
            abi.DUPLICATE_CLOSE_SOURCE,
        ):
            raise_last_error()

    def open_process_for_job_query(self, process_id: int) -> NativeHandle:
        """Open the current process behind a window PID for exact job checking."""
        handle = handle_value(
            self._open_process(abi.PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
        )
        if not handle:
            raise_last_error()
        return handle

    def wait_process_exit(self, process: NativeHandle, timeout: float) -> bool:
        """Wait a bounded duration for one process handle to become signaled."""
        _require_timeout(timeout)
        milliseconds = min(math.ceil(timeout * 1000), abi.MAXIMUM_WAIT_MILLISECONDS)
        result = int(self._wait(process, milliseconds))
        if result == abi.WAIT_OBJECT_0:
            return True
        if result == abi.WAIT_TIMEOUT:
            return False
        if result == abi.WAIT_FAILED:
            raise_last_error()
        raise OSError("unexpected process wait result")

    def root_exit_code(self, process: NativeHandle) -> int | None:
        """Return the exit code only after the process handle is signaled."""
        if not self.wait_process_exit(process, 0):
            return None
        code = wintypes.DWORD()
        if not self._exit_code(process, ctypes.byref(code)):
            raise_last_error()
        return int(code.value)

    def is_inheritable(self, handle: NativeHandle) -> bool:
        """Return the native inheritance bit for a main-process handle."""
        flags = wintypes.DWORD()
        if not self._handle_information(handle, ctypes.byref(flags)):
            raise_last_error()
        return bool(flags.value & abi.HANDLE_FLAG_INHERIT)

    def close_handle(self, handle: NativeHandle) -> None:
        """Close exactly one local handle."""
        if not self._close(handle):
            raise_last_error()


def _require_timeout(timeout: float) -> None:
    """Reject invalid native wait bounds."""
    if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout < 0:
        raise ValueError("process wait timeout is invalid")
