"""Focused first-cause and retry tests for Bridge RPC transport termination."""

from __future__ import annotations

import asyncio
from typing import cast

import pytest
from toqraq.bridge.bridge_rpc_state import BridgeDisconnectionKind
from toqraq.bridge.bridge_rpc_termination import BridgeConnectionTermination
from toqraq.bridge.bridge_websocket import BridgeSocket
from toqraq.core.errors import BridgeConnectionError, ProtocolError


class RetrySocket:
    """Fail the first close attempt and record the bounded retry."""

    def __init__(self) -> None:
        self.close_attempts = 0
        self.wait_attempts = 0

    async def close(self, _code: int = 1000, _reason: str = "") -> None:
        """Fail exactly once before accepting a retry."""
        self.close_attempts += 1
        if self.close_attempts == 1:
            raise RuntimeError("synthetic close failure")

    async def wait_closed(self) -> None:
        """Record publication waiting after a successful close."""
        self.wait_attempts += 1


def test_first_cause_survives_failed_transport_close_and_retry() -> None:
    async def scenario() -> None:
        fake_socket = RetrySocket()
        termination = BridgeConnectionTermination(
            socket=cast(BridgeSocket, fake_socket),
            close_timeout_seconds=0.1,
        )
        failure = ProtocolError(details={"reason": "invalid_rpc_message"})

        assert termination.begin(BridgeDisconnectionKind.PROTOCOL, failure)
        assert termination.started
        assert termination.started_event.is_set()
        assert termination.failure is failure
        with pytest.raises(BridgeConnectionError) as raised:
            await termination.ensure_transport()
        assert raised.value.details == {"reason": "connection_cleanup_failed"}
        assert not termination.disconnected

        assert not termination.begin(
            BridgeDisconnectionKind.OWNER,
            BridgeConnectionError(details={"reason": "connection_closed"}),
        )
        await termination.ensure_transport()
        disconnected = await termination.wait()

        assert disconnected.kind is BridgeDisconnectionKind.PROTOCOL
        assert fake_socket.close_attempts == 2
        assert fake_socket.wait_attempts == 1
        assert termination.disconnected

    asyncio.run(scenario())
