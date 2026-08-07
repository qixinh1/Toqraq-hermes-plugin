"""Strict JSON-RPC contract for same-connection request cancellation."""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import model_validator

from ..core.bridge import BridgeRequestReference
from ..core.request_cancellation import (
    CancellationAcknowledgement,
    CancellationDisposition,
    CancelRequestCommand,
)
from .base import ContractModel
from .bridge import JSON_RPC_VERSION
from .bridge_rpc import BridgeHostRequestId

REQUEST_CANCEL_METHOD: Literal["toqraq.request.cancel"] = "toqraq.request.cancel"
CancellationDispositionValue: TypeAlias = Literal[
    "requested",
    "already_terminal",
    "not_found",
]


class RequestCancelParams(ContractModel):
    """Reference to one request owned by the same authenticated connection."""

    target_request_id: BridgeHostRequestId

    def to_core(self) -> CancelRequestCommand:
        """Convert one strict target to the pure cancellation command."""
        return CancelRequestCommand(
            target=BridgeRequestReference(value=self.target_request_id),
        )

    @classmethod
    def from_core(cls, value: CancelRequestCommand) -> RequestCancelParams:
        """Create canonical params from one validated pure command."""
        return cls(target_request_id=value.target.value)


class RequestCancelResult(ContractModel):
    """Idempotent disposition for the request-bound cancellation target."""

    disposition: CancellationDispositionValue

    def to_core(self) -> CancellationAcknowledgement:
        """Convert one strict request-bound result to its pure value."""
        return CancellationAcknowledgement(disposition=CancellationDisposition(self.disposition))

    @classmethod
    def from_core(cls, value: CancellationAcknowledgement) -> RequestCancelResult:
        """Create one exact request-bound result from core."""
        return cls(disposition=value.disposition.value)


class RequestCancelRequest(ContractModel):
    """Exact JSON-RPC cancellation request with its own identity."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    method: Literal["toqraq.request.cancel"]
    params: RequestCancelParams

    @model_validator(mode="after")
    def validate_distinct_target(self) -> RequestCancelRequest:
        """Prevent one cancellation operation from targeting itself."""
        if self.id == self.params.target_request_id:
            raise ValueError("cancellation request ID must differ from its target")
        return self

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        command: CancelRequestCommand,
    ) -> RequestCancelRequest:
        """Bind one cancellation command to a distinct request identity."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            method=REQUEST_CANCEL_METHOD,
            params=RequestCancelParams.from_core(command),
        )


class RequestCancelResponse(ContractModel):
    """Exact JSON-RPC cancellation acknowledgement response."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    result: RequestCancelResult

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        value: CancellationAcknowledgement,
    ) -> RequestCancelResponse:
        """Bind one request-owned acknowledgement to its identity."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            result=RequestCancelResult.from_core(value),
        )
