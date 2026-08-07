"""Authoritative pure native-preview aspect-fit policy tests."""

from __future__ import annotations

import pytest
from toqraq.core.geometry import Rect, Size
from toqraq.core.preview_geometry import aspect_fit_rect, pane_host_point


@pytest.mark.parametrize(
    ("pane", "viewport", "expected"),
    [
        (Rect(100, 50, 800, 600), Size(1_920, 1_080), Rect(100, 125, 800, 450)),
        (Rect(100, 50, 800, 600), Size(1_080, 1_920), Rect(331, 50, 338, 600)),
        (Rect(7, 11, 801, 601), Size(16, 9), Rect(7, 86, 801, 451)),
        (Rect(-50, -80, 400, 800), Size(16, 9), Rect(-50, 207, 400, 225)),
        (Rect(0, 0, 1, 1), Size(32_768, 1), Rect(0, 0, 1, 1)),
    ],
)
def test_aspect_fit_centers_complete_landscape_portrait_and_odd_geometry(
    pane: Rect,
    viewport: Size,
    expected: Rect,
) -> None:
    assert aspect_fit_rect(pane, viewport) == expected


def test_aspect_fit_recomputes_from_each_resized_pane() -> None:
    viewport = Size(960, 540)

    assert aspect_fit_rect(Rect(0, 0, 960, 540), viewport) == Rect(0, 0, 960, 540)
    assert aspect_fit_rect(Rect(0, 0, 540, 960), viewport) == Rect(0, 328, 540, 304)


def test_pane_host_point_uses_the_physical_pane_not_letterbox_geometry() -> None:
    point = pane_host_point(Rect(100, 50, 801, 601))
    assert (point.x, point.y) == (500, 350)
