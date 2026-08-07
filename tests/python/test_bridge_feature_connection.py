"""Transport-hidden runtime feature connection ownership tests."""

from __future__ import annotations

import asyncio
import json
from typing import cast

import pytest
import toqraq.bridge.bridge_listener as bridge_listener_module
from toqraq.bridge.bridge_feature_connection import BridgeRuntimeFeatureConnectionFactory
from toqraq.bridge.bridge_listener import BridgeListener
from toqraq.bridge.bridge_websocket import BridgeSocket
from toqraq.core.errors import BridgeConnectionError
from toqraq.core.runtime_features import (
    RuntimeFeatureConnection,
    RuntimeFeatureConnectionFactory,
    RuntimeFeaturePorts,
)
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from _bridge_rpc_support import expectation, handshake_payload


async def _peer(owner: RuntimeFeatureConnection) -> ClientConnection:
    """Open one bounded engine-side socket for a runtime feature owner."""
    return await connect(
        owner.endpoint.url,
        compression=None,
        open_timeout=1.0,
        close_timeout=1.0,
        max_size=32 << 20,
    )


def test_factory_hides_listener_authentication_and_rpc_behind_core_owner() -> None:
    async def scenario() -> None:
        factory = BridgeRuntimeFeatureConnectionFactory()
        assert isinstance(factory, RuntimeFeatureConnectionFactory)
        owner = await factory.open(expectation())
        assert isinstance(owner, RuntimeFeatureConnection)
        assert owner.owner == expectation().owner
        assert not hasattr(owner, "listener")
        assert not hasattr(owner, "connection")

        peer = await _peer(owner)
        await peer.send(json.dumps(handshake_payload()))
        response = await peer.recv()
        assert isinstance(response, str)

        features = await owner.wait_ready()
        assert isinstance(features, RuntimeFeaturePorts)
        assert await owner.wait_ready() is features
        assert not hasattr(features, "close")
        unavailable = asyncio.create_task(owner.wait_unavailable())
        await owner.close()
        await peer.wait_closed()
        failure = await unavailable
        assert isinstance(failure, BridgeConnectionError)
        assert failure.details == {"reason": "connection_closed"}
        with pytest.raises(BridgeConnectionError) as raised:
            await owner.wait_ready()
        assert raised.value.details == {"reason": "connection_closed"}

    asyncio.run(scenario())


def test_cancelled_readiness_wait_does_not_consume_the_authentication_claim() -> None:
    async def scenario() -> None:
        owner = await BridgeRuntimeFeatureConnectionFactory().open(expectation())
        first = asyncio.create_task(owner.wait_ready())
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first

        peer = await _peer(owner)
        await peer.send(json.dumps(handshake_payload()))
        assert isinstance(await peer.recv(), str)
        assert isinstance(await owner.wait_ready(), RuntimeFeaturePorts)
        await owner.close()
        await peer.wait_closed()

    asyncio.run(scenario())


def test_proven_identity_mismatch_is_one_immediate_safe_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        rejection_entered = asyncio.Event()
        release_rejection = asyncio.Event()
        original_rejection = BridgeListener._send_rejection

        async def delayed_rejection(
            listener: BridgeListener,
            peer: BridgeSocket,
            response: str,
        ) -> None:
            rejection_entered.set()
            await release_rejection.wait()
            await original_rejection(listener, peer, response)

        monkeypatch.setattr(BridgeListener, "_send_rejection", delayed_rejection)
        owner = await BridgeRuntimeFeatureConnectionFactory().open(expectation())
        concurrent = await _peer(owner)
        cancelled = asyncio.create_task(owner.wait_ready())
        await asyncio.sleep(0)
        cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled

        mismatch = await _peer(owner)
        payload = handshake_payload()
        params = cast(dict[str, object], payload["params"])
        credential = cast(str, params["credential"])
        params["build_id"] = "toqraq.rpc.2"
        await mismatch.send(json.dumps(payload))
        await asyncio.wait_for(rejection_entered.wait(), timeout=1.0)

        with pytest.raises(BridgeConnectionError) as first:
            await asyncio.wait_for(owner.wait_ready(), timeout=1.0)
        failure = first.value
        assert failure.parameters == {"field": "build_id"}
        assert failure.details == {
            "reason": "authenticated_handshake_mismatch",
            "wire_code": "bridge.handshake_mismatch",
            "wire_category": "unauthenticated",
        }
        with pytest.raises(BridgeConnectionError) as repeated:
            await owner.wait_ready()
        assert repeated.value is failure
        assert credential not in repr(failure)
        assert "toqraq.rpc.2" not in repr(failure.cause)

        release_rejection.set()
        message = await mismatch.recv()
        assert isinstance(message, str)
        response = cast(dict[str, object], json.loads(message))
        error = cast(dict[str, object], response["error"])
        data = cast(dict[str, object], error["data"])
        assert error["code"] == -32001
        assert data["trace_id"] == str(failure.trace_id)
        assert credential not in message

        await concurrent.send(json.dumps(handshake_payload()))
        with pytest.raises(ConnectionClosed):
            await concurrent.recv()
        with pytest.raises((OSError, InvalidStatus)):
            await _peer(owner)
        await owner.close()
        await mismatch.wait_closed()

    asyncio.run(scenario())


def test_success_response_encoding_failure_is_terminal_before_peer_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingResponse:
        """Test boundary that fails after the exact offer authenticates."""

        @staticmethod
        def from_core(**_values: object) -> None:
            raise RuntimeError("response encoding failed")

    async def scenario() -> None:
        monkeypatch.setattr(bridge_listener_module, "BridgeHandshakeResponse", FailingResponse)
        owner = await BridgeRuntimeFeatureConnectionFactory().open(expectation())
        peer = await _peer(owner)
        await peer.send(json.dumps(handshake_payload()))

        with pytest.raises(BridgeConnectionError) as raised:
            await asyncio.wait_for(owner.wait_ready(), timeout=1.0)
        assert raised.value.details == {"reason": "handshake_response_failed"}
        with pytest.raises(ConnectionClosed):
            await peer.recv()
        await owner.close()

    asyncio.run(scenario())
