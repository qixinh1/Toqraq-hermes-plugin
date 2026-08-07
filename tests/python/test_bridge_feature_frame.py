"""Real-socket binary ownership and integrity tests for focused frame capture."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace

import pytest
from toqraq.bridge.bridge_binary_transfer import (
    MAX_BRIDGE_BINARY_FRAME_BYTES,
    bridge_transport_message_limit,
)
from toqraq.bridge.bridge_features.aggregate import create_bridge_feature_ports
from toqraq.bridge.bridge_rpc_state import BridgeRpcPolicy
from toqraq.contracts.bridge_frame import FrameCaptureRequest, FrameCaptureResponse
from toqraq.core.bridge import MAX_BRIDGE_BINARY_TRANSFER_BYTES
from toqraq.core.errors import BridgeConnectionError, ProtocolError
from toqraq.core.frame_capture import FrameCaptureQuery, FrameCaptureResult

from _bridge_feature_values import frame_values
from _bridge_rpc_support import BridgeRpcHarness, open_rpc_harness, receive_json

_TRANSFER_ID = "123e4567e89b42d3a456426614174000"


async def _capture_request(
    harness: BridgeRpcHarness,
    query: FrameCaptureQuery,
) -> tuple[asyncio.Task[FrameCaptureResult], FrameCaptureRequest]:
    """Start one focused capture and return its exact peer request."""
    features = create_bridge_feature_ports(harness.authenticated)
    capture = asyncio.create_task(features.frame.capture(query))
    request = FrameCaptureRequest.model_validate(await receive_json(harness.peer))
    return capture, request


def _binary(data: bytes, transfer_id: str = _TRANSFER_ID) -> bytes:
    """Prefix one test payload with the protocol's raw 128-bit transfer ID."""
    return bytes.fromhex(transfer_id) + data


def test_transport_limit_includes_prefix_and_rejects_above_protocol_maximum() -> None:
    assert (
        bridge_transport_message_limit(
            maximum_text_bytes=262_144,
            maximum_binary_bytes=MAX_BRIDGE_BINARY_TRANSFER_BYTES,
        )
        == MAX_BRIDGE_BINARY_FRAME_BYTES
    )
    assert (
        bridge_transport_message_limit(
            maximum_text_bytes=262_144,
            maximum_binary_bytes=1,
        )
        == 262_144
    )
    with pytest.raises(ValueError, match="binary-transfer"):
        bridge_transport_message_limit(
            maximum_text_bytes=262_144,
            maximum_binary_bytes=MAX_BRIDGE_BINARY_TRANSFER_BYTES + 1,
        )


def test_binary_larger_than_text_limit_completes_and_late_duplicate_fails_closed() -> None:
    async def scenario() -> None:
        query, frame = frame_values(padding_bytes=300_000)
        harness = await open_rpc_harness(max_binary_bytes=len(frame.data))
        task, request = await _capture_request(harness, query)
        assert request.params.to_core() == query
        response = FrameCaptureResponse.from_core(
            request_id=request.id,
            value=frame,
            query=query,
            transfer_id=_TRANSFER_ID,
        )
        await harness.peer.send(response.model_dump_json())
        message = _binary(frame.data)
        await harness.peer.send(message)
        assert await task == frame

        await harness.peer.send(message)
        assert (await harness.authenticated.connection.wait_disconnected()).kind == "protocol"
        await harness.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ("transfer_id", "length", "hash", "png", "query"))
def test_binary_integrity_or_query_mismatch_fails_closed_without_a_result(
    failure: str,
) -> None:
    async def scenario() -> None:
        original_query, frame = frame_values()
        request_query = (
            replace(original_query, maximum_bytes=len(frame.data) - 1)
            if failure == "query"
            else original_query
        )
        harness = await open_rpc_harness()
        task, request = await _capture_request(harness, request_query)
        response = FrameCaptureResponse.from_core(
            request_id=request.id,
            value=frame,
            query=original_query,
            transfer_id=_TRANSFER_ID,
        )
        payload = response.model_dump(mode="json")
        binary = _binary(frame.data)
        if failure == "transfer_id":
            binary = _binary(frame.data, "0" * 32)
        elif failure == "length":
            binary += b"x"
        elif failure == "hash":
            payload["result"]["transfer"]["sha256"] = "0" * 64
        elif failure == "png":
            invalid_png = b"not-png!" + frame.data[8:]
            payload["result"]["transfer"]["sha256"] = hashlib.sha256(invalid_png).hexdigest()
            binary = _binary(invalid_png)
        await harness.peer.send(FrameCaptureResponse.model_validate(payload).model_dump_json())
        if failure != "query":
            await harness.peer.send(binary)

        with pytest.raises(ProtocolError):
            await task
        assert (await harness.authenticated.connection.wait_disconnected()).kind == "protocol"
        await harness.close()

    asyncio.run(scenario())


def test_text_interleaving_after_announcement_fails_closed() -> None:
    async def scenario() -> None:
        query, frame = frame_values()
        harness = await open_rpc_harness()
        task, request = await _capture_request(harness, query)
        await harness.peer.send(
            FrameCaptureResponse.from_core(
                request_id=request.id,
                value=frame,
                query=query,
                transfer_id=_TRANSFER_ID,
            ).model_dump_json()
        )
        await harness.peer.send(
            '{"jsonrpc":"2.0","method":"toqraq.state.changed","params":{"families":["frame"]}}'
        )

        with pytest.raises(ProtocolError):
            await task
        assert (await harness.authenticated.connection.wait_disconnected()).kind == "protocol"
        await harness.close()

    asyncio.run(scenario())


def test_announcement_without_binary_uses_the_original_total_deadline() -> None:
    async def scenario() -> None:
        query, frame = frame_values()
        harness = await open_rpc_harness(
            rpc_policy=BridgeRpcPolicy(
                work_timeout_seconds=0.02,
                maximum_work_timeout_seconds=1.0,
                send_timeout_seconds=1.0,
                cancellation_grace_seconds=1.0,
                close_timeout_seconds=1.0,
            )
        )
        task, request = await _capture_request(harness, query)
        await harness.peer.send(
            FrameCaptureResponse.from_core(
                request_id=request.id,
                value=frame,
                query=query,
                transfer_id=_TRANSFER_ID,
            ).model_dump_json()
        )

        with pytest.raises(ProtocolError) as raised:
            await task
        assert raised.value.details == {"reason": "binary_transfer_deadline"}
        assert (await harness.authenticated.connection.wait_disconnected()).kind == "protocol"
        await harness.close()

    asyncio.run(scenario())


def test_caller_cancellation_after_announcement_discards_transfer_and_connection() -> None:
    async def scenario() -> None:
        query, frame = frame_values()
        harness = await open_rpc_harness()
        task, request = await _capture_request(harness, query)
        await harness.peer.send(
            FrameCaptureResponse.from_core(
                request_id=request.id,
                value=frame,
                query=query,
                transfer_id=_TRANSFER_ID,
            ).model_dump_json()
        )
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (await harness.authenticated.connection.wait_disconnected()).kind == "protocol"
        await harness.close()

    asyncio.run(scenario())


def test_disconnect_after_announcement_settles_capture_without_retaining_bytes() -> None:
    async def scenario() -> None:
        query, frame = frame_values()
        harness = await open_rpc_harness()
        task, request = await _capture_request(harness, query)
        await harness.peer.send(
            FrameCaptureResponse.from_core(
                request_id=request.id,
                value=frame,
                query=query,
                transfer_id=_TRANSFER_ID,
            ).model_dump_json()
        )
        await harness.peer.close()

        with pytest.raises(BridgeConnectionError):
            await task
        assert (await harness.authenticated.connection.wait_disconnected()).kind == "remote"
        await harness.close()

    asyncio.run(scenario())


def test_frame_above_negotiated_binary_ceiling_is_rejected_by_real_transport() -> None:
    async def scenario() -> None:
        binary_limit = 300_000
        _query, header = frame_values()
        query, frame = frame_values(padding_bytes=binary_limit - len(header.data))
        harness = await open_rpc_harness(max_binary_bytes=binary_limit)
        task, request = await _capture_request(harness, query)
        await harness.peer.send(
            FrameCaptureResponse.from_core(
                request_id=request.id,
                value=frame,
                query=query,
                transfer_id=_TRANSFER_ID,
            ).model_dump_json()
        )
        await harness.peer.send(_binary(frame.data + b"x"))

        with pytest.raises(BridgeConnectionError):
            await task
        await harness.authenticated.connection.wait_disconnected()
        await harness.close()

    asyncio.run(scenario())
