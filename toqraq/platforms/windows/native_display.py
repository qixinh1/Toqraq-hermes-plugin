"""Windows implementation of reversible native preview presentation."""

from __future__ import annotations

import threading

from ...core.errors import PlatformOperationError
from ...core.geometry import Point, Rect
from ...core.native_display import NativeDisplay
from ...core.preview import NativeWindowReference
from . import dpi, embedder, host_window, native


class WindowsNativeDisplay(NativeDisplay):
    """Own original Win32 state for every child mutated by this instance."""

    def __init__(self) -> None:
        """Enable physical-pixel coordinates and create an empty mutation owner."""
        dpi.ensure_dpi_awareness()
        self._embedded: dict[int, embedder.WindowSnapshot] = {}
        self._lock = threading.RLock()

    def locate_host(
        self,
        point: Point,
        *,
        excluded_process_id: int,
    ) -> NativeWindowReference:
        """Resolve the interactive Hermes window containing one pane point."""
        if not isinstance(point, Point):
            raise ValueError("native host point is invalid")
        return NativeWindowReference(
            value=host_window.locate_host_window(
                (point.x, point.y),
                excluded_process_id=excluded_process_id,
            )
        )

    def attach(
        self,
        child: NativeWindowReference,
        host: NativeWindowReference,
    ) -> None:
        """Apply reversible border, owner, taskbar, and z-order changes."""
        child_handle = _live_handle(child)
        host_handle = _live_handle(host)
        with self._lock:
            existing = child_handle in self._embedded
            state = self._embedded[child_handle] if existing else embedder.snapshot(child_handle)
            if not existing:
                self._embedded[child_handle] = state
            try:
                embedder.embed(child_handle, host_handle)
            except Exception:
                if not existing:
                    embedder.restore(child_handle, state)
                    self._embedded.pop(child_handle, None)
                raise

    def restore(self, child: NativeWindowReference) -> None:
        """Restore a live child or forget state after its OS window vanished."""
        child_handle = _handle(child)
        with self._lock:
            state = self._embedded.get(child_handle)
            if state is None:
                return
            if not native.is_window(child_handle):
                self._embedded.pop(child_handle, None)
                return
            embedder.restore(child_handle, state)
            self._embedded.pop(child_handle, None)

    def follow(
        self,
        child: NativeWindowReference,
        rect: Rect,
        host: NativeWindowReference,
    ) -> None:
        """Move and clip an owned preview inside the current Hermes client area."""
        with self._lock:
            embedder.follow(_live_handle(child), rect, _live_handle(host))

    def set_visible(self, child: NativeWindowReference, visible: bool) -> None:
        """Change preview visibility without transferring focus."""
        if type(visible) is not bool:
            raise ValueError("native preview visibility is invalid")
        with self._lock:
            embedder.set_visible(_live_handle(child), visible)


def _handle(window: NativeWindowReference) -> int:
    """Unwrap one validated process-local native reference."""
    if not isinstance(window, NativeWindowReference):
        raise ValueError("native window reference is invalid")
    return int(window.value)


def _live_handle(window: NativeWindowReference) -> int:
    """Return one still-live Win32 handle or a stable platform failure."""
    value = _handle(window)
    if not native.is_window(value):
        raise PlatformOperationError(
            parameters={"operation": "validate_window"},
            details={"reason": "stale_window_handle"},
        )
    return value
