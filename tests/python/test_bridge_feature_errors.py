"""Real-socket method-specific remote error mapping tests for Bridge features."""

from __future__ import annotations

import asyncio
import json

import pytest
from toqraq.bridge.bridge_features.aggregate import create_bridge_feature_ports
from toqraq.core.errors import PerceptionStaleError, ProtocolError

from _bridge_feature_values import frame_values, hierarchy_values
from _bridge_rpc_support import open_rpc_harness, receive_json

_REMOTE_TRACE = "123e4567-e89b-42d3-a456-426614174000"


def _application_error(
    request_id: str,
    *,
    code: str,
    category: str,
    details: dict[str, object] | None = None,
) -> str:
    """Encode one bounded non-internal application error for a peer."""
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32000,
                "message": "application failure",
                "data": {
                    "code": code,
                    "category": category,
                    "parameters": {},
                    "details": details or {},
                    "trace_id": _REMOTE_TRACE,
                },
            },
        }
    )


def test_read_adapter_maps_only_its_allowed_registered_error() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness()
        features = create_bridge_feature_ports(harness.authenticated)
        query, _page = hierarchy_values()
        call = asyncio.create_task(features.hierarchy.read(query))
        request = await receive_json(harness.peer)
        await harness.peer.send(
            _application_error(
                str(request["id"]),
                code="perception.stale",
                category="conflict",
                details={"current_revision": "hierarchy:2"},
            )
        )

        with pytest.raises(PerceptionStaleError) as raised:
            await call
        assert raised.value.details == {"current_revision": "hierarchy:2"}
        assert str(raised.value.trace_id) != _REMOTE_TRACE
        assert not harness.authenticated.connection.disconnected
        await harness.close()

    asyncio.run(scenario())


def test_error_allowed_for_reads_but_not_frame_capture_fails_protocol() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness()
        features = create_bridge_feature_ports(harness.authenticated)
        query, _frame = frame_values()
        call = asyncio.create_task(features.frame.capture(query))
        request = await receive_json(harness.peer)
        await harness.peer.send(
            _application_error(
                str(request["id"]),
                code="perception.stale",
                category="conflict",
            )
        )

        with pytest.raises(ProtocolError):
            await call
        assert (await harness.authenticated.connection.wait_disconnected()).kind == "protocol"
        await harness.close()

    asyncio.run(scenario())
