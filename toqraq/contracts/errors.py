"""Single public Pydantic application-error contract."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    JsonValue,
    StringConstraints,
    field_serializer,
    field_validator,
)

from ..core.error_values import (
    MAX_ERROR_DEPTH,
    MAX_ERROR_FIELDS,
    MAX_ERROR_KEY_LENGTH,
    MAX_ERROR_SAFE_INTEGER,
    MAX_ERROR_SEQUENCE_ITEMS,
    MAX_ERROR_STRING_LENGTH,
    MAX_ERROR_VALUE_NODES,
    ErrorFields,
    ErrorValue,
    freeze_error_fields,
)
from ..core.errors import ErrorCategory, ToqraqError
from ..core.session_readiness import ReadinessFailure
from ..core.trace import TraceId
from .identifiers import CanonicalUuid4Text
from .json_values import FrozenJson, FrozenJsonValue

ErrorCode = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=96,
        pattern=r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*)+$",
    ),
]


def _canonical_trace_id(value: str) -> str:
    """Retain one lowercase canonical UUID4 trace identifier."""
    return str(TraceId(value))


TraceIdValue = Annotated[
    CanonicalUuid4Text,
    AfterValidator(_canonical_trace_id),
]


class PublicError(BaseModel):
    """Safe transport representation of one application failure."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        json_schema_extra={
            "x-toqraq-error-json": {
                "maximumDepth": MAX_ERROR_DEPTH,
                "maximumFields": MAX_ERROR_FIELDS,
                "maximumKeyLength": MAX_ERROR_KEY_LENGTH,
                "maximumNodes": MAX_ERROR_VALUE_NODES,
                "maximumSafeInteger": MAX_ERROR_SAFE_INTEGER,
                "maximumSequenceItems": MAX_ERROR_SEQUENCE_ITEMS,
                "maximumStringLength": MAX_ERROR_STRING_LENGTH,
            }
        },
    )

    code: ErrorCode
    category: ErrorCategory
    parameters: Mapping[str, FrozenJsonValue]
    details: Mapping[str, FrozenJsonValue]
    trace_id: TraceIdValue

    @field_validator("parameters", "details")
    @classmethod
    def validate_safe_fields(
        cls,
        value: Mapping[str, FrozenJson],
    ) -> Mapping[str, FrozenJson]:
        """Freeze the field map after applying shared aggregate bounds."""
        core_fields: dict[str, ErrorValue] = {key: item.data for key, item in value.items()}
        freeze_error_fields(core_fields)
        return MappingProxyType(dict(value))

    @field_serializer("parameters", "details")
    def serialize_safe_fields(self, value: Mapping[str, FrozenJson]) -> dict[str, JsonValue]:
        """Return fresh JSON containers without exposing immutable storage."""
        return {key: item.to_json() for key, item in value.items()}


class ErrorEnvelope(BaseModel):
    """Only public envelope used by HTTP, Hermes tools, and Desktop."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    error: PublicError


def error_envelope(error: ToqraqError) -> ErrorEnvelope:
    """Convert a core application failure to its sole public contract.

    Args:
        error: Structured internal failure.

    Returns:
        Strict public Pydantic envelope.
    """
    return ErrorEnvelope(error=public_error(error))


def public_error(error: ToqraqError | ReadinessFailure) -> PublicError:
    """Copy the safe facts shared by live failures and readiness snapshots."""
    if not isinstance(error, ToqraqError | ReadinessFailure):
        raise TypeError("public error source is invalid")
    return PublicError(
        code=error.code,
        category=error.category,
        parameters=_frozen_fields(error.parameters),
        details=_frozen_fields(error.details),
        trace_id=str(error.trace_id),
    )


def _frozen_fields(fields: ErrorFields) -> Mapping[str, FrozenJson]:
    """Wrap already-owned core values without thawing mutable containers."""
    return MappingProxyType({key: FrozenJson(value) for key, value in fields.items()})
