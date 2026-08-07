"""Minimal helper parent that exits when its Hermes host exits."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

_SYNCHRONIZE = 0x00100000
_WAIT_OBJECT_0 = 0
_INFINITE = 0xFFFFFFFF
_INVALID_ARGUMENT_EXIT_CODE = 64
_PARENT_OPEN_EXIT_CODE = 65
_PARENT_WAIT_EXIT_CODE = 66


def main(arguments: list[str]) -> int:
    """Wait on the exact host process supplied by the trusted launcher."""
    if len(arguments) != 1 or not arguments[0].isdecimal():
        return _INVALID_ARGUMENT_EXIT_CODE
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_process.restype = wintypes.HANDLE
    wait = kernel32.WaitForSingleObject
    wait.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    wait.restype = wintypes.DWORD
    close = kernel32.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    parent = open_process(_SYNCHRONIZE, False, int(arguments[0]))
    if not parent:
        return _PARENT_OPEN_EXIT_CODE
    try:
        return 0 if wait(parent, _INFINITE) == _WAIT_OBJECT_0 else _PARENT_WAIT_EXIT_CODE
    finally:
        close(parent)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
