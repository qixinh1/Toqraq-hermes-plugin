"""Real-socket ownership and authentication tests for the bridge listener."""

from __future__ import annotations

import asyncio
import gc
import json
import logging
import weakref
from typing import cast

import pytest
import toqraq.bridge.bridge_listener as bridge_listener_module
from toqraq.bridge.bridge_listener import BridgeListener
from toqraq.bridge.bridge_listener_policy import BridgeListenerPolicy
from toqraq.contracts.bridge import BRIDGE_HANDSHAKE_METHOD
from toqraq.core.bridge import (
    BRIDGE_ENDPOINT_PATH,
    BRIDGE_LOOPBACK_HOST,
    BridgeHandshakeExpectation,
    BridgeLimits,
    BridgeOwnerKey,
)
from toqraq.core.capability_ids import (
    MANDATORY_BRIDGE_CAPABILITY_IDS,
    MANDATORY_ENGINE_CAPABILITY_IDS,
)
from toqraq.core.errors import BridgeConnectionError
from toqraq.core.runtime import RuntimeEntryPointBinding, RuntimeIdentity, RuntimeRelease
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

_CREDENTIAL = "c" * 64
_SESSION_ID = "hermes-session"
_CAPABILITIES = MANDATORY_ENGINE_CAPABILITY_IDS | frozenset({"godot.observe.physics"})
_BRIDGE_CAPABILITIES = MANDATORY_BRIDGE_CAPABILITY_IDS | frozenset({"godot.observe.physics"})


def _release() -> RuntimeRelease:
    """Build one exact runtime identity expected by the listener."""
    component_id = "1" * 64
    return RuntimeRelease(
        identity=RuntimeIdentity(
            engine_id="godot",
            version="4.7.1",
            build_id="toqraq.1",
            distribution_id="toqraq",
            platform="windows",
            architecture="x86_64",
        ),
        component_release_ids=(component_id,),
        entry_point_bindings=(
            RuntimeEntryPointBinding(
                name="editor",
                component_release_id=component_id,
                component_entry_point_name="editor",
            ),
        ),
        bridge_id="toqraq.godot.bridge",
        bridge_protocol="1.0",
        capability_ids=_CAPABILITIES,
        bridge_capability_ids=_BRIDGE_CAPABILITIES,
    )


def _expectation(
    credential: str = _CREDENTIAL,
    *,
    text_limit: int = 262_144,
) -> BridgeHandshakeExpectation:
    """Build the immutable launch facts for one listener."""
    return BridgeHandshakeExpectation(
        credential=credential,
        owner=BridgeOwnerKey(session_id=_SESSION_ID, run_revision=9),
        release=_release(),
        limits=BridgeLimits(
            max_text_message_bytes=text_limit,
            max_binary_transfer_bytes=32 << 20,
            max_in_flight_requests=8,
        ),
    )


def _payload(
    credential: str = _CREDENTIAL,
    *,
    request_id: str = "handshake:9",
    method: str = BRIDGE_HANDSHAKE_METHOD,
    text_limit: int = 262_144,
) -> dict[str, object]:
    """Build one complete first-message request."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": {
            "credential": credential,
            "session_id": _SESSION_ID,
            "run_revision": 9,
            "engine_id": "godot",
            "engine_version": "4.7.1",
            "build_id": "toqraq.1",
            "distribution_id": "toqraq",
            "platform": "windows",
            "architecture": "x86_64",
            "bridge_id": "toqraq.godot.bridge",
            "protocol": "1.0",
            "capabilities": sorted(_BRIDGE_CAPABILITIES),
            "limits": {
                "max_text_message_bytes": text_limit,
                "max_binary_transfer_bytes": 32 << 20,
                "max_in_flight_requests": 8,
            },
        },
    }


async def _client(listener: BridgeListener, *, origin: str | None = None) -> ClientConnection:
    """Connect one bounded test client without negotiating compression."""
    options: dict[str, object] = {
        "compression": None,
        "open_timeout": 1.0,
        "close_timeout": 1.0,
        "max_size": 262_144,
    }
    if origin is not None:
        options["origin"] = origin
    return await connect(listener.endpoint.url, **options)


async def _authenticate(
    listener: BridgeListener,
    credential: str = _CREDENTIAL,
    *,
    text_limit: int = 262_144,
) -> tuple[ClientConnection, dict[str, object]]:
    """Connect, send a valid offer, and decode the success response."""
    client = await _client(listener)
    await client.send(json.dumps(_payload(credential, text_limit=text_limit)))
    message = await client.recv()
    assert isinstance(message, str)
    return client, cast(dict[str, object], json.loads(message))


def test_valid_handshake_exposes_exact_nonsecret_endpoint_and_keeps_socket() -> None:
    async def scenario() -> None:
        listener = await BridgeListener.open(_expectation())
        assert listener.endpoint.host == BRIDGE_LOOPBACK_HOST
        assert listener.endpoint.path == BRIDGE_ENDPOINT_PATH
        assert listener.endpoint.url.startswith("ws://127.0.0.1:")
        assert listener.endpoint.url.endswith(BRIDGE_ENDPOINT_PATH)

        client, response = await _authenticate(listener)
        authenticated = await listener.claim_authenticated()
        accepted = authenticated.acceptance
        with pytest.raises(RuntimeError):
            await listener.claim_authenticated()
        assert not hasattr(authenticated.connection, "socket")
        assert not hasattr(authenticated.connection, "execute")
        assert response["id"] == "handshake:9"
        assert accepted.owner == BridgeOwnerKey(session_id=_SESSION_ID, run_revision=9)
        assert not listener.accepting
        assert client.close_code is None
        assert "Server" not in client.response.headers
        assert "Sec-WebSocket-Extensions" not in client.response.headers
        with pytest.raises((OSError, InvalidStatus)):
            await _client(listener)

        await listener.close()
        await client.wait_closed()
        assert client.close_code == 1001
        assert listener.closed

    asyncio.run(scenario())


def test_wrong_path_and_browser_origin_are_rejected_before_dispatch() -> None:
    async def scenario() -> None:
        listener = await BridgeListener.open(_expectation())
        wrong_url = listener.endpoint.url.replace(BRIDGE_ENDPOINT_PATH, "/other")
        with pytest.raises(InvalidStatus):
            await connect(wrong_url, compression=None, open_timeout=1.0)
        with pytest.raises(InvalidStatus):
            await _client(listener, origin="https://example.invalid")
        assert listener.accepting
        client, _ = await _authenticate(listener)
        await listener.claim_authenticated()
        await listener.close()
        await client.wait_closed()

    asyncio.run(scenario())


def test_invalid_offer_echoes_only_valid_request_id_then_allows_valid_offer() -> None:
    async def scenario() -> None:
        listener = await BridgeListener.open(_expectation())
        pending_claim = asyncio.create_task(listener.claim_authenticated())
        await asyncio.sleep(0)
        mismatch = await _client(listener)
        await mismatch.send(json.dumps(_payload("d" * 64, request_id="bad-credential")))
        mismatch_message = await mismatch.recv()
        assert isinstance(mismatch_message, str)
        mismatch_response = cast(dict[str, object], json.loads(mismatch_message))
        assert mismatch_response["id"] == "bad-credential"
        mismatch_error = cast(dict[str, object], mismatch_response["error"])
        assert mismatch_error["code"] == -32001
        with pytest.raises(ConnectionClosed):
            await mismatch.recv()
        assert not pending_claim.done()

        invalid = await _client(listener)
        await invalid.send(
            json.dumps(_payload(method="toqraq.not-the-handshake", request_id="valid-id"))
        )
        message = await invalid.recv()
        assert isinstance(message, str)
        rejection = cast(dict[str, object], json.loads(message))
        assert rejection["id"] == "valid-id"
        error = cast(dict[str, object], rejection["error"])
        assert error["code"] == -32601
        with pytest.raises(ConnectionClosed):
            await invalid.recv()

        client, response = await _authenticate(listener)
        assert "result" in response
        await pending_claim
        await listener.close()
        await client.wait_closed()

    asyncio.run(scenario())


def test_malformed_envelope_uses_null_id_and_does_not_consume_credential() -> None:
    async def scenario() -> None:
        listener = await BridgeListener.open(_expectation())
        invalid = await _client(listener)
        malformed = {**_payload(request_id="apparently-valid"), "extra": True}
        await invalid.send(json.dumps(malformed))
        message = await invalid.recv()
        assert isinstance(message, str)
        rejection = cast(dict[str, object], json.loads(message))
        assert rejection["id"] is None
        client, _ = await _authenticate(listener)
        await listener.claim_authenticated()
        await listener.close()
        await client.wait_closed()

    asyncio.run(scenario())


def test_first_message_timeout_and_binary_first_do_not_block_later_client() -> None:
    async def scenario() -> None:
        policy = BridgeListenerPolicy(first_message_timeout_seconds=0.05)
        listener = await BridgeListener.open(_expectation(), policy)

        silent = await _client(listener)
        with pytest.raises(ConnectionClosed) as timed_out:
            await silent.recv()
        assert timed_out.value.rcvd is not None
        assert timed_out.value.rcvd.code == 1008

        binary = await _client(listener)
        await binary.send(b"not a handshake")
        with pytest.raises(ConnectionClosed) as binary_closed:
            await binary.recv()
        assert binary_closed.value.rcvd is not None
        assert binary_closed.value.rcvd.code == 1008

        client, _ = await _authenticate(listener)
        await listener.claim_authenticated()
        await listener.close()
        await client.wait_closed()

    asyncio.run(scenario())


def test_codec_rejects_oversize_text_and_then_accepts_valid_client() -> None:
    async def scenario() -> None:
        listener = await BridgeListener.open(_expectation(text_limit=4_096))
        oversized = await _client(listener)
        await oversized.send("x" * 4_097)
        response = await oversized.recv()
        assert isinstance(response, str)
        failure = cast(dict[str, object], json.loads(response))
        error = cast(dict[str, object], failure["error"])
        data = cast(dict[str, object], error["data"])
        assert error["code"] == -32002
        assert data["code"] == "bridge.message_too_large"
        with pytest.raises(ConnectionClosed) as closed:
            await oversized.recv()
        assert closed.value.rcvd is not None
        assert closed.value.rcvd.code == 1008

        client, _ = await _authenticate(listener, text_limit=4_096)
        await listener.claim_authenticated()
        await listener.close()
        await client.wait_closed()

    asyncio.run(scenario())


def test_two_matching_connections_have_exactly_one_winner() -> None:
    async def scenario() -> None:
        listener = await BridgeListener.open(_expectation())
        first, second = await asyncio.gather(_client(listener), _client(listener))
        request = json.dumps(_payload())
        await asyncio.gather(first.send(request), second.send(request))

        async def outcome(client: ClientConnection) -> str:
            try:
                message = await client.recv()
            except ConnectionClosed:
                return "closed"
            assert isinstance(message, str)
            return "success" if "result" in json.loads(message) else "rejected"

        outcomes = await asyncio.gather(outcome(first), outcome(second))
        assert outcomes.count("success") == 1
        assert outcomes.count("closed") + outcomes.count("rejected") == 1
        await listener.claim_authenticated()
        await listener.close()
        await asyncio.gather(first.wait_closed(), second.wait_closed())

    asyncio.run(scenario())


def test_close_before_authentication_is_bounded_and_idempotent() -> None:
    async def scenario() -> None:
        listener = await BridgeListener.open(_expectation())
        endpoint = listener.endpoint
        await asyncio.gather(listener.close(), listener.close())
        await listener.close()
        assert listener.closed
        assert not listener.accepting
        with pytest.raises(BridgeConnectionError) as raised:
            await listener.claim_authenticated()
        assert raised.value.code == "bridge.unavailable"
        assert raised.value.details == {"reason": "listener_closed"}
        assert raised.value.__cause__ is None
        assert raised.value.__context__ is None
        with pytest.raises(OSError):
            await asyncio.wait_for(
                asyncio.open_connection(endpoint.host, endpoint.port),
                timeout=1.0,
            )

    asyncio.run(scenario())


def test_connection_start_failure_settles_the_authentication_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        listener = await BridgeListener.open(_expectation())

        def fail_connection(**_arguments: object) -> None:
            raise RuntimeError("connection construction failed")

        monkeypatch.setattr(
            bridge_listener_module,
            "BridgeRpcConnection",
            fail_connection,
        )
        client, response = await _authenticate(listener)
        assert "result" in response

        with pytest.raises(BridgeConnectionError) as raised:
            await asyncio.wait_for(listener.claim_authenticated(), timeout=1.0)
        assert raised.value.details == {"reason": "connection_start_failed"}
        with pytest.raises(ConnectionClosed):
            await client.recv()
        await listener.close()
        assert listener.closed

    asyncio.run(scenario())


def test_credential_leaves_listener_references_and_never_enters_debug_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class Secret(str):
        """Weak-referenceable credential probe."""

    async def scenario() -> None:
        credential = Secret("e" * 64)
        reference = weakref.ref(credential)
        expectation = _expectation(credential)
        listener = await BridgeListener.open(expectation)
        assert credential not in repr(listener)
        del expectation, credential
        gc.collect()
        assert reference() is not None

        client, response = await _authenticate(listener, "e" * 64)
        await listener.claim_authenticated()
        assert "e" * 64 not in json.dumps(response)
        gc.collect()
        assert reference() is None
        await listener.close()
        await client.wait_closed()

    caplog.set_level(logging.DEBUG, logger="toqraq.bridge.bridge_websocket.transport")
    asyncio.run(scenario())
    records = [
        record
        for record in caplog.records
        if record.name.startswith("toqraq.bridge.bridge_websocket")
    ]
    assert all("e" * 64 not in record.getMessage() for record in records)
    assert all("e" * 64 not in repr(record.args) for record in records)
