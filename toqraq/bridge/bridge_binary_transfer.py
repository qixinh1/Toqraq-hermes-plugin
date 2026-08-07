"""Single pending binary-message ownership for controlled Bridge RPC."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from ..contracts.base import ContractModel
from ..contracts.bridge_rpc import BridgeRpcSuccessEnvelope
from ..core.bridge import MAX_BRIDGE_BINARY_TRANSFER_BYTES, MAX_BRIDGE_TEXT_MESSAGE_BYTES
from ..core.errors import ProtocolError

BRIDGE_BINARY_TRANSFER_ID_BYTES = 16
MAX_BRIDGE_BINARY_FRAME_BYTES = MAX_BRIDGE_BINARY_TRANSFER_BYTES + BRIDGE_BINARY_TRANSFER_ID_BYTES
BridgeBinaryConsumer: TypeAlias = Callable[[bytes], None]


class BridgeBinaryProtocolReason(StrEnum):
    """Safe closed reasons for rejecting a post-announcement message."""

    WITHOUT_ANNOUNCEMENT = "binary_without_announcement"
    TEXT_INTERLEAVED = "binary_text_interleaved"
    ANNOUNCEMENT_INVALID = "binary_announcement_invalid"
    FRAME_INVALID = "binary_frame_invalid"
    DEADLINE = "binary_transfer_deadline"
    CALLER_CANCELLED = "binary_transfer_cancelled"


@dataclass(frozen=True, slots=True, kw_only=True)
class BridgeBinaryAnnouncement:
    """One exact next-message claim produced by a focused response decoder."""

    response: ContractModel
    transfer_id: bytes
    byte_length: int
    maximum_payload_bytes: int
    consume: BridgeBinaryConsumer

    def __post_init__(self) -> None:
        """Reject a transfer claim that cannot be bounded before publication."""
        if not isinstance(self.response, ContractModel):
            raise TypeError("bridge binary response is invalid")
        if type(self.transfer_id) is not bytes or len(self.transfer_id) != (
            BRIDGE_BINARY_TRANSFER_ID_BYTES
        ):
            raise ValueError("bridge binary transfer ID is invalid")
        for value in (self.byte_length, self.maximum_payload_bytes):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 1 <= value <= MAX_BRIDGE_BINARY_TRANSFER_BYTES
            ):
                raise ValueError("bridge binary transfer bound is invalid")
        if not callable(self.consume):
            raise TypeError("bridge binary consumer is invalid")


BridgeBinaryAnnouncementDecoder: TypeAlias = Callable[
    [BridgeRpcSuccessEnvelope], BridgeBinaryAnnouncement
]


@dataclass(frozen=True, slots=True, kw_only=True)
class _PendingBinaryTransfer:
    """Internal ownership tying one host request to its next binary message."""

    request_id: str
    announcement: BridgeBinaryAnnouncement


class BridgeBinaryTransferOwner:
    """Own and consume at most one immediately following binary message."""

    def __init__(self, *, negotiated_maximum_bytes: int) -> None:
        """Create an empty owner under the accepted connection byte ceiling."""
        if (
            isinstance(negotiated_maximum_bytes, bool)
            or not isinstance(negotiated_maximum_bytes, int)
            or not 1 <= negotiated_maximum_bytes <= MAX_BRIDGE_BINARY_TRANSFER_BYTES
        ):
            raise ValueError("negotiated bridge binary limit is invalid")
        self._negotiated_maximum_bytes = negotiated_maximum_bytes
        self._pending: _PendingBinaryTransfer | None = None

    @property
    def active(self) -> bool:
        """Report whether the next inbound message belongs to a transfer."""
        return self._pending is not None

    def owns(self, request_id: str) -> bool:
        """Report whether one request currently owns the next-message slot."""
        pending = self._pending
        return pending is not None and pending.request_id == request_id

    def expect(self, request_id: str, announcement: BridgeBinaryAnnouncement) -> None:
        """Publish one validated announcement as the sole next-message owner."""
        if self._pending is not None:
            raise binary_protocol_error(BridgeBinaryProtocolReason.TEXT_INTERLEAVED)
        if not isinstance(announcement, BridgeBinaryAnnouncement):
            raise binary_protocol_error(BridgeBinaryProtocolReason.ANNOUNCEMENT_INVALID)
        if announcement.byte_length > min(
            self._negotiated_maximum_bytes,
            announcement.maximum_payload_bytes,
        ):
            raise binary_protocol_error(BridgeBinaryProtocolReason.ANNOUNCEMENT_INVALID)
        self._pending = _PendingBinaryTransfer(
            request_id=request_id,
            announcement=announcement,
        )

    def consume(self, frame: bytes) -> tuple[str, ContractModel]:
        """Consume the exact next binary message and transfer its payload once."""
        pending = self._pending
        self._pending = None
        if pending is None:
            raise binary_protocol_error(BridgeBinaryProtocolReason.WITHOUT_ANNOUNCEMENT)
        if type(frame) is not bytes:
            raise binary_protocol_error(BridgeBinaryProtocolReason.FRAME_INVALID)
        announcement = pending.announcement
        expected_length = BRIDGE_BINARY_TRANSFER_ID_BYTES + announcement.byte_length
        if (
            len(frame) != expected_length
            or frame[:BRIDGE_BINARY_TRANSFER_ID_BYTES] != announcement.transfer_id
        ):
            raise binary_protocol_error(BridgeBinaryProtocolReason.FRAME_INVALID)
        payload = frame[BRIDGE_BINARY_TRANSFER_ID_BYTES:]
        try:
            announcement.consume(payload)
        except Exception:
            raise binary_protocol_error(BridgeBinaryProtocolReason.FRAME_INVALID) from None
        return pending.request_id, announcement.response

    def clear(self) -> None:
        """Discard an unconsumed announcement during fail-closed teardown."""
        self._pending = None


def binary_protocol_error(reason: BridgeBinaryProtocolReason) -> ProtocolError:
    """Create one safe binary failure without retaining announcement or bytes."""
    return ProtocolError(details={"reason": reason.value})


def bridge_transport_message_limit(
    *,
    maximum_text_bytes: int,
    maximum_binary_bytes: int,
) -> int:
    """Bound a shared WebSocket message ceiling for independent payload limits."""
    if (
        isinstance(maximum_text_bytes, bool)
        or not isinstance(maximum_text_bytes, int)
        or not 1 <= maximum_text_bytes <= MAX_BRIDGE_TEXT_MESSAGE_BYTES
    ):
        raise ValueError("bridge text-message limit is invalid")
    if (
        isinstance(maximum_binary_bytes, bool)
        or not isinstance(maximum_binary_bytes, int)
        or not 1 <= maximum_binary_bytes <= MAX_BRIDGE_BINARY_TRANSFER_BYTES
    ):
        raise ValueError("bridge binary-transfer limit is invalid")
    binary_frame_bytes = maximum_binary_bytes + BRIDGE_BINARY_TRANSFER_ID_BYTES
    if binary_frame_bytes > MAX_BRIDGE_BINARY_FRAME_BYTES:
        raise ValueError("bridge binary-frame limit is invalid")
    return max(maximum_text_bytes, binary_frame_bytes)
