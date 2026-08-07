"""Real-socket fail-closed tests for malformed and miscorrelated Bridge RPC."""

from __future__ import annotations

import asyncio
import json
import logging

import pytest
from pydantic import ValidationError
from toqraq.contracts.bridge_rpc import BridgeRpcSuccessEnvelope
from toqraq.core.errors import ProtocolError

from _bridge_rpc_support import (
    open_rpc_harness,
    pause_operation,
    pause_response,
    receive_json,
)

_TRACE = "123e4567-e89b-42d3-a456-426614174000"


@pytest.mark.parametrize(
    "frame",
    (
        '{"jsonrpc":"2.0","method":"toqraq.state.changed",'
        '"params":{"families":["frame"]},"extra":true}',
        '{"jsonrpc":"2.0","method":"toqraq.unknown","params":{}}',
        '{"jsonrpc":"2.0","id":"host-1","result":{"value":NaN}}',
        '{"jsonrpc":"2.0","id":"host-1","id":"host-1","result":{}}',
        '{"jsonrpc":"2.0","id":"engine-1","result":{}}',
    ),
)
def test_invalid_text_envelopes_fail_closed(frame: str) -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness()
        connection = harness.authenticated.connection
        await harness.peer.send(frame)
        disconnection = await connection.wait_disconnected()
        assert disconnection.kind == "protocol"
        await harness.close()

    asyncio.run(scenario())


def test_binary_without_announced_transfer_fails_closed() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness()
        connection = harness.authenticated.connection
        await harness.peer.send(b"unannounced")
        assert (await connection.wait_disconnected()).kind == "protocol"
        await harness.close()

    asyncio.run(scenario())


def test_unknown_and_duplicate_response_ids_fail_closed() -> None:
    async def unknown_scenario() -> None:
        harness = await open_rpc_harness()
        connection = harness.authenticated.connection
        operation = pause_operation()
        await harness.peer.send(pause_response("host-99", operation.command))
        assert (await connection.wait_disconnected()).kind == "protocol"
        await harness.close()

    async def duplicate_scenario() -> None:
        harness = await open_rpc_harness()
        connection = harness.authenticated.connection
        operation = pause_operation()
        call = asyncio.create_task(connection.call(operation.request, operation.decode))
        request = await receive_json(harness.peer)
        response = pause_response(str(request["id"]), operation.command)
        await harness.peer.send(response)
        await call
        await harness.peer.send(response)
        assert (await connection.wait_disconnected()).kind == "protocol"
        await harness.close()

    asyncio.run(unknown_scenario())
    asyncio.run(duplicate_scenario())


def test_invalid_expected_result_fails_connection_and_pending_call() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness()
        connection = harness.authenticated.connection
        operation = pause_operation()
        call = asyncio.create_task(connection.call(operation.request, operation.decode))
        request = await receive_json(harness.peer)
        await harness.peer.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "result": {"paused": "not-a-boolean"},
                }
            )
        )
        with pytest.raises(ProtocolError) as raised:
            await call
        assert raised.value.details == {"reason": "invalid_rpc_response"}
        assert (await connection.wait_disconnected()).kind == "protocol"
        await harness.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "error",
    (
        {
            "code": -32001,
            "message": "unsupported number",
            "data": {
                "code": "simulation.invalid_state",
                "category": "conflict",
                "parameters": {},
                "details": {},
                "trace_id": _TRACE,
            },
        },
        {
            "code": -32601,
            "message": "Method not found",
            "data": {
                "code": "simulation.invalid_state",
                "category": "conflict",
                "parameters": {},
                "details": {},
                "trace_id": _TRACE,
            },
        },
        {
            "code": -32000,
            "message": "application failure",
            "data": {
                "code": "simulation.internal_failure",
                "category": "internal",
                "parameters": {},
                "details": {},
                "trace_id": _TRACE,
            },
        },
    ),
)
def test_unknown_or_inconsistent_error_classification_fails_closed(
    error: dict[str, object],
) -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness()
        connection = harness.authenticated.connection
        operation = pause_operation()
        call = asyncio.create_task(connection.call(operation.request, operation.decode))
        request = await receive_json(harness.peer)
        await harness.peer.send(json.dumps({"jsonrpc": "2.0", "id": request["id"], "error": error}))
        with pytest.raises(ProtocolError):
            await call
        assert (await connection.wait_disconnected()).kind == "protocol"
        await harness.close()

    asyncio.run(scenario())


def test_valid_but_unmapped_application_error_fails_closed() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness()
        connection = harness.authenticated.connection
        operation = pause_operation()
        call = asyncio.create_task(connection.call(operation.request, operation.decode))
        request = await receive_json(harness.peer)
        await harness.peer.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "error": {
                        "code": -32000,
                        "message": "application failure",
                        "data": {
                            "code": "simulation.invalid_state",
                            "category": "conflict",
                            "parameters": {},
                            "details": {},
                            "trace_id": _TRACE,
                        },
                    },
                }
            )
        )
        with pytest.raises(ProtocolError) as raised:
            await call
        assert raised.value.details == {"reason": "unmapped_remote_error"}
        assert (await connection.wait_disconnected()).kind == "protocol"
        await harness.close()

    asyncio.run(scenario())


def test_post_auth_host_id_has_exact_shape_and_safe_integer_bound() -> None:
    maximum = "host-9007199254740991"
    assert (
        BridgeRpcSuccessEnvelope.model_validate(
            {"jsonrpc": "2.0", "id": maximum, "result": None}
        ).id
        == maximum
    )
    for invalid in (
        "host-0",
        "host-01",
        "engine-1",
        "host-9007199254740992",
    ):
        with pytest.raises(ValidationError):
            BridgeRpcSuccessEnvelope.model_validate(
                {"jsonrpc": "2.0", "id": invalid, "result": None}
            )


def test_protocol_failure_logs_do_not_retain_frame_or_technical_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "frame-secret-that-must-not-be-logged"

    async def scenario() -> None:
        harness = await open_rpc_harness()
        connection = harness.authenticated.connection
        operation = pause_operation()
        call = asyncio.create_task(connection.call(operation.request, operation.decode))
        request = await receive_json(harness.peer)
        await harness.peer.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "result": {"paused": secret},
                }
            )
        )
        with pytest.raises(ProtocolError):
            await call
        await connection.wait_disconnected()
        await harness.close()

    caplog.set_level(logging.DEBUG)
    asyncio.run(scenario())
    plugin_records = [record for record in caplog.records if record.name.startswith("toqraq.")]
    assert all(secret not in record.getMessage() for record in plugin_records)
    assert all(secret not in repr(record.args) for record in plugin_records)
