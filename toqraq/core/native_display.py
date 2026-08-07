"""Pure platform port for renderer-owned native preview mutations."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .geometry import Point, Rect
from .preview import NativeWindowReference


@runtime_checkable
class NativeDisplay(Protocol):
    """Attach and position one already-discovered native preview window."""

    def locate_host(
        self,
        point: Point,
        *,
        excluded_process_id: int,
    ) -> NativeWindowReference:
        """Return the Hermes top-level window at one pane-owned screen point."""
        ...

    def attach(
        self,
        child: NativeWindowReference,
        host: NativeWindowReference,
    ) -> None:
        """Apply reversible native ownership and presentation mutations."""
        ...

    def restore(self, child: NativeWindowReference) -> None:
        """Restore or forget all native mutations owned for one child."""
        ...

    def follow(
        self,
        child: NativeWindowReference,
        rect: Rect,
        host: NativeWindowReference,
    ) -> None:
        """Move, resize, and clip one child to its pane rectangle."""
        ...

    def set_visible(self, child: NativeWindowReference, visible: bool) -> None:
        """Show or hide one attached child without activation."""
        ...
