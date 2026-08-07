"""Public geometry values and their pure-core conversions."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..core.geometry import Rect, Size
from .base import ContractModel

MAX_DIMENSION = 32_768
MAX_SCREEN_COORDINATE = 1_000_000

Dimension = Annotated[int, Field(gt=0, le=MAX_DIMENSION)]
ScreenCoordinate = Annotated[
    int,
    Field(ge=-MAX_SCREEN_COORDINATE, le=MAX_SCREEN_COORDINATE),
]


class SizeValue(ContractModel):
    """Positive pixel dimensions."""

    width: Dimension
    height: Dimension

    @classmethod
    def from_core(cls, value: Size) -> SizeValue:
        """Build public dimensions from a core value."""
        return cls(width=value.width, height=value.height)

    def to_core(self) -> Size:
        """Build the pure geometry value used by services and adapters."""
        return Size(self.width, self.height)


class RectValue(ContractModel):
    """Screen-absolute physical pixel rectangle."""

    x: ScreenCoordinate
    y: ScreenCoordinate
    width: Dimension
    height: Dimension

    def to_core(self) -> Rect:
        """Build the pure rectangle used by the display service."""
        return Rect(self.x, self.y, self.width, self.height)
