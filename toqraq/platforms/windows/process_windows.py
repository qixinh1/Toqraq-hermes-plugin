"""Bounded top-level-window collection and message primitives."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from . import process_abi as abi
from .process_errors import raise_last_error
from .process_types import NativeWindow


class WindowsProcessWindowApi:
    """Keep Win32 callbacks free of process and resource operations."""

    def __init__(self) -> None:
        """Bind enumeration, PID lookup, and non-blocking close messaging."""
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self._callback_type = callback_type
        self._enumerate = user32.EnumWindows
        self._enumerate.argtypes = [callback_type, wintypes.LPARAM]
        self._enumerate.restype = wintypes.BOOL
        self._process_id = user32.GetWindowThreadProcessId
        self._process_id.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self._process_id.restype = wintypes.DWORD
        self._post = user32.PostMessageW
        self._post.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        self._post.restype = wintypes.BOOL

    def collect_top_level(self) -> tuple[NativeWindow, ...]:
        """Collect a bounded HWND snapshot without native calls in the callback."""
        collected: list[NativeWindow] = []

        def collect(window: int, _parameter: int) -> int:
            collected.append(int(window))
            return int(len(collected) <= abi.MAX_TOP_LEVEL_WINDOWS)

        callback = self._callback_type(collect)
        ctypes.set_last_error(0)
        succeeded = bool(self._enumerate(callback, 0))
        error = ctypes.get_last_error()
        if not succeeded and error:
            raise_last_error()
        return tuple(collected[: abi.MAX_TOP_LEVEL_WINDOWS])

    def process_id(self, window: NativeWindow) -> int:
        """Return the PID currently associated with one HWND."""
        process_id = wintypes.DWORD()
        if not self._process_id(window, ctypes.byref(process_id)):
            raise_last_error()
        if not process_id.value:
            raise OSError("window has no current process")
        return int(process_id.value)

    def post_close(self, window: NativeWindow) -> None:
        """Post a non-blocking close request to one still-current HWND."""
        if not self._post(window, abi.WM_CLOSE, 0, 0):
            raise_last_error()
