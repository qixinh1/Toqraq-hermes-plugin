"""Pure authoritative geometry policy for native preview presentation."""

from __future__ import annotations

from .geometry import Point, Rect, Size


def aspect_fit_rect(pane: Rect, viewport: Size) -> Rect:
    """Center the closest whole-pixel aspect fit completely inside a pane."""
    if not isinstance(pane, Rect):
        raise ValueError("preview pane rectangle is invalid")
    if not isinstance(viewport, Size):
        raise ValueError("preview viewport size is invalid")

    if pane.width * viewport.height <= pane.height * viewport.width:
        width = pane.width
        height = max(
            1,
            min(
                pane.height,
                _nearest_integer_ratio(pane.width * viewport.height, viewport.width),
            ),
        )
    else:
        width = max(
            1,
            min(
                pane.width,
                _nearest_integer_ratio(pane.height * viewport.width, viewport.height),
            ),
        )
        height = pane.height
    return Rect(
        x=pane.x + (pane.width - width) // 2,
        y=pane.y + (pane.height - height) // 2,
        width=width,
        height=height,
    )


def _nearest_integer_ratio(numerator: int, denominator: int) -> int:
    """Round one positive rational value to the nearest whole pixel."""
    return (numerator + denominator // 2) // denominator


def pane_host_point(pane: Rect) -> Point:
    """Return one deterministic interior point for locating the pane's host window."""
    if not isinstance(pane, Rect):
        raise ValueError("preview pane rectangle is invalid")
    return Point(
        x=pane.x + pane.width // 2,
        y=pane.y + pane.height // 2,
    )
