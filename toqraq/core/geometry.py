"""Validated geometry values used at native and process boundaries."""

from __future__ import annotations

from dataclasses import dataclass

_MAX_DIMENSION = 32_768
_MAX_COORDINATE = 1_000_000


@dataclass(frozen=True)
class Point:
    """A validated screen-absolute point in physical pixels."""

    x: int
    y: int

    def __post_init__(self) -> None:
        """Reject booleans, fractions, and unbounded screen positions."""
        if any(isinstance(value, bool) or not isinstance(value, int) for value in (self.x, self.y)):
            raise ValueError("point coordinates must be integers")
        if not -_MAX_COORDINATE <= self.x <= _MAX_COORDINATE:
            raise ValueError(f"point x must be within +/-{_MAX_COORDINATE}")
        if not -_MAX_COORDINATE <= self.y <= _MAX_COORDINATE:
            raise ValueError(f"point y must be within +/-{_MAX_COORDINATE}")


@dataclass(frozen=True)
class Size:
    """A validated width and height in pixels."""

    width: int
    height: int

    def __post_init__(self) -> None:
        """Reject non-integer or out-of-range dimensions."""
        if any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in (self.width, self.height)
        ):
            raise ValueError("size dimensions must be integers")
        if not 0 < self.width <= _MAX_DIMENSION or not 0 < self.height <= _MAX_DIMENSION:
            raise ValueError(f"size dimensions must be between 1 and {_MAX_DIMENSION}")


@dataclass(frozen=True)
class Rect:
    """A validated screen-absolute rectangle in physical pixels."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        """Reject non-integer or out-of-range fields."""
        if any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in (self.x, self.y, self.width, self.height)
        ):
            raise ValueError("rectangle fields must be integers")
        if not -_MAX_COORDINATE <= self.x <= _MAX_COORDINATE:
            raise ValueError(f"rectangle x must be within +/-{_MAX_COORDINATE}")
        if not -_MAX_COORDINATE <= self.y <= _MAX_COORDINATE:
            raise ValueError(f"rectangle y must be within +/-{_MAX_COORDINATE}")
        if not 0 < self.width <= _MAX_DIMENSION or not 0 < self.height <= _MAX_DIMENSION:
            raise ValueError(f"rectangle dimensions must be between 1 and {_MAX_DIMENSION}")
