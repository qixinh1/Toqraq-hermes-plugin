"""Public JSON result for one complete verified runtime frame."""

from __future__ import annotations

import base64
import binascii
import hashlib
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from ..core.bridge import MAX_BRIDGE_BINARY_TRANSFER_BYTES
from ..core.frame_capture import (
    FRAME_PNG_MIME_TYPE,
    FrameCaptureQuery,
    validate_frame_capture_result,
)
from ..core.frame_capture import (
    FrameCaptureResult as CoreFrameCaptureResult,
)
from ..core.observation import ObservationRevision
from .base import ContractModel
from .bridge_frame import FrameCaptureSizeValue
from .bridge_observation import ObservationRevisionValue, ObservationUnixMilliseconds
from .identifiers import Sha256Value

MAX_FRAME_PNG_BASE64_CHARACTERS = 4 * ((MAX_BRIDGE_BINARY_TRANSFER_BYTES + 2) // 3)


def _validate_png_base64(value: str) -> str:
    """Require canonical padded base64 whose decoded value fits the Bridge ceiling."""
    try:
        encoded = value.encode("ascii")
        decoded = base64.b64decode(encoded, validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise ValueError("frame PNG base64 is invalid") from exc
    if not 1 <= len(decoded) <= MAX_BRIDGE_BINARY_TRANSFER_BYTES:
        raise ValueError("frame PNG base64 length is invalid")
    if base64.b64encode(decoded) != encoded:
        raise ValueError("frame PNG base64 is not canonical")
    return value


FramePngBase64 = Annotated[
    str,
    StringConstraints(min_length=4, max_length=MAX_FRAME_PNG_BASE64_CHARACTERS),
    AfterValidator(_validate_png_base64),
]


class FrameCaptureResult(ContractModel):
    """JSON-safe complete PNG without Bridge transfer or socket identity."""

    viewport_size: FrameCaptureSizeValue
    captured_at_unix_ms: ObservationUnixMilliseconds
    encoded_size: FrameCaptureSizeValue
    frame_revision: ObservationRevisionValue
    mime_type: Literal["image/png"]
    byte_length: int = Field(ge=1, le=MAX_BRIDGE_BINARY_TRANSFER_BYTES)
    sha256: Sha256Value
    png_base64: FramePngBase64

    @model_validator(mode="after")
    def validate_png_facts(self) -> FrameCaptureResult:
        """Correlate the JSON metadata with the complete decoded PNG bytes."""
        data = _decode_png(self.png_base64)
        if len(data) != self.byte_length:
            raise ValueError("frame PNG length does not match its metadata")
        if hashlib.sha256(data).hexdigest() != self.sha256:
            raise ValueError("frame PNG SHA-256 does not match its metadata")
        return self

    def to_core(self, *, query: FrameCaptureQuery) -> CoreFrameCaptureResult:
        """Decode and correlate this public value with its exact capture request."""
        result = CoreFrameCaptureResult(
            viewport_size=self.viewport_size.to_core(),
            captured_at_unix_ms=self.captured_at_unix_ms,
            encoded_size=self.encoded_size.to_core(),
            frame_revision=ObservationRevision(value=self.frame_revision),
            data=_decode_png(self.png_base64),
        )
        validate_frame_capture_result(result, query)
        return result

    @classmethod
    def from_core(
        cls,
        value: CoreFrameCaptureResult,
        *,
        query: FrameCaptureQuery,
    ) -> FrameCaptureResult:
        """Create the public JSON value only after request correlation succeeds."""
        validate_frame_capture_result(value, query)
        return cls(
            viewport_size=FrameCaptureSizeValue.from_core(value.viewport_size),
            captured_at_unix_ms=value.captured_at_unix_ms,
            encoded_size=FrameCaptureSizeValue.from_core(value.encoded_size),
            frame_revision=value.frame_revision.value,
            mime_type=FRAME_PNG_MIME_TYPE,
            byte_length=value.byte_length,
            sha256=hashlib.sha256(value.data).hexdigest(),
            png_base64=base64.b64encode(value.data).decode("ascii"),
        )


def _decode_png(value: str) -> bytes:
    """Decode a value already admitted by the canonical base64 validator."""
    return base64.b64decode(value.encode("ascii"), validate=True)
