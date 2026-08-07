"""Real-socket deadline, cancellation-slot, disconnect, and close tests."""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy

import pytest
from pydantic import ValidationError
from toqraq.bridge.bridge_rpc_state import BridgeRpcPolicy, acquire_work_slot_or_termination
from toqraq.contracts.bridge_cancellation import RequestCancelResponse
from toqraq.contracts.bridge_rpc import BridgeRpcOperationErrorEnvelope
from toqraq.core.errors import BridgeConnectionError, ProtocolError
from toqraq.core.request_cancellation import (
    CancellationAcknowledgement,
    CancellationDisposition,
)
from websockets.exceptions import ConnectionClosed

from _bridge_rpc_support import (
    open_rpc_harness,
    pause_operation,
    pause_response,
    receive_json,
)

_TRACE = "123e4567-e89b-42d3-a456-426614174000"


def _cancel_response(cancel_id: str) -> str:
    """Encode one exact lightweight requested acknowledgement."""
    return RequestCancelResponse.from_core(
        request_id=cancel_id,
        value=CancellationAcknowledgement(
            disposition=CancellationDisposition.REQUESTED,
        ),
    ).model_dump_json()


def _cancelled_work_response(request_id: str) -> str:
    """Encode the built-in fieldless terminal cancellation error."""
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32800,
                "message": "Request cancelled",
                "data": {
                    "code": "request.cancelled",
                    "category": "conflict",
                    "parameters": {},
                    "details": {},
                    "trace_id": _TRACE,
                },
            },
        }
    )


def test_terminal_cancellation_contract_has_one_fieldless_shape() -> None:
    payload = json.loads(_cancelled_work_response("host-1"))
    envelope = BridgeRpcOperationErrorEnvelope.model_validate(payload)
    assert envelope.error.code == -32800
    assert envelope.error.data.code == "request.cancelled"

    for field in ("parameters", "details"):
        invalid = deepcopy(payload)
        invalid["error"]["data"][field] = {"reason": "native text is forbidden"}
        with pytest.raises(ValidationError, match="must not contain fields"):
            BridgeRpcOperationErrorEnvelope.model_validate(invalid)


def test_unsolicited_terminal_cancellation_fails_protocol() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness()
        connection = harness.authenticated.connection
        operation = pause_operation()
        call = asyncio.create_task(connection.call(operation.request, operation.decode))
        request = await receive_json(harness.peer)
        await harness.peer.send(_cancelled_work_response(str(request["id"])))

        with pytest.raises(ProtocolError) as raised:
            await call
        assert raised.value.details == {"reason": "unexpected_request_cancellation"}
        assert (await connection.wait_disconnected()).kind == "protocol"
        await harness.close()

    asyncio.run(scenario())


def test_termination_wins_when_capacity_is_already_available() -> None:
    async def scenario() -> None:
        semaphore = asyncio.BoundedSemaphore(1)
        termination = asyncio.Event()
        termination.set()

        acquired = await acquire_work_slot_or_termination(
            semaphore,
            termination,
            expires_at=asyncio.get_running_loop().time() + 1.0,
        )

        assert acquired is False
        await asyncio.wait_for(semaphore.acquire(), timeout=0.1)

    asyncio.run(scenario())


def test_caller_cancellation_uses_control_slot_and_keeps_original_owner() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness(max_in_flight=1)
        connection = harness.authenticated.connection
        first_operation = pause_operation()
        first = asyncio.create_task(
            connection.call(
                first_operation.request,
                first_operation.decode,
                timeout_seconds=1.0,
            )
        )
        first_request = await receive_json(harness.peer)
        assert first_request["id"] == "host-1"

        first.cancel()
        cancellation = await receive_json(harness.peer)
        assert cancellation["id"] == "host-2"
        assert cancellation["method"] == "toqraq.request.cancel"
        assert cancellation["params"] == {"target_request_id": "host-1"}
        await harness.peer.send(_cancel_response("host-2"))
        with pytest.raises(asyncio.CancelledError):
            await first

        second_operation = pause_operation(False)
        second = asyncio.create_task(
            connection.call(
                second_operation.request,
                second_operation.decode,
                timeout_seconds=1.0,
            )
        )
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(harness.peer.recv(), timeout=0.05)

        await harness.peer.send(_cancelled_work_response("host-1"))
        second_request = await receive_json(harness.peer)
        assert second_request["id"] == "host-3"
        await harness.peer.send(pause_response("host-3", second_operation.command))
        assert (await second).result.paused is False
        assert not connection.disconnected
        await harness.close()

    asyncio.run(scenario())


def test_total_deadline_releases_work_then_sends_independent_cancellation() -> None:
    async def scenario() -> None:
        policy = BridgeRpcPolicy(cancellation_grace_seconds=0.25)
        harness = await open_rpc_harness(max_in_flight=1, rpc_policy=policy)
        connection = harness.authenticated.connection
        operation = pause_operation()
        call = asyncio.create_task(
            connection.call(operation.request, operation.decode, timeout_seconds=0.05)
        )
        request = await receive_json(harness.peer)
        cancellation = await receive_json(harness.peer)
        assert cancellation["id"] == "host-2"
        assert cancellation["params"] == {"target_request_id": request["id"]}
        await harness.peer.send(_cancel_response("host-2"))
        with pytest.raises(BridgeConnectionError) as raised:
            await call
        assert raised.value.details == {"reason": "request_deadline"}

        await harness.peer.send(pause_response("host-1", operation.command))
        disconnection = await connection.wait_disconnected()
        assert disconnection.kind == "protocol"
        await harness.close()

    asyncio.run(scenario())


def test_missing_cancellation_ack_fails_closed_after_separate_grace() -> None:
    async def scenario() -> None:
        policy = BridgeRpcPolicy(
            cancellation_grace_seconds=0.05,
            close_timeout_seconds=0.25,
        )
        harness = await open_rpc_harness(max_in_flight=1, rpc_policy=policy)
        connection = harness.authenticated.connection
        operation = pause_operation()
        call = asyncio.create_task(
            connection.call(operation.request, operation.decode, timeout_seconds=0.03)
        )
        await receive_json(harness.peer)
        cancellation = await receive_json(harness.peer)
        assert cancellation["method"] == "toqraq.request.cancel"
        with pytest.raises(BridgeConnectionError) as raised:
            await call
        assert raised.value.details == {"reason": "request_deadline"}

        disconnection = await connection.wait_disconnected()
        assert disconnection.kind == "cancellation_control"
        with pytest.raises(ConnectionClosed):
            await harness.peer.recv()
        await harness.close()

    asyncio.run(scenario())


def test_owner_close_is_bounded_idempotent_and_settles_waiter_once() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness(max_in_flight=1)
        connection = harness.authenticated.connection
        operation = pause_operation()
        call = asyncio.create_task(connection.call(operation.request, operation.decode))
        await receive_json(harness.peer)
        queued_operation = pause_operation(False)
        queued = asyncio.create_task(
            connection.call(queued_operation.request, queued_operation.decode)
        )

        await asyncio.gather(connection.close(), connection.close())
        await connection.close()
        for waiter in (call, queued):
            with pytest.raises(BridgeConnectionError) as raised:
                await waiter
            assert raised.value.details == {"reason": "connection_closed"}
        assert connection.closed
        assert (await connection.wait_disconnected()).kind == "owner"
        await harness.close()

    asyncio.run(scenario())


def test_cancelling_capacity_wait_does_not_leak_the_work_slot() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness(max_in_flight=1)
        connection = harness.authenticated.connection
        first_operation = pause_operation()
        first = asyncio.create_task(
            connection.call(first_operation.request, first_operation.decode)
        )
        first_request = await receive_json(harness.peer)

        waiting_operation = pause_operation(False)
        waiting = asyncio.create_task(
            connection.call(waiting_operation.request, waiting_operation.decode)
        )
        await asyncio.sleep(0)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting

        await harness.peer.send(pause_response(str(first_request["id"]), first_operation.command))
        await first
        third_operation = pause_operation(False)
        third = asyncio.create_task(
            connection.call(third_operation.request, third_operation.decode)
        )
        third_request = await receive_json(harness.peer)
        assert third_request["id"] == "host-2"
        await harness.peer.send(pause_response("host-2", third_operation.command))
        await third
        await harness.close()

    asyncio.run(scenario())


def test_natural_disconnect_is_observable_and_wakes_pending_work() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness()
        connection = harness.authenticated.connection
        operation = pause_operation()
        call = asyncio.create_task(connection.call(operation.request, operation.decode))
        await receive_json(harness.peer)
        await harness.peer.close()

        disconnection = await connection.wait_disconnected()
        assert disconnection.kind == "remote"
        with pytest.raises(BridgeConnectionError) as raised:
            await call
        assert raised.value.details == {"reason": "connection_closed"}
        await harness.listener.close()
        assert connection.closed

    asyncio.run(scenario())
