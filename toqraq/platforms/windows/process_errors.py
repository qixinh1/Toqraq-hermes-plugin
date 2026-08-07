"""Shared helpers for preserving Win32 error codes at the platform boundary."""

from __future__ import annotations

import ctypes


def raise_last_error() -> None:
    """Raise the calling thread's current Win32 failure."""
    raise_windows_error(ctypes.get_last_error())


def raise_windows_error(error: int) -> None:
    """Raise one native error without formatting it into public output."""
    raise ctypes.WinError(error)


def handle_value(handle: int | None | ctypes.c_void_p) -> int:
    """Convert a ctypes handle result to a stable integer."""
    if isinstance(handle, int):
        return handle
    if handle is None or handle.value is None:
        return 0
    return int(handle.value)
