"""Focused verified frame capture over one controlled Bridge connection."""

from __future__ import annotations

from ...contracts.bridge_frame import FrameCaptureRequest, FrameCaptureResponse
from ...contracts.bridge_rpc import BridgeRpcSuccessEnvelope
from ...core.frame_capture import FrameCaptureQuery, FrameCaptureResult
from ..bridge_binary_transfer import BridgeBinaryAnnouncement
from ..bridge_rpc_codec import decode_expected_success
from ..bridge_rpc_connection import BridgeRpcConnection
from .remote_errors import map_frame_remote_error


class BridgeFrameCapture:
    """Complete frame capture only after one exact verified binary message."""

    __slots__ = ("_connection",)

    def __init__(self, connection: BridgeRpcConnection) -> None:
        """Bind the capture port to one authenticated controlled connection."""
        if not isinstance(connection, BridgeRpcConnection):
            raise TypeError("controlled Bridge connection is invalid")
        self._connection = connection

    async def capture(self, query: FrameCaptureQuery) -> FrameCaptureResult:
        """Capture one PNG correlated with the retained query and announcement."""
        decoded: FrameCaptureResult | None = None

        def request(request_id: str) -> FrameCaptureRequest:
            return FrameCaptureRequest.from_core(request_id=request_id, query=query)

        def announce(envelope: BridgeRpcSuccessEnvelope) -> BridgeBinaryAnnouncement:
            response = decode_expected_success(envelope, FrameCaptureResponse)
            response.result.validate_announcement(query=query)
            transfer = response.result.transfer

            def consume(png_bytes: bytes) -> None:
                nonlocal decoded
                decoded = response.result.to_core(query=query, png_bytes=png_bytes)

            return BridgeBinaryAnnouncement(
                response=response,
                transfer_id=bytes.fromhex(transfer.transfer_id),
                byte_length=transfer.byte_length,
                maximum_payload_bytes=query.maximum_bytes,
                consume=consume,
            )

        await self._connection.call_binary(
            request,
            announce,
            map_remote_error=map_frame_remote_error,
        )
        if decoded is None:
            raise RuntimeError("frame response completed without its Core value")
        return decoded
