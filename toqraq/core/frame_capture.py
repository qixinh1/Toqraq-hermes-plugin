"""Pure frame-capture request, verified result, and focused port."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable

from .bridge import MAX_BRIDGE_BINARY_TRANSFER_BYTES
from .geometry import Size
from .observation import (
    ObservationRevision,
    validate_observation_timestamp,
)
from .png import png_dimensions

MAX_FRAME_CAPTURE_DIMENSION = 16_384
MAX_FRAME_CAPTURE_PIXELS = 67_108_864
FRAME_PNG_MIME_TYPE: Literal["image/png"] = "image/png"


class FrameScaling(StrEnum):
    """Closed capture scaling policies implemented by every bridge."""

    NATIVE = "native"
    CONTAIN = "contain"


@dataclass(frozen=True, slots=True, kw_only=True)
class FrameCaptureQuery:
    """Explicit dimensions, scaling, and PNG result byte ceiling."""

    maximum_size: Size
    scaling: FrameScaling
    maximum_bytes: int

    def __post_init__(self) -> None:
        """Reject oversized work before an engine capture begins."""
        if not isinstance(self.maximum_size, Size):
            raise ValueError("frame maximum size is invalid")
        _validate_capture_size(self.maximum_size, label="frame maximum size")
        if not isinstance(self.scaling, FrameScaling):
            raise ValueError("frame scaling policy is invalid")
        if (
            isinstance(self.maximum_bytes, bool)
            or not isinstance(self.maximum_bytes, int)
            or not 1 <= self.maximum_bytes <= MAX_BRIDGE_BINARY_TRANSFER_BYTES
        ):
            raise ValueError("frame byte ceiling is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class FrameCaptureResult:
    """One completely received and verified immutable PNG capture."""

    viewport_size: Size
    captured_at_unix_ms: int
    encoded_size: Size
    frame_revision: ObservationRevision
    data: bytes = field(repr=False)

    def __post_init__(self) -> None:
        """Require bounded PNG bytes whose IHDR matches the encoded size."""
        if not isinstance(self.viewport_size, Size):
            raise ValueError("frame viewport size is invalid")
        validate_observation_timestamp(self.captured_at_unix_ms)
        if not isinstance(self.encoded_size, Size):
            raise ValueError("frame encoded size is invalid")
        _validate_capture_size(self.encoded_size, label="frame encoded size")
        if not isinstance(self.frame_revision, ObservationRevision):
            raise ValueError("frame revision is invalid")
        if type(self.data) is not bytes:
            raise ValueError("frame data must be immutable bytes")
        if not 1 <= len(self.data) <= MAX_BRIDGE_BINARY_TRANSFER_BYTES:
            raise ValueError("frame data length is invalid")
        _validate_png(self.data, expected_size=self.encoded_size)

    @property
    def byte_length(self) -> int:
        """Return the verified immutable payload length."""
        return len(self.data)


def expected_frame_capture_size(
    viewport_size: Size,
    query: FrameCaptureQuery,
) -> Size:
    """Return the one deterministic encoded size permitted by a query."""
    if not isinstance(viewport_size, Size):
        raise ValueError("frame viewport size is invalid")
    if not isinstance(query, FrameCaptureQuery):
        raise ValueError("frame capture query is invalid")

    maximum = query.maximum_size
    fits = viewport_size.width <= maximum.width and viewport_size.height <= maximum.height
    if query.scaling is FrameScaling.NATIVE:
        if not fits:
            raise ValueError("native frame does not fit the requested maximum")
        return viewport_size
    if fits:
        return viewport_size

    width_limited = maximum.width * viewport_size.height <= maximum.height * viewport_size.width
    if width_limited:
        return Size(
            width=maximum.width,
            height=max(
                1,
                viewport_size.height * maximum.width // viewport_size.width,
            ),
        )
    return Size(
        width=max(
            1,
            viewport_size.width * maximum.height // viewport_size.height,
        ),
        height=maximum.height,
    )


def validate_frame_capture_result(
    result: FrameCaptureResult,
    query: FrameCaptureQuery,
) -> None:
    """Correlate one verified capture with the request that owns it."""
    if not isinstance(result, FrameCaptureResult):
        raise ValueError("frame capture result is invalid")
    if not isinstance(query, FrameCaptureQuery):
        raise ValueError("frame capture query is invalid")
    expected_size = expected_frame_capture_size(result.viewport_size, query)
    if result.encoded_size != expected_size:
        raise ValueError("frame encoded size does not match its request")
    if result.byte_length > query.maximum_bytes:
        raise ValueError("frame data exceeds its request byte ceiling")


@runtime_checkable
class FrameCapture(Protocol):
    """Read-only engine boundary returning a complete verified frame."""

    async def capture(self, query: FrameCaptureQuery) -> FrameCaptureResult:
        """Return only after the complete binary transfer has been verified."""
        ...


def _validate_capture_size(value: Size, *, label: str) -> None:
    """Apply the capture-specific dimension and pixel-work ceilings."""
    if (
        value.width > MAX_FRAME_CAPTURE_DIMENSION
        or value.height > MAX_FRAME_CAPTURE_DIMENSION
        or value.width * value.height > MAX_FRAME_CAPTURE_PIXELS
    ):
        raise ValueError(f"{label} exceeds the capture policy")


def _validate_png(data: bytes, *, expected_size: Size) -> None:
    """Validate the shared bounded PNG header and exact encoded dimensions."""
    width, height = png_dimensions(data)
    if (width, height) != (expected_size.width, expected_size.height):
        raise ValueError("frame PNG dimensions do not match the encoded size")
