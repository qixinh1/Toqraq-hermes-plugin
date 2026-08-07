"""Strict JSON-RPC contracts for one bounded runtime frame capture."""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal, TypeAlias

from pydantic import Field, StringConstraints, model_validator

from ..core.bridge import MAX_BRIDGE_BINARY_TRANSFER_BYTES
from ..core.frame_capture import (
    FRAME_PNG_MIME_TYPE,
    MAX_FRAME_CAPTURE_DIMENSION,
    MAX_FRAME_CAPTURE_PIXELS,
    FrameCaptureQuery,
    FrameCaptureResult,
    FrameScaling,
    expected_frame_capture_size,
    validate_frame_capture_result,
)
from ..core.geometry import Size
from ..core.observation import ObservationRevision
from .base import ContractModel
from .bridge import JSON_RPC_VERSION
from .bridge_observation import ObservationRevisionValue, ObservationUnixMilliseconds
from .bridge_rpc import BridgeHostRequestId
from .geometry import SizeValue
from .identifiers import Sha256Value

FRAME_CAPTURE_METHOD: Literal["toqraq.frame.capture"] = "toqraq.frame.capture"
FrameScalingValue: TypeAlias = Literal["native", "contain"]
FRAME_TRANSFER_ID_CHARACTERS = 32

FrameTransferId = Annotated[
    str,
    StringConstraints(
        min_length=FRAME_TRANSFER_ID_CHARACTERS,
        max_length=FRAME_TRANSFER_ID_CHARACTERS,
        pattern=rf"^[0-9a-f]{{{FRAME_TRANSFER_ID_CHARACTERS}}}$",
    ),
]


class FrameCaptureSizeValue(ContractModel):
    """Pixel dimensions independently bounded for native capture work."""

    width: int = Field(ge=1, le=MAX_FRAME_CAPTURE_DIMENSION)
    height: int = Field(ge=1, le=MAX_FRAME_CAPTURE_DIMENSION)

    @model_validator(mode="after")
    def validate_pixel_count(self) -> FrameCaptureSizeValue:
        """Reject dimensions whose area exceeds the capture work budget."""
        if self.width * self.height > MAX_FRAME_CAPTURE_PIXELS:
            raise ValueError("frame dimensions exceed the pixel budget")
        return self

    def to_core(self) -> Size:
        """Convert bounded capture dimensions to the pure geometry value."""
        return Size(width=self.width, height=self.height)

    @classmethod
    def from_core(cls, value: Size) -> FrameCaptureSizeValue:
        """Create exact capture dimensions from one validated pure size."""
        return cls(width=value.width, height=value.height)


class FrameCaptureParams(ContractModel):
    """Explicit frame dimensions, scaling, and transfer byte ceiling."""

    maximum_size: FrameCaptureSizeValue
    scaling: FrameScalingValue
    maximum_bytes: int = Field(ge=1, le=MAX_BRIDGE_BINARY_TRANSFER_BYTES)

    def to_core(self) -> FrameCaptureQuery:
        """Convert strict params to the focused pure frame query."""
        return FrameCaptureQuery(
            maximum_size=self.maximum_size.to_core(),
            scaling=FrameScaling(self.scaling),
            maximum_bytes=self.maximum_bytes,
        )

    @classmethod
    def from_core(cls, value: FrameCaptureQuery) -> FrameCaptureParams:
        """Create canonical wire params from one validated pure query."""
        return cls(
            maximum_size=FrameCaptureSizeValue.from_core(value.maximum_size),
            scaling=value.scaling.value,
            maximum_bytes=value.maximum_bytes,
        )


class FrameTransferValue(ContractModel):
    """Exact announcement for the single binary PNG message that follows."""

    transfer_id: FrameTransferId
    mime_type: Literal["image/png"]
    size: FrameCaptureSizeValue
    byte_length: int = Field(ge=1, le=MAX_BRIDGE_BINARY_TRANSFER_BYTES)
    sha256: Sha256Value
    frame_revision: ObservationRevisionValue

    @classmethod
    def from_core(
        cls,
        value: FrameCaptureResult,
        *,
        transfer_id: str,
    ) -> FrameTransferValue:
        """Announce verified core bytes without copying or retaining them."""
        return cls(
            transfer_id=transfer_id,
            mime_type=FRAME_PNG_MIME_TYPE,
            size=FrameCaptureSizeValue.from_core(value.encoded_size),
            byte_length=value.byte_length,
            sha256=hashlib.sha256(value.data).hexdigest(),
            frame_revision=value.frame_revision.value,
        )


class FrameCaptureResultValue(ContractModel):
    """Real viewport facts plus one binary transfer announcement."""

    viewport_size: SizeValue
    captured_at_unix_ms: ObservationUnixMilliseconds
    transfer: FrameTransferValue

    def validate_announcement(self, *, query: FrameCaptureQuery) -> None:
        """Reject response work outside its request before accepting binary bytes."""
        if not isinstance(query, FrameCaptureQuery):
            raise ValueError("frame capture query is invalid")
        if self.transfer.byte_length > query.maximum_bytes:
            raise ValueError("frame binary exceeds its request byte ceiling")
        if self.transfer.size.to_core() != expected_frame_capture_size(
            self.viewport_size.to_core(),
            query,
        ):
            raise ValueError("frame encoded size does not match the capture query")

    def to_core(
        self,
        *,
        query: FrameCaptureQuery,
        png_bytes: bytes,
    ) -> FrameCaptureResult:
        """Verify the announced binary and complete the focused core result."""
        self.validate_announcement(query=query)
        if type(png_bytes) is not bytes:
            raise ValueError("frame binary must be immutable bytes")
        if len(png_bytes) != self.transfer.byte_length:
            raise ValueError("frame binary length does not match its announcement")
        if len(png_bytes) > query.maximum_bytes:
            raise ValueError("frame binary exceeds its request byte ceiling")
        if hashlib.sha256(png_bytes).hexdigest() != self.transfer.sha256:
            raise ValueError("frame binary SHA-256 does not match its announcement")
        result = FrameCaptureResult(
            viewport_size=self.viewport_size.to_core(),
            captured_at_unix_ms=self.captured_at_unix_ms,
            encoded_size=self.transfer.size.to_core(),
            frame_revision=ObservationRevision(value=self.transfer.frame_revision),
            data=png_bytes,
        )
        validate_frame_capture_result(result, query)
        return result

    @classmethod
    def from_core(
        cls,
        value: FrameCaptureResult,
        *,
        query: FrameCaptureQuery,
        transfer_id: str,
    ) -> FrameCaptureResultValue:
        """Create one correlated announcement from verified core bytes."""
        validate_frame_capture_result(value, query)
        return cls(
            viewport_size=SizeValue.from_core(value.viewport_size),
            captured_at_unix_ms=value.captured_at_unix_ms,
            transfer=FrameTransferValue.from_core(
                value,
                transfer_id=transfer_id,
            ),
        )


class FrameCaptureRequest(ContractModel):
    """Exact JSON-RPC frame-capture request."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    method: Literal["toqraq.frame.capture"]
    params: FrameCaptureParams

    @classmethod
    def from_core(cls, *, request_id: str, query: FrameCaptureQuery) -> FrameCaptureRequest:
        """Bind one pure query to a validated request ID and method."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            method=FRAME_CAPTURE_METHOD,
            params=FrameCaptureParams.from_core(query),
        )


class FrameCaptureResponse(ContractModel):
    """Exact JSON-RPC frame-capture success response."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    result: FrameCaptureResultValue

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        value: FrameCaptureResult,
        query: FrameCaptureQuery,
        transfer_id: str,
    ) -> FrameCaptureResponse:
        """Bind one correlated core result to its transport announcement."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            result=FrameCaptureResultValue.from_core(
                value,
                query=query,
                transfer_id=transfer_id,
            ),
        )
