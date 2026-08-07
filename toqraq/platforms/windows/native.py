"""Typed standard-library bindings for the Win32 display boundary."""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from ctypes import wintypes

from ...core.errors import PlatformOperationError

WindowHandle = int
NativeRect = tuple[int, int, int, int]
WindowVisitor = Callable[[WindowHandle], bool]

# Window data indexes.
GWL_STYLE = -16
GWL_EXSTYLE = -20
GWLP_HWNDPARENT = -8
GW_OWNER = 4

# Window styles used by magnetic preview attachment.
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
WS_VISIBLE = 0x10000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000

# SetWindowPos and ShowWindow constants.
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SW_HIDE = 0
SW_SHOWNA = 8

_ERROR_ACCESS_DENIED = 5
_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

_NativeCallback = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
_WindowEnumProc = _NativeCallback(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

_set_process_dpi_awareness_context = _user32.SetProcessDpiAwarenessContext
_set_process_dpi_awareness_context.argtypes = [ctypes.c_void_p]
_set_process_dpi_awareness_context.restype = wintypes.BOOL

_enum_windows = _user32.EnumWindows
_enum_windows.argtypes = [_WindowEnumProc, wintypes.LPARAM]
_enum_windows.restype = wintypes.BOOL

_is_window = _user32.IsWindow
_is_window.argtypes = [wintypes.HWND]
_is_window.restype = wintypes.BOOL

_is_window_visible = _user32.IsWindowVisible
_is_window_visible.argtypes = [wintypes.HWND]
_is_window_visible.restype = wintypes.BOOL

_get_window_long = _user32.GetWindowLongW
_get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
_get_window_long.restype = wintypes.LONG

_set_window_long = _user32.SetWindowLongW
_set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
_set_window_long.restype = wintypes.LONG

_get_window_rect = _user32.GetWindowRect
_get_window_rect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_get_window_rect.restype = wintypes.BOOL

_get_client_rect = _user32.GetClientRect
_get_client_rect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_get_client_rect.restype = wintypes.BOOL

_client_to_screen = _user32.ClientToScreen
_client_to_screen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
_client_to_screen.restype = wintypes.BOOL

_get_window_thread_process_id = _user32.GetWindowThreadProcessId
_get_window_thread_process_id.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_get_window_thread_process_id.restype = wintypes.DWORD

_set_window_pos = _user32.SetWindowPos
_set_window_pos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
_set_window_pos.restype = wintypes.BOOL

_get_window = _user32.GetWindow
_get_window.argtypes = [wintypes.HWND, wintypes.UINT]
_get_window.restype = wintypes.HWND

_set_window_long_ptr = _user32.SetWindowLongPtrW
_set_window_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LPARAM]
_set_window_long_ptr.restype = wintypes.LPARAM

_set_window_region = _user32.SetWindowRgn
_set_window_region.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
_set_window_region.restype = ctypes.c_int

_show_window_async = _user32.ShowWindowAsync
_show_window_async.argtypes = [wintypes.HWND, ctypes.c_int]
_show_window_async.restype = wintypes.BOOL

_create_rect_region = _gdi32.CreateRectRgn
_create_rect_region.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
_create_rect_region.restype = wintypes.HRGN

_delete_object = _gdi32.DeleteObject
_delete_object.argtypes = [wintypes.HGDIOBJ]
_delete_object.restype = wintypes.BOOL


def enumerate_windows(visitor: WindowVisitor) -> None:
    """Enumerate top-level windows in Z-order until the visitor stops."""
    callback_error: BaseException | None = None
    stopped = False

    def callback(raw_handle: int, _parameter: int) -> int:
        nonlocal callback_error, stopped
        try:
            keep_going = visitor(int(raw_handle))
        except BaseException as exc:
            callback_error = exc
            return 0
        stopped = not keep_going
        return int(keep_going)

    proc = _WindowEnumProc(callback)
    ctypes.set_last_error(0)
    succeeded = bool(_enum_windows(proc, 0))
    if callback_error is not None:
        raise callback_error
    if not succeeded and not stopped:
        _raise_last_error("EnumWindows")


def is_window(handle: WindowHandle) -> bool:
    """Return whether a native window handle is live."""
    return handle != 0 and bool(_is_window(handle))


def is_window_visible(handle: WindowHandle) -> bool:
    """Return whether a native window is visible."""
    return bool(_is_window_visible(handle))


def get_window_long(handle: WindowHandle, index: int) -> int:
    """Read a 32-bit window attribute without ambiguity around zero."""
    ctypes.set_last_error(0)
    value = int(_get_window_long(handle, index))
    if value == 0 and ctypes.get_last_error():
        _raise_last_error("GetWindowLongW")
    return value & 0xFFFFFFFF


def set_window_long(handle: WindowHandle, index: int, value: int) -> None:
    """Write a 32-bit window attribute and reject native failures."""
    ctypes.set_last_error(0)
    previous = int(_set_window_long(handle, index, ctypes.c_int32(value).value))
    if previous == 0 and ctypes.get_last_error():
        _raise_last_error("SetWindowLongW")


def get_window_rect(handle: WindowHandle) -> NativeRect:
    """Return a window rectangle in screen coordinates."""
    rect = wintypes.RECT()
    ctypes.set_last_error(0)
    if not _get_window_rect(handle, ctypes.byref(rect)):
        _raise_last_error("GetWindowRect")
    return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)


def get_client_rect(handle: WindowHandle) -> NativeRect:
    """Return a window client rectangle in client coordinates."""
    rect = wintypes.RECT()
    ctypes.set_last_error(0)
    if not _get_client_rect(handle, ctypes.byref(rect)):
        _raise_last_error("GetClientRect")
    return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)


def client_to_screen(handle: WindowHandle, point: tuple[int, int]) -> tuple[int, int]:
    """Convert one client-coordinate point to physical screen coordinates."""
    native_point = wintypes.POINT(point[0], point[1])
    ctypes.set_last_error(0)
    if not _client_to_screen(handle, ctypes.byref(native_point)):
        _raise_last_error("ClientToScreen")
    return int(native_point.x), int(native_point.y)


def get_window_process_id(handle: WindowHandle) -> int:
    """Return the process ID that owns a native window."""
    process_id = wintypes.DWORD()
    ctypes.set_last_error(0)
    if not _get_window_thread_process_id(handle, ctypes.byref(process_id)):
        _raise_last_error("GetWindowThreadProcessId")
    return int(process_id.value)


def set_window_pos(
    handle: WindowHandle,
    insert_after: WindowHandle,
    rect: NativeRect,
    flags: int,
) -> None:
    """Set native position, size, and z-order attributes."""
    x, y, width, height = rect
    ctypes.set_last_error(0)
    if not _set_window_pos(handle, insert_after, x, y, width, height, flags):
        _raise_last_error("SetWindowPos")


def get_window(handle: WindowHandle, command: int) -> WindowHandle:
    """Return a window related to another native window."""
    return int(_get_window(handle, command) or 0)


def set_window_pointer(handle: WindowHandle, index: int, value: int) -> None:
    """Write pointer-sized window data without ambiguity around zero."""
    ctypes.set_last_error(0)
    previous = int(_set_window_long_ptr(handle, index, value))
    if previous == 0 and ctypes.get_last_error():
        _raise_last_error("SetWindowLongPtrW")


def create_rect_region(rect: NativeRect) -> int:
    """Create a rectangular GDI region owned by the caller."""
    left, top, right, bottom = rect
    ctypes.set_last_error(0)
    region = int(_create_rect_region(left, top, right, bottom) or 0)
    if not region:
        _raise_last_error("CreateRectRgn")
    return region


def set_window_region(handle: WindowHandle, region: int | None) -> None:
    """Apply a region, transferring successful non-null ownership to Windows."""
    ctypes.set_last_error(0)
    if _set_window_region(handle, region, True):
        return
    error = ctypes.get_last_error()
    if region is not None:
        _delete_object(region)
    _raise_windows_error("SetWindowRgn", error)


def show_window_async(handle: WindowHandle, command: int) -> None:
    """Post a visibility change without waiting on the target process."""
    ctypes.set_last_error(0)
    if not _show_window_async(handle, command):
        _raise_last_error("ShowWindowAsync")


def enable_dpi_awareness() -> None:
    """Request physical pixels or accept the DPI policy already owned by Hermes."""
    ctypes.set_last_error(0)
    if _set_process_dpi_awareness_context(_PER_MONITOR_AWARE_V2):
        return
    error = ctypes.get_last_error()
    if error != _ERROR_ACCESS_DENIED:
        _raise_windows_error("SetProcessDpiAwarenessContext", error)


def _raise_last_error(operation: str) -> None:
    """Raise a typed platform failure using the calling thread's last error."""
    _raise_windows_error(operation, ctypes.get_last_error())


def _raise_windows_error(operation: str, error: int) -> None:
    """Raise a typed platform failure for a failed Win32 operation."""
    raise PlatformOperationError(
        parameters={"operation": operation},
        details={"reason": "windows_api_failed", "native_error": error},
    )
