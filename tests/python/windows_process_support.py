"""Real Win32 process observation owned by integration tests."""

from __future__ import annotations

import ctypes
import threading
import time
from collections.abc import Callable
from ctypes import wintypes

_SYNCHRONIZE = 0x00100000
_PROCESS_TERMINATE = 0x0001
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258
_OBSERVATION_INTERVAL_SECONDS = 0.01


def wait_for(predicate: Callable[[], bool], timeout: float) -> None:
    """Wait for an observable condition within a monotonic deadline."""
    deadline = time.monotonic() + timeout
    while not predicate():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("observable process condition did not arrive")
        threading.Event().wait(min(_OBSERVATION_INTERVAL_SECONDS, remaining))


def open_process_for_wait(process_id: int) -> int:
    """Open a synchronization and cleanup handle to one test-owned process."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_process.restype = wintypes.HANDLE
    handle = int(open_process(_SYNCHRONIZE | _PROCESS_TERMINATE, False, process_id) or 0)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


def wait_handle_ended(handle: int, timeout_seconds: float) -> bool:
    """Return whether one test-owned process handle becomes signaled."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    wait = kernel32.WaitForSingleObject
    wait.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    wait.restype = wintypes.DWORD
    result = int(wait(handle, round(timeout_seconds * 1000)))
    if result == _WAIT_OBJECT_0:
        return True
    if result == _WAIT_TIMEOUT:
        return False
    raise ctypes.WinError(ctypes.get_last_error())


def close_test_handle(handle: int) -> None:
    """Close one process handle owned only by an integration test."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    close = kernel32.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    if not close(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def terminate_test_process(handle: int) -> None:
    """Force a leaked test fixture process to exit during failure cleanup."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    terminate = kernel32.TerminateProcess
    terminate.argtypes = [wintypes.HANDLE, wintypes.UINT]
    terminate.restype = wintypes.BOOL
    if not terminate(handle, 1):
        raise ctypes.WinError(ctypes.get_last_error())
