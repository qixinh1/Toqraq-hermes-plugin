"""Real-socket fixtures for the authenticated controlled Bridge RPC tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast

from toqraq.bridge.bridge_authentication import AuthenticatedBridge
from toqraq.bridge.bridge_listener import BridgeListener
from toqraq.bridge.bridge_listener_policy import BridgeListenerPolicy
from toqraq.bridge.bridge_rpc_codec import decode_expected_success
from toqraq.bridge.bridge_rpc_state import BridgeRpcPolicy
from toqraq.contracts.bridge import BRIDGE_HANDSHAKE_METHOD
from toqraq.contracts.bridge_rpc import BridgeRpcSuccessEnvelope
from toqraq.contracts.bridge_simulation import (
    SimulationSetPausedRequest,
    SimulationSetPausedResponse,
)
from toqraq.core.bridge import BridgeHandshakeExpectation, BridgeLimits, BridgeOwnerKey
from toqraq.core.observation import ObservationRevision
from toqraq.core.runtime import RuntimeEntryPointBinding, RuntimeIdentity, RuntimeRelease
from toqraq.core.simulation_control import SetPausedAcknowledgement, SetPausedCommand
from websockets.asyncio.client import ClientConnection, connect

_CREDENTIAL = "a" * 64
_SESSION_ID = "rpc-session"
_BRIDGE_CAPABILITIES = frozenset({"godot.observe.physics"})
_CONTRIBUTION_CAPABILITIES = _BRIDGE_CAPABILITIES | frozenset({"game.project.inspect"})


@dataclass(slots=True, kw_only=True)
class BridgeRpcHarness:
    """One listener, authenticated engine peer, and controlled connection claim."""

    listener: BridgeListener
    peer: ClientConnection
    authenticated: AuthenticatedBridge

    async def close(self) -> None:
        """Release both ends through the owning listener path."""
        await self.listener.close()
        await self.peer.wait_closed()


def runtime_release(
    *,
    bridge_capabilities: frozenset[str] = _BRIDGE_CAPABILITIES,
    contribution_capabilities: frozenset[str] = _CONTRIBUTION_CAPABILITIES,
) -> RuntimeRelease:
    """Build one certified runtime with distinct contribution and bridge sets."""
    component_id = "2" * 64
    return RuntimeRelease(
        identity=RuntimeIdentity(
            engine_id="godot",
            version="4.7.1",
            build_id="toqraq.rpc.1",
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
        capability_ids=contribution_capabilities,
        bridge_capability_ids=bridge_capabilities,
    )


def expectation(
    *,
    max_in_flight: int = 4,
    max_binary_bytes: int = 32 << 20,
    bridge_capabilities: frozenset[str] = _BRIDGE_CAPABILITIES,
    contribution_capabilities: frozenset[str] = _CONTRIBUTION_CAPABILITIES,
) -> BridgeHandshakeExpectation:
    """Build one exact listener expectation with a selectable work bound."""
    return BridgeHandshakeExpectation(
        credential=_CREDENTIAL,
        owner=BridgeOwnerKey(session_id=_SESSION_ID, run_revision=3),
        release=runtime_release(
            bridge_capabilities=bridge_capabilities,
            contribution_capabilities=contribution_capabilities,
        ),
        limits=BridgeLimits(
            max_text_message_bytes=262_144,
            max_binary_transfer_bytes=max_binary_bytes,
            max_in_flight_requests=max_in_flight,
        ),
    )


def handshake_payload(
    *,
    max_in_flight: int = 4,
    max_binary_bytes: int = 32 << 20,
    bridge_capabilities: frozenset[str] = _BRIDGE_CAPABILITIES,
) -> dict[str, object]:
    """Build the peer offer corresponding to ``expectation``."""
    return {
        "jsonrpc": "2.0",
        "id": "engine-handshake:3",
        "method": BRIDGE_HANDSHAKE_METHOD,
        "params": {
            "credential": _CREDENTIAL,
            "session_id": _SESSION_ID,
            "run_revision": 3,
            "engine_id": "godot",
            "engine_version": "4.7.1",
            "build_id": "toqraq.rpc.1",
            "distribution_id": "toqraq",
            "platform": "windows",
            "architecture": "x86_64",
            "bridge_id": "toqraq.godot.bridge",
            "protocol": "1.0",
            "capabilities": sorted(bridge_capabilities),
            "limits": {
                "max_text_message_bytes": 262_144,
                "max_binary_transfer_bytes": max_binary_bytes,
                "max_in_flight_requests": max_in_flight,
            },
        },
    }


async def open_rpc_harness(
    *,
    max_in_flight: int = 4,
    max_binary_bytes: int = 32 << 20,
    rpc_policy: BridgeRpcPolicy | None = None,
    bridge_capabilities: frozenset[str] = _BRIDGE_CAPABILITIES,
    contribution_capabilities: frozenset[str] = _CONTRIBUTION_CAPABILITIES,
) -> BridgeRpcHarness:
    """Authenticate one real WebSocket peer and claim its controlled connection."""
    listener = await BridgeListener.open(
        expectation(
            max_in_flight=max_in_flight,
            max_binary_bytes=max_binary_bytes,
            bridge_capabilities=bridge_capabilities,
            contribution_capabilities=contribution_capabilities,
        ),
        BridgeListenerPolicy(rpc=rpc_policy or BridgeRpcPolicy()),
    )
    peer = await connect(
        listener.endpoint.url,
        compression=None,
        open_timeout=1.0,
        close_timeout=1.0,
        max_size=max(262_144, max_binary_bytes + 16),
    )
    await peer.send(
        json.dumps(
            handshake_payload(
                max_in_flight=max_in_flight,
                max_binary_bytes=max_binary_bytes,
                bridge_capabilities=bridge_capabilities,
            )
        )
    )
    response = await peer.recv()
    assert isinstance(response, str)
    assert "result" in cast(dict[str, object], json.loads(response))
    return BridgeRpcHarness(
        listener=listener,
        peer=peer,
        authenticated=await listener.claim_authenticated(),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class PauseRpcOperation:
    """Keep one pause command with both of its correlated RPC adapters."""

    command: SetPausedCommand

    def request(self, request_id: str) -> SimulationSetPausedRequest:
        """Bind the owned command to one host-issued identity."""
        return SimulationSetPausedRequest.from_core(
            request_id=request_id,
            command=self.command,
        )

    def decode(self, envelope: BridgeRpcSuccessEnvelope) -> SimulationSetPausedResponse:
        """Decode and correlate one result with the exact owned command."""
        response = decode_expected_success(envelope, SimulationSetPausedResponse)
        response.result.to_core(command=self.command)
        return response


def pause_operation(paused: bool = True) -> PauseRpcOperation:
    """Create one complete request/response operation for a desired pause state."""
    return PauseRpcOperation(command=SetPausedCommand(paused=paused))


def pause_response(
    request_id: str,
    command: SetPausedCommand,
    *,
    changed: bool = True,
) -> str:
    """Encode one command-correlated peer pause acknowledgement."""
    return SimulationSetPausedResponse.from_core(
        request_id=request_id,
        value=SetPausedAcknowledgement(
            paused=command.paused,
            changed=changed,
            simulation_revision=ObservationRevision(value="simulation:1"),
            frame_revision=ObservationRevision(value="frame:1"),
        ),
        command=command,
    ).model_dump_json()


async def receive_json(peer: ClientConnection) -> dict[str, object]:
    """Receive one peer text message and decode its test-owned JSON object."""
    message = await peer.recv()
    assert isinstance(message, str)
    return cast(dict[str, object], json.loads(message))
