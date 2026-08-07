"""Private anonymous-pipe creation and bounded synchronous I/O."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from ...core.process_tree import MAX_PROCESS_BOOTSTRAP_BYTES
from . import process_abi as abi
from .process_errors import handle_value, raise_last_error, raise_windows_error
from .process_types import NativeHandle, NativePipe


class WindowsPipeApi:
    """Create only non-inheritable local pipe handles."""

    def __init__(self) -> None:
        """Bind anonymous pipe and synchronous bounded I/O functions."""
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._create_pipe = kernel32.CreatePipe
        self._create_pipe.argtypes = [
            ctypes.POINTER(wintypes.HANDLE),
            ctypes.POINTER(wintypes.HANDLE),
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        self._create_pipe.restype = wintypes.BOOL
        self._write = kernel32.WriteFile
        self._write.argtypes = [
            wintypes.HANDLE,
            wintypes.LPCVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        self._write.restype = wintypes.BOOL
        self._peek = kernel32.PeekNamedPipe
        self._peek.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._peek.restype = wintypes.BOOL
        self._read = kernel32.ReadFile
        self._read.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        self._read.restype = wintypes.BOOL

    def create_pipe(self) -> NativePipe:
        """Create a pipe whose two local handles are both non-inheritable."""
        read = wintypes.HANDLE()
        write = wintypes.HANDLE()
        if not self._create_pipe(
            ctypes.byref(read),
            ctypes.byref(write),
            None,
            MAX_PROCESS_BOOTSTRAP_BYTES,
        ):
            raise_last_error()
        return NativePipe(read=handle_value(read), write=handle_value(write))

    def write_pipe(self, handle: NativeHandle, payload: bytes) -> None:
        """Write one bounded bootstrap value completely before child creation."""
        if not payload or len(payload) > MAX_PROCESS_BOOTSTRAP_BYTES:
            raise ValueError("process bootstrap payload is invalid")
        offset = 0
        while offset < len(payload):
            remaining = payload[offset:]
            buffer = ctypes.create_string_buffer(remaining, len(remaining))
            written = wintypes.DWORD()
            if not self._write(
                handle,
                buffer,
                len(remaining),
                ctypes.byref(written),
                None,
            ):
                raise_last_error()
            if not written.value:
                raise OSError("WriteFile made no bootstrap progress")
            offset += int(written.value)

    def read_pipe(self, handle: NativeHandle, maximum_bytes: int) -> bytes | None:
        """Read available bytes, return empty while idle, or None at EOF."""
        if isinstance(maximum_bytes, bool) or maximum_bytes < 1:
            raise ValueError("process output read bound is invalid")
        available = wintypes.DWORD()
        ctypes.set_last_error(0)
        if not self._peek(handle, None, 0, None, ctypes.byref(available), None):
            error = ctypes.get_last_error()
            if error in {abi.ERROR_BROKEN_PIPE, abi.ERROR_NO_DATA}:
                return None
            raise_windows_error(error)
        if not available.value:
            return b""
        count = min(int(available.value), maximum_bytes)
        buffer = ctypes.create_string_buffer(count)
        read = wintypes.DWORD()
        ctypes.set_last_error(0)
        if not self._read(handle, buffer, count, ctypes.byref(read), None):
            error = ctypes.get_last_error()
            if error in {abi.ERROR_BROKEN_PIPE, abi.ERROR_NO_DATA}:
                return None
            raise_windows_error(error)
        return bytes(buffer.raw[: read.value])
