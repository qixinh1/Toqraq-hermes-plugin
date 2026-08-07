"""Exact post-authentication engine-bridge text decoding."""

from __future__ import annotations

from enum import StrEnum
from typing import TypeVar

from pydantic import ValidationError

from ..contracts.base import ContractModel
from ..contracts.bridge_codec import decode_bridge_json
from ..contracts.bridge_rpc import (
    BridgeRpcOperationErrorEnvelope,
    BridgeRpcSuccessEnvelope,
    BridgeStateChangedNotification,
)
from ..core.bridge_errors import BridgeWireError
from ..core.errors import ProtocolError

BridgeRpcEnvelope = (
    BridgeRpcSuccessEnvelope | BridgeRpcOperationErrorEnvelope | BridgeStateChangedNotification
)
ResponseContractT = TypeVar("ResponseContractT", bound=ContractModel)


class BridgeRpcProtocolReason(StrEnum):
    """Safe closed reasons for rejecting one post-authentication frame."""

    INVALID_MESSAGE = "invalid_rpc_message"
    INVALID_RESPONSE = "invalid_rpc_response"
    UNKNOWN_RESPONSE_ID = "unknown_rpc_response_id"


def decode_bridge_rpc_message(
    message: str,
    *,
    maximum_bytes: int,
) -> BridgeRpcEnvelope:
    """Decode one text frame into the only accepted envelope families."""
    try:
        decoded = decode_bridge_json(message, maximum_bytes=maximum_bytes)
    except BridgeWireError:
        raise _protocol_failure(BridgeRpcProtocolReason.INVALID_MESSAGE) from None
    if not isinstance(decoded, dict):
        raise _protocol_failure(BridgeRpcProtocolReason.INVALID_MESSAGE)

    model: type[BridgeRpcEnvelope]
    if "id" in decoded and "result" in decoded:
        model = BridgeRpcSuccessEnvelope
    elif "id" in decoded and "error" in decoded:
        model = BridgeRpcOperationErrorEnvelope
    elif "id" not in decoded and "method" in decoded:
        model = BridgeStateChangedNotification
    else:
        raise _protocol_failure(BridgeRpcProtocolReason.INVALID_MESSAGE)
    try:
        return model.model_validate(decoded)
    except ValidationError:
        raise _protocol_failure(BridgeRpcProtocolReason.INVALID_MESSAGE) from None


def decode_expected_success(
    envelope: BridgeRpcSuccessEnvelope,
    response_model: type[ResponseContractT],
) -> ResponseContractT:
    """Convert a generic success immediately to its registered exact response."""
    if not isinstance(response_model, type) or not issubclass(response_model, ContractModel):
        raise TypeError("bridge response contract is invalid")
    try:
        return response_model.model_validate(envelope.model_dump(mode="python"))
    except ValidationError:
        raise _protocol_failure(BridgeRpcProtocolReason.INVALID_RESPONSE) from None


def encode_bridge_rpc_request(
    request: ContractModel,
    *,
    request_id: str,
    maximum_bytes: int,
) -> str:
    """Serialize one exact host-owned request within its negotiated text bound."""
    if not isinstance(request, ContractModel) or getattr(request, "id", None) != request_id:
        raise TypeError("bridge request factory returned an invalid contract")
    if isinstance(maximum_bytes, bool) or not isinstance(maximum_bytes, int):
        raise ValueError("bridge request byte limit is invalid")
    payload = request.model_dump_json()
    if len(payload.encode("utf-8")) > maximum_bytes:
        raise ProtocolError(details={"reason": "outbound_message_too_large"})
    return payload


def unknown_response_error() -> ProtocolError:
    """Create the stable failure for an unknown, duplicate, or late ID."""
    return _protocol_failure(BridgeRpcProtocolReason.UNKNOWN_RESPONSE_ID)


def _protocol_failure(reason: BridgeRpcProtocolReason) -> ProtocolError:
    """Create one safe failure without retaining a decoded frame or validation error."""
    return ProtocolError(details={"reason": reason.value})
