"""Tests for geometry boundary models."""

from __future__ import annotations

import pytest
from toqraq.core.geometry import Rect, Size


@pytest.mark.parametrize("value", [0, True, 1.5, 32_769])
def test_invalid_dimensions_are_rejected(value: object) -> None:
    """Dimensions are bounded strict integers."""
    with pytest.raises(ValueError):
        Size(value, 1)  # type: ignore[arg-type]


def test_rect_rejects_untrusted_field_types() -> None:
    """Rect construction does not coerce strings."""
    with pytest.raises(ValueError):
        Rect("1", 2, 3, 4)  # type: ignore[arg-type]


@pytest.mark.parametrize("coordinate", [-1_000_001, 1_000_001])
def test_rect_rejects_out_of_range_coordinates(coordinate: int) -> None:
    with pytest.raises(ValueError):
        Rect(coordinate, 0, 1, 1)
