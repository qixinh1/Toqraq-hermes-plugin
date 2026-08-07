"""Real-socket success and typed-boundary tests for controlled Bridge RPC."""

from __future__ import annotations

import asyncio
import json
from typing import cast

import pytest
from toqraq.bridge.bridge_remote_error import BridgeRemoteError
from toqraq.core.errors import BridgeConnectionError, ProtocolError

from _bridge_rpc_support import (
    open_rpc_harness,
    pause_operation,
    pause_response,
    receive_json,
)

_REMOTE_TRACE = "123e4567-e89b-42d3-a456-426614174000"


def test_out_of_order_responses_use_unique_monotonic_host_ids() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness(max_in_flight=2)
        connection = harness.authenticated.connection
        first_operation = pause_operation(True)
        second_operation = pause_operation(False)
        first = asyncio.create_task(
            connection.call(first_operation.request, first_operation.decode)
        )
        second = asyncio.create_task(
            connection.call(second_operation.request, second_operation.decode)
        )
        requests = [await receive_json(harness.peer), await receive_json(harness.peer)]
        by_paused: dict[bool, dict[str, object]] = {}
        for request in requests:
            params = cast(dict[str, object], request["params"])
            by_paused[cast(bool, params["paused"])] = request
        true_request = by_paused[True]
        false_request = by_paused[False]
        assert {request["id"] for request in requests} == {"host-1", "host-2"}

        await harness.peer.send(pause_response(str(false_request["id"]), second_operation.command))
        await harness.peer.send(pause_response(str(true_request["id"]), first_operation.command))
        first_result, second_result = await asyncio.gather(first, second)
        assert first_result.result.paused is True
        assert second_result.result.paused is False
        assert not connection.disconnected
        await harness.close()

    asyncio.run(scenario())


def test_state_changed_is_a_six_family_dirty_set_not_a_fifo() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness()
        connection = harness.authenticated.connection
        operation = pause_operation()
        call = asyncio.create_task(connection.call(operation.request, operation.decode))
        request = await receive_json(harness.peer)
        notification = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "toqraq.state.changed",
                "params": {
                    "families": [
                        "simulation",
                        "frame",
                        "hierarchy",
                        "objects",
                        "diagnostics",
                        "metrics",
                    ]
                },
            }
        )
        for _index in range(100):
            await harness.peer.send(notification)
        await harness.peer.send(pause_response(str(request["id"]), operation.command))
        await call

        assert connection.take_state_changes() == (
            "hierarchy",
            "objects",
            "diagnostics",
            "metrics",
            "frame",
            "simulation",
        )
        assert connection.take_state_changes() == ()
        assert not connection.disconnected
        await harness.close()

    asyncio.run(scenario())


def test_remote_error_preserves_safe_value_and_separate_local_trace() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness()
        connection = harness.authenticated.connection
        remote_failures: list[BridgeRemoteError] = []
        operation = pause_operation()

        def map_remote_error(failure: BridgeRemoteError) -> BridgeConnectionError:
            remote_failures.append(failure)
            return BridgeConnectionError(details={"reason": "mapped_test_failure"})

        call = asyncio.create_task(
            connection.call(
                operation.request,
                operation.decode,
                map_remote_error=map_remote_error,
            )
        )
        request = await receive_json(harness.peer)
        technical_message = "native technical detail must stay private"
        await harness.peer.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "error": {
                        "code": -32000,
                        "message": technical_message,
                        "data": {
                            "code": "simulation.invalid_state",
                            "category": "conflict",
                            "parameters": {"expected": "paused"},
                            "details": {"current": "running"},
                            "trace_id": _REMOTE_TRACE,
                        },
                    },
                }
            )
        )
        with pytest.raises(BridgeConnectionError) as raised:
            await call
        assert raised.value.details == {"reason": "mapped_test_failure"}
        failure = remote_failures.pop()
        assert failure.rpc_code == -32000
        assert failure.remote.code == "simulation.invalid_state"
        assert failure.remote.parameters["expected"].data == "paused"
        assert failure.remote.details["current"].data == "running"
        assert failure.remote.trace_id == _REMOTE_TRACE
        assert str(failure.local_trace_id) != failure.remote.trace_id
        assert technical_message not in repr(failure)
        assert technical_message not in repr(failure.args)

        follow_up_operation = pause_operation()
        follow_up = asyncio.create_task(
            connection.call(follow_up_operation.request, follow_up_operation.decode)
        )
        follow_up_request = await receive_json(harness.peer)
        assert follow_up_request["id"] == "host-2"
        await harness.peer.send(pause_response("host-2", follow_up_operation.command))
        await follow_up
        assert not connection.disconnected
        await harness.close()

    asyncio.run(scenario())


def test_per_request_decoder_can_enforce_operation_correlation() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness()
        connection = harness.authenticated.connection
        operation = pause_operation(True)
        call = asyncio.create_task(connection.call(operation.request, operation.decode))
        request = await receive_json(harness.peer)
        response = json.loads(pause_response(str(request["id"]), operation.command))
        cast(dict[str, object], response["result"])["paused"] = False
        await harness.peer.send(json.dumps(response))
        with pytest.raises(ProtocolError) as raised:
            await call
        assert raised.value.details == {"reason": "invalid_rpc_response"}
        disconnected = await connection.wait_disconnected()
        assert disconnected.kind == "protocol"
        await harness.close()

    asyncio.run(scenario())


def test_empty_native_bridge_set_authenticates_without_feature_claim() -> None:
    async def scenario() -> None:
        contribution = frozenset({"game.project.inspect", "game.lifecycle.start"})
        harness = await open_rpc_harness(
            bridge_capabilities=frozenset(),
            contribution_capabilities=contribution,
        )
        authenticated = harness.authenticated
        assert authenticated.acceptance.capability_ids == frozenset()
        assert not hasattr(authenticated.connection, "capability_ids")
        assert not hasattr(authenticated, "feature_ports")
        await harness.close()

    asyncio.run(scenario())
