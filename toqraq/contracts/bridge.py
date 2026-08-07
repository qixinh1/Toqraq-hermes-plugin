"""Strict JSON-RPC contracts for the authenticated engine handshake."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal, TypeAlias, cast

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    JsonValue,
    StringConstraints,
)

from ..core.bridge import (
    BRIDGE_CREDENTIAL_HEX_CHARACTERS,
    MAX_BRIDGE_BINARY_TRANSFER_BYTES,
    MAX_BRIDGE_CAPABILITIES,
    MAX_BRIDGE_IN_FLIGHT_REQUESTS,
    MAX_BRIDGE_REQUEST_ID_CHARACTERS,
    MAX_BRIDGE_RUN_REVISION,
    MAX_BRIDGE_SESSION_ID_BYTES,
    MAX_BRIDGE_TEXT_MESSAGE_BYTES,
    MIN_BRIDGE_TEXT_MESSAGE_BYTES,
    BridgeHandshakeAcceptance,
    BridgeHandshakeOffer,
    BridgeLimits,
    BridgeOwnerKey,
    validate_bridge_request_id,
    validate_bridge_session_id,
)
from ..core.bridge_errors import BridgeWireError
from ..core.runtime import RuntimeIdentity
from .base import ContractModel, freeze_sequence
from .errors import PublicError, error_envelope
from .identifiers import CapabilityId, PlatformId

JSON_RPC_VERSION: Literal["2.0"] = "2.0"
BRIDGE_HANDSHAKE_METHOD: Literal["toqraq.handshake"] = "toqraq.handshake"
MAX_BRIDGE_PARAMETER_FIELDS = 32

BridgeRequestId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=MAX_BRIDGE_REQUEST_ID_CHARACTERS,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
    AfterValidator(validate_bridge_request_id),
]
BridgeCredential = Annotated[
    str,
    StringConstraints(
        min_length=BRIDGE_CREDENTIAL_HEX_CHARACTERS,
        max_length=BRIDGE_CREDENTIAL_HEX_CHARACTERS,
        pattern=r"^[0-9a-f]{64}$",
    ),
]
BridgeSessionId = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_BRIDGE_SESSION_ID_BYTES),
    AfterValidator(validate_bridge_session_id),
]
BridgeOpaqueId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]*$",
    ),
]
BridgeSymbolicId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
    ),
]


def _unique_capabilities(values: tuple[str, ...]) -> tuple[str, ...]:
    """Reject duplicate capabilities at their single declared type boundary."""
    if len(set(values)) != len(values):
        raise ValueError("bridge capabilities must be unique")
    return values


BridgeCapabilities: TypeAlias = Annotated[
    tuple[CapabilityId, ...],
    BeforeValidator(freeze_sequence),
    Field(max_length=MAX_BRIDGE_CAPABILITIES),
    AfterValidator(_unique_capabilities),
]
BridgeRpcErrorCode: TypeAlias = Literal[-32700, -32600, -32601, -32602, -32001, -32002]


class BridgeLimitsValue(ContractModel):
    """Exact peer or effective limits exchanged during authentication."""

    max_text_message_bytes: int = Field(
        ge=MIN_BRIDGE_TEXT_MESSAGE_BYTES,
        le=MAX_BRIDGE_TEXT_MESSAGE_BYTES,
    )
    max_binary_transfer_bytes: int = Field(ge=1, le=MAX_BRIDGE_BINARY_TRANSFER_BYTES)
    max_in_flight_requests: int = Field(ge=1, le=MAX_BRIDGE_IN_FLIGHT_REQUESTS)

    def to_core(self) -> BridgeLimits:
        """Convert one validated wire value to the pure core limit value."""
        return BridgeLimits(
            max_text_message_bytes=self.max_text_message_bytes,
            max_binary_transfer_bytes=self.max_binary_transfer_bytes,
            max_in_flight_requests=self.max_in_flight_requests,
        )

    @classmethod
    def from_core(cls, value: BridgeLimits) -> BridgeLimitsValue:
        """Create the exact response contract from negotiated core limits."""
        return cls(
            max_text_message_bytes=value.max_text_message_bytes,
            max_binary_transfer_bytes=value.max_binary_transfer_bytes,
            max_in_flight_requests=value.max_in_flight_requests,
        )


class BridgeHandshakeParams(ContractModel):
    """Complete first-message identity offered by an engine process."""

    credential: BridgeCredential = Field(repr=False)
    session_id: BridgeSessionId
    run_revision: int = Field(gt=0, le=MAX_BRIDGE_RUN_REVISION)
    engine_id: BridgeSymbolicId
    engine_version: BridgeOpaqueId
    build_id: BridgeOpaqueId
    distribution_id: BridgeSymbolicId
    platform: PlatformId
    architecture: PlatformId
    bridge_id: CapabilityId
    protocol: BridgeOpaqueId
    capabilities: BridgeCapabilities
    limits: BridgeLimitsValue

    def to_core(self) -> BridgeHandshakeOffer:
        """Convert untrusted boundary data to its immutable core offer."""
        return BridgeHandshakeOffer(
            credential=self.credential,
            owner=BridgeOwnerKey(
                session_id=self.session_id,
                run_revision=self.run_revision,
            ),
            runtime_identity=RuntimeIdentity(
                engine_id=self.engine_id,
                version=self.engine_version,
                build_id=self.build_id,
                distribution_id=self.distribution_id,
                platform=self.platform,
                architecture=self.architecture,
            ),
            bridge_id=self.bridge_id,
            protocol=self.protocol,
            capability_ids=frozenset(self.capabilities),
            limits=self.limits.to_core(),
        )


class BridgeHandshakeRequest(ContractModel):
    """Only JSON-RPC request accepted as the first application message."""

    jsonrpc: Literal["2.0"]
    id: BridgeRequestId
    method: Literal["toqraq.handshake"]
    params: BridgeHandshakeParams


class BridgeOwnerValue(ContractModel):
    """Accepted session and internal run revision returned to the peer."""

    session_id: BridgeSessionId
    run_revision: int = Field(gt=0, le=MAX_BRIDGE_RUN_REVISION)


class BridgeHandshakeResult(ContractModel):
    """Successful authentication result without the consumed credential."""

    owner: BridgeOwnerValue
    protocol: BridgeOpaqueId
    capabilities: BridgeCapabilities
    limits: BridgeLimitsValue

    @classmethod
    def from_core(cls, value: BridgeHandshakeAcceptance) -> BridgeHandshakeResult:
        """Create a canonical result from one authenticated core value."""
        return cls(
            owner=BridgeOwnerValue(
                session_id=value.owner.session_id,
                run_revision=value.owner.run_revision,
            ),
            protocol=value.protocol,
            capabilities=tuple(sorted(value.capability_ids)),
            limits=BridgeLimitsValue.from_core(value.limits),
        )


class BridgeHandshakeResponse(ContractModel):
    """JSON-RPC success response for one exact handshake request."""

    jsonrpc: Literal["2.0"]
    id: BridgeRequestId
    result: BridgeHandshakeResult

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        value: BridgeHandshakeAcceptance,
    ) -> BridgeHandshakeResponse:
        """Bind the accepted value to its validated request identifier."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            result=BridgeHandshakeResult.from_core(value),
        )


class BridgeRpcErrorValue(ContractModel):
    """JSON-RPC number, technical message, and shared safe error data."""

    code: BridgeRpcErrorCode
    message: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    data: PublicError


class BridgeErrorResponse(ContractModel):
    """Exact JSON-RPC failure response emitted by the bridge boundary."""

    jsonrpc: Literal["2.0"]
    id: BridgeRequestId | None
    error: BridgeRpcErrorValue


class JsonRpcRequestEnvelope(ContractModel):
    """Bounded generic request header decoded before method dispatch."""

    jsonrpc: Literal["2.0"]
    id: BridgeRequestId
    method: CapabilityId
    params: Annotated[dict[str, JsonValue], Field(max_length=MAX_BRIDGE_PARAMETER_FIELDS)]


_ERROR_MESSAGES: Mapping[str, str] = MappingProxyType(
    {
        "bridge.json_invalid": "Parse error",
        "bridge.request_invalid": "Invalid Request",
        "bridge.method_not_found": "Method not found",
        "bridge.params_invalid": "Invalid params",
        "bridge.handshake_mismatch": "Handshake mismatch",
        "bridge.message_too_large": "Message too large",
    }
)


def bridge_error_response(
    error: BridgeWireError,
    *,
    request_id: str | None,
) -> BridgeErrorResponse:
    """Translate one stable pure failure to the exact JSON-RPC error contract."""
    message = _ERROR_MESSAGES.get(error.code)
    if message is None:
        raise ValueError("bridge wire error type is not registered")
    return BridgeErrorResponse(
        jsonrpc=JSON_RPC_VERSION,
        id=request_id,
        error=BridgeRpcErrorValue(
            code=cast(BridgeRpcErrorCode, error.rpc_code),
            message=message,
            data=error_envelope(error).error,
        ),
    )
