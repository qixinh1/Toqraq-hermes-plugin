"""Response correlation and next-binary dispatch for one Bridge connection."""

from __future__ import annotations

from ..contracts.base import ContractModel
from ..contracts.bridge_rpc import (
    BRIDGE_STATE_FAMILY_ORDER,
    BridgeRpcOperationErrorEnvelope,
    BridgeRpcSuccessEnvelope,
    BridgeStateChangedNotification,
    BridgeStateFamily,
)
from ..core.errors import (
    APPLICATION_ERROR_TYPES,
    ProtocolError,
    RequestCancelledError,
    ToqraqError,
)
from .bridge_binary_transfer import (
    BridgeBinaryAnnouncement,
    BridgeBinaryProtocolReason,
    BridgeBinaryTransferOwner,
    binary_protocol_error,
)
from .bridge_remote_error import BridgeRemoteError
from .bridge_rpc_codec import unknown_response_error
from .bridge_rpc_registry import BridgeRequestRegistry
from .bridge_rpc_state import (
    BridgeRemoteErrorMapper,
    BridgeResponseDecoder,
    PendingBridgeRequest,
)


class BridgeRpcDispatcher:
    """Own exact response promotion, invalidations, and one binary claim."""

    def __init__(
        self,
        *,
        registry: BridgeRequestRegistry,
        maximum_binary_bytes: int,
    ) -> None:
        """Bind correlation state to the connection's sole request registry."""
        if not isinstance(registry, BridgeRequestRegistry):
            raise TypeError("bridge request registry is invalid")
        self._registry = registry
        self._binary = BridgeBinaryTransferOwner(
            negotiated_maximum_bytes=maximum_binary_bytes,
        )
        self._dirty_families: set[BridgeStateFamily] = set()

    def dispatch_text(
        self,
        envelope: (
            BridgeRpcSuccessEnvelope
            | BridgeRpcOperationErrorEnvelope
            | BridgeStateChangedNotification
        ),
    ) -> None:
        """Correlate one exact text envelope or fail before changing ownership."""
        if self._binary.active:
            raise binary_protocol_error(BridgeBinaryProtocolReason.TEXT_INTERLEAVED)
        if isinstance(envelope, BridgeStateChangedNotification):
            self._dirty_families.update(envelope.params.families)
            return
        pending = self._registry.find(envelope.id)
        if pending is None:
            raise unknown_response_error()
        if isinstance(envelope, BridgeRpcOperationErrorEnvelope):
            self._dispatch_remote_error(pending, envelope)
            return
        if pending.decoder is not None:
            response = self._decode_response(pending.decoder, envelope)
            self._registry.complete(pending, result=response)
            return
        decoder = pending.binary_decoder
        if decoder is None:
            raise ProtocolError(details={"reason": "missing_rpc_response_decoder"})
        try:
            announcement = decoder(envelope)
        except ProtocolError:
            raise
        except Exception:
            raise ProtocolError(details={"reason": "invalid_rpc_response"}) from None
        if not isinstance(announcement, BridgeBinaryAnnouncement):
            raise ProtocolError(details={"reason": "invalid_rpc_response"})
        if pending.cancel_task is not None:
            raise binary_protocol_error(BridgeBinaryProtocolReason.CALLER_CANCELLED)
        self._binary.expect(pending.request_id, announcement)

    def dispatch_binary(self, frame: bytes) -> None:
        """Consume one announced frame and complete its retained request owner."""
        request_id, response = self._binary.consume(frame)
        pending = self._registry.find(request_id)
        if pending is None:
            raise unknown_response_error()
        self._registry.complete(pending, result=response)

    def take_state_changes(self) -> tuple[BridgeStateFamily, ...]:
        """Return and clear one canonical merged dirty-family snapshot."""
        values = tuple(
            family for family in BRIDGE_STATE_FAMILY_ORDER if family in self._dirty_families
        )
        self._dirty_families.clear()
        return values

    def binary_owned_by(self, request_id: str) -> bool:
        """Report whether one work request awaits its immediate binary message."""
        return self._binary.owns(request_id)

    def clear_binary(self) -> None:
        """Discard any pending announcement during connection teardown."""
        self._binary.clear()

    def _dispatch_remote_error(
        self,
        pending: PendingBridgeRequest,
        envelope: BridgeRpcOperationErrorEnvelope,
    ) -> None:
        """Apply one request-owned mapper without trusting dynamic exception types."""
        mapper: BridgeRemoteErrorMapper = pending.map_remote_error
        if not callable(mapper):
            raise ProtocolError(details={"reason": "invalid_remote_error_mapping"})
        remote = BridgeRemoteError(
            rpc_code=envelope.error.code,
            remote=envelope.error.data,
        )
        if remote.rpc_code == -32800:
            if pending.cancel_task is None:
                raise ProtocolError(details={"reason": "unexpected_request_cancellation"})
            self._registry.complete(
                pending,
                error=RequestCancelledError(
                    cause=remote,
                    trace_id=remote.local_trace_id,
                ),
            )
            return
        try:
            mapped = mapper(remote)
        except ProtocolError:
            raise
        except Exception:
            raise ProtocolError(details={"reason": "invalid_remote_error_mapping"}) from None
        if isinstance(mapped, ProtocolError):
            raise mapped
        if not isinstance(mapped, ToqraqError) or type(mapped) not in APPLICATION_ERROR_TYPES:
            raise ProtocolError(details={"reason": "invalid_remote_error_mapping"})
        self._registry.complete(pending, error=mapped)

    @staticmethod
    def _decode_response(
        decoder: BridgeResponseDecoder,
        envelope: BridgeRpcSuccessEnvelope,
    ) -> ContractModel:
        """Run one exact operation decoder and require its boundary model result."""
        if not callable(decoder):
            raise ProtocolError(details={"reason": "missing_rpc_response_decoder"})
        try:
            response = decoder(envelope)
        except ProtocolError:
            raise
        except Exception:
            raise ProtocolError(details={"reason": "invalid_rpc_response"}) from None
        if not isinstance(response, ContractModel):
            raise ProtocolError(details={"reason": "invalid_rpc_response"})
        return response
