"""Focused runtime-object reader over one controlled Bridge connection."""

from __future__ import annotations

from ...contracts.bridge_objects import ObjectReadRequest, ObjectReadResponse
from ...contracts.bridge_rpc import BridgeRpcSuccessEnvelope
from ...core.object_inspection import ObjectReadQuery, ObjectSnapshot
from ..bridge_rpc_codec import decode_expected_success
from ..bridge_rpc_connection import BridgeRpcConnection
from .remote_errors import map_perception_reference_remote_error


class BridgeObjectReader:
    """Construct, correlate, and return only selected object Core values."""

    __slots__ = ("_connection",)

    def __init__(self, connection: BridgeRpcConnection) -> None:
        """Bind the reader to one authenticated controlled connection."""
        if not isinstance(connection, BridgeRpcConnection):
            raise TypeError("controlled Bridge connection is invalid")
        self._connection = connection

    async def read(self, query: ObjectReadQuery) -> ObjectSnapshot:
        """Inspect explicit objects against the exact retained query."""
        decoded: ObjectSnapshot | None = None

        def request(request_id: str) -> ObjectReadRequest:
            return ObjectReadRequest.from_core(request_id=request_id, query=query)

        def decode(envelope: BridgeRpcSuccessEnvelope) -> ObjectReadResponse:
            nonlocal decoded
            response = decode_expected_success(envelope, ObjectReadResponse)
            decoded = response.result.to_core(query=query)
            return response

        await self._connection.call(
            request,
            decode,
            map_remote_error=map_perception_reference_remote_error,
        )
        if decoded is None:
            raise RuntimeError("object response completed without its Core value")
        return decoded
