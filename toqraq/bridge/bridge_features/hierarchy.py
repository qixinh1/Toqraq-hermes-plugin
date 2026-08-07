"""Focused hierarchy reader over one controlled Bridge connection."""

from __future__ import annotations

from ...contracts.bridge_hierarchy import HierarchyReadRequest, HierarchyReadResponse
from ...contracts.bridge_rpc import BridgeRpcSuccessEnvelope
from ...core.hierarchy import HierarchyPage, HierarchyQuery
from ..bridge_rpc_codec import decode_expected_success
from ..bridge_rpc_connection import BridgeRpcConnection
from .remote_errors import map_perception_reference_remote_error


class BridgeHierarchyReader:
    """Construct, correlate, and return only bounded hierarchy Core values."""

    __slots__ = ("_connection",)

    def __init__(self, connection: BridgeRpcConnection) -> None:
        """Bind the reader to one authenticated controlled connection."""
        if not isinstance(connection, BridgeRpcConnection):
            raise TypeError("controlled Bridge connection is invalid")
        self._connection = connection

    async def read(self, query: HierarchyQuery) -> HierarchyPage:
        """Read one page correlated with the exact retained query."""
        decoded: HierarchyPage | None = None

        def request(request_id: str) -> HierarchyReadRequest:
            return HierarchyReadRequest.from_core(request_id=request_id, query=query)

        def decode(envelope: BridgeRpcSuccessEnvelope) -> HierarchyReadResponse:
            nonlocal decoded
            response = decode_expected_success(envelope, HierarchyReadResponse)
            decoded = response.result.to_core(query=query)
            return response

        await self._connection.call(
            request,
            decode,
            map_remote_error=map_perception_reference_remote_error,
        )
        if decoded is None:
            raise RuntimeError("hierarchy response completed without its Core value")
        return decoded
