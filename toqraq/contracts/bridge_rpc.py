"""Strict post-authentication JSON-RPC envelopes and notifications."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

from ..core.errors import ErrorCategory
from .base import ContractModel, freeze_sequence
from .errors import PublicError
from .identifiers import MAX_JSON_INTEGER

BRIDGE_REMOTE_INTERNAL_CODE = "bridge.remote_internal"
MAX_BRIDGE_HOST_REQUEST_ID_CHARACTERS = len(f"host-{MAX_JSON_INTEGER}")
_STANDARD_OPERATION_ERRORS = {
    -32601: ("bridge.method_not_found", ErrorCategory.INVALID),
    -32602: ("bridge.params_invalid", ErrorCategory.INVALID),
    -32603: (BRIDGE_REMOTE_INTERNAL_CODE, ErrorCategory.INTERNAL),
    -32800: ("request.cancelled", ErrorCategory.CONFLICT),
}
_RESERVED_OPERATION_DATA_CODES = frozenset(
    code for code, _category in _STANDARD_OPERATION_ERRORS.values()
)

BridgeOperationRpcCode: TypeAlias = Literal[-32601, -32602, -32603, -32000, -32800]
BridgeStateFamily: TypeAlias = Literal[
    "hierarchy",
    "objects",
    "diagnostics",
    "metrics",
    "frame",
    "simulation",
]
BRIDGE_STATE_FAMILY_ORDER: tuple[BridgeStateFamily, ...] = (
    "hierarchy",
    "objects",
    "diagnostics",
    "metrics",
    "frame",
    "simulation",
)


def _validate_host_request_id(value: str) -> str:
    """Require a positive monotonically representable host sequence value."""
    if int(value.removeprefix("host-")) > MAX_JSON_INTEGER:
        raise ValueError("bridge host request ID exceeds the exact integer range")
    return value


BridgeHostRequestId: TypeAlias = Annotated[
    str,
    StringConstraints(
        min_length=6,
        max_length=MAX_BRIDGE_HOST_REQUEST_ID_CHARACTERS,
        pattern=r"^host-[1-9][0-9]*$",
    ),
    AfterValidator(_validate_host_request_id),
]


def _unique_families(values: tuple[str, ...]) -> tuple[str, ...]:
    """Reject redundant invalidations instead of silently normalizing them."""
    if len(set(values)) != len(values):
        raise ValueError("bridge state families must be unique")
    return values


BridgeStateFamilies: TypeAlias = Annotated[
    tuple[BridgeStateFamily, ...],
    BeforeValidator(freeze_sequence),
    Field(min_length=1, max_length=6),
    AfterValidator(_unique_families),
]


class BridgeRpcSuccessEnvelope(ContractModel):
    """Bounded generic header used before one expected result is decoded."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    result: JsonValue


class BridgePublicError(PublicError):
    """Shared public error with exact JSON-to-enum boundary conversion."""

    @field_validator("category", mode="before")
    @classmethod
    def decode_category(cls, value: object) -> ErrorCategory:
        """Convert one JSON string immediately to the strict core enum."""
        if not isinstance(value, str):
            raise ValueError("bridge public error category is invalid")
        try:
            return ErrorCategory(value)
        except ValueError:
            raise ValueError("bridge public error category is invalid") from None


class BridgeRpcOperationErrorValue(ContractModel):
    """Exact operational error number with safe shared application data."""

    code: BridgeOperationRpcCode
    message: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    data: BridgePublicError

    @model_validator(mode="after")
    def validate_rpc_semantics(self) -> BridgeRpcOperationErrorValue:
        """Tie the JSON-RPC number to one unambiguous data classification."""
        standard = _STANDARD_OPERATION_ERRORS.get(self.code)
        if standard is not None:
            expected_code, expected_category = standard
            if self.data.code != expected_code or self.data.category is not expected_category:
                raise ValueError("bridge operation error semantics are inconsistent")
            if self.code == -32800 and (self.data.parameters or self.data.details):
                raise ValueError("bridge cancellation error must not contain fields")
            return self
        if (
            self.data.category is ErrorCategory.INTERNAL
            or self.data.code in _RESERVED_OPERATION_DATA_CODES
        ):
            raise ValueError("bridge application error semantics are inconsistent")
        return self


class BridgeRpcOperationErrorEnvelope(ContractModel):
    """Only post-authentication error response accepted from an engine."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    error: BridgeRpcOperationErrorValue


class BridgeStateChangedParams(ContractModel):
    """Authoritative observation families invalidated by the engine."""

    families: BridgeStateFamilies


class BridgeStateChangedNotification(ContractModel):
    """Only engine-to-host notification accepted by the common protocol."""

    jsonrpc: Literal["2.0"]
    method: Literal["toqraq.state.changed"]
    params: BridgeStateChangedParams
