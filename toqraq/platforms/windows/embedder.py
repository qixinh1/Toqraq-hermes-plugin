"""Win32 window discovery, native ownership, and geometry follow.

The game stays a borderless top-level window owned by the Hermes host. Windows
therefore maintains host-relative z-order and minimization, while the renderer
reports the pane geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...core.errors import PlatformOperationError
from ...core.geometry import Rect
from . import native

_STYLE_STRIP = (
    native.WS_CAPTION
    | native.WS_THICKFRAME
    | native.WS_MINIMIZEBOX
    | native.WS_MAXIMIZEBOX
    | native.WS_SYSMENU
)
_EXSTYLE_STRIP = native.WS_EX_APPWINDOW
_EXSTYLE_ADD = native.WS_EX_TOOLWINDOW
_POS_FLAGS = native.SWP_NOZORDER | native.SWP_NOACTIVATE


@dataclass(frozen=True)
class WindowSnapshot:
    """Native attributes restored when magnetic embedding ends."""

    style: int
    exstyle: int
    owner: int
    rect: tuple[int, int, int, int]
    visible: bool


def snapshot(child: int) -> WindowSnapshot:
    """Capture native window attributes before embedding.

    Args:
        child: Native window handle.

    Returns:
        Attributes required by :func:`restore`.
    """
    return WindowSnapshot(
        style=native.get_window_long(child, native.GWL_STYLE),
        exstyle=native.get_window_long(child, native.GWL_EXSTYLE),
        owner=_owner(child),
        rect=native.get_window_rect(child),
        visible=native.is_window_visible(child),
    )


def embed(child: int, host: int) -> None:
    """Prepare a window for magnetic embedding into a host.

    Makes the window borderless, hides it from the taskbar and alt-tab, and
    assigns the Hermes window as its native owner.

    Args:
        child: Native handle of the window to embed.
        host: Native handle of the host window.
    """
    _set_owner(child, host)
    style = native.get_window_long(child, native.GWL_STYLE) & ~_STYLE_STRIP
    native.set_window_long(child, native.GWL_STYLE, style | native.WS_VISIBLE)
    exstyle = native.get_window_long(child, native.GWL_EXSTYLE)
    exstyle = (exstyle & ~_EXSTYLE_STRIP) | _EXSTYLE_ADD
    native.set_window_long(child, native.GWL_EXSTYLE, exstyle)
    native.set_window_pos(
        child,
        0,
        (0, 0, 0, 0),
        _POS_FLAGS | native.SWP_NOSIZE | native.SWP_NOMOVE | native.SWP_FRAMECHANGED,
    )


def restore(child: int, state: WindowSnapshot) -> None:
    """Restore a window prepared for magnetic embedding.

    Args:
        child: Native window handle.
        state: Snapshot captured before embedding.
    """
    if not native.is_window(child):
        return
    native.set_window_long(child, native.GWL_STYLE, state.style)
    native.set_window_long(child, native.GWL_EXSTYLE, state.exstyle)
    _set_owner(child, state.owner)
    left, top, right, bottom = state.rect
    native.set_window_region(child, None)
    native.set_window_pos(
        child,
        (native.HWND_TOPMOST if state.exstyle & native.WS_EX_TOPMOST else native.HWND_NOTOPMOST),
        (left, top, right - left, bottom - top),
        native.SWP_NOACTIVATE | native.SWP_FRAMECHANGED,
    )
    _set_visible(child, state.visible)


def _owner(child: int) -> int:
    """Return the native owner of a top-level window."""
    return native.get_window(child, native.GW_OWNER)


def _set_owner(child: int, host: int) -> None:
    """Assign and verify the native owner of a top-level window."""
    native.set_window_pointer(child, native.GWLP_HWNDPARENT, host)
    actual = _owner(child)
    if actual != host:
        raise PlatformOperationError(
            parameters={"operation": "assign_window_owner"},
            details={"reason": "owner_mismatch"},
        )


def follow(child: int, rect: Rect, host: int) -> None:
    """Move and resize an owned window to a screen-absolute rect.

    The window is additionally clipped to the host's client area when a
    host is given, so it never overdraws the host's edges.

    Args:
        child: Native child window handle.
        rect: Target rectangle in screen-absolute physical pixels.
        host: Owning window for client-area clipping.
    """
    if not native.is_window(child):
        return
    native.set_window_pos(child, 0, (rect.x, rect.y, rect.width, rect.height), _POS_FLAGS)
    if native.is_window(host):
        _clip_to_host(child, host, rect)


def _clip_to_host(child: int, host: int, rect: Rect) -> None:
    """Clip the owned window to the host's client area.

    Args:
        child: Owned window handle.
        host: Owning window handle.
        rect: The window's current screen-absolute rect.
    """
    left, top = native.client_to_screen(host, (0, 0))
    client_left, client_top, client_right, client_bottom = native.get_client_rect(host)
    width = client_right - client_left
    height = client_bottom - client_top
    clip_left = max(rect.x, left)
    clip_top = max(rect.y, top)
    clip_right = min(rect.x + rect.width, left + width)
    clip_bottom = min(rect.y + rect.height, top + height)
    if clip_right <= clip_left or clip_bottom <= clip_top:
        region_rect = (0, 0, 0, 0)
    else:
        region_rect = (
            clip_left - rect.x,
            clip_top - rect.y,
            clip_right - rect.x,
            clip_bottom - rect.y,
        )
    native.set_window_region(child, native.create_rect_region(region_rect))


def set_visible(child: int, visible: bool) -> None:
    """Show or hide an owned window without activating it.

    Args:
        child: Native window handle.
        visible: Desired visibility.
    """
    if not native.is_window(child):
        return
    _set_visible(child, visible)


def _set_visible(child: int, visible: bool) -> None:
    """Post a visibility change without waiting on another process."""
    native.show_window_async(child, native.SW_SHOWNA if visible else native.SW_HIDE)
