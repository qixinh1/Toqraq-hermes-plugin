"""Focused diagnostics reader over one controlled Bridge connection."""

from __future__ import annotations

from ...contracts.bridge_diagnostics import DiagnosticsReadRequest, DiagnosticsReadResponse
from ...contracts.bridge_rpc import BridgeRpcSuccessEnvelope
from ...core.diagnostics import DiagnosticsPage, DiagnosticsQuery
from ..bridge_rpc_codec import decode_expected_success
from ..bridge_rpc_connection import BridgeRpcConnection
from .remote_errors import map_perception_stale_remote_error


class BridgeDiagnosticsReader:
    """Construct, correlate, and return only bounded diagnostic Core values."""

    __slots__ = ("_connection",)

    def __init__(self, connection: BridgeRpcConnection) -> None:
        """Bind the reader to one authenticated controlled connection."""
        if not isinstance(connection, BridgeRpcConnection):
            raise TypeError("controlled Bridge connection is invalid")
        self._connection = connection

    async def read(self, query: DiagnosticsQuery) -> DiagnosticsPage:
        """Read diagnostics correlated with the exact retained filters."""
        decoded: DiagnosticsPage | None = None

        def request(request_id: str) -> DiagnosticsReadRequest:
            return DiagnosticsReadRequest.from_core(request_id=request_id, query=query)

        def decode(envelope: BridgeRpcSuccessEnvelope) -> DiagnosticsReadResponse:
            nonlocal decoded
            response = decode_expected_success(envelope, DiagnosticsReadResponse)
            decoded = response.result.to_core(query=query)
            return response

        await self._connection.call(
            request,
            decode,
            map_remote_error=map_perception_stale_remote_error,
        )
        if decoded is None:
            raise RuntimeError("diagnostics response completed without its Core value")
        return decoded
