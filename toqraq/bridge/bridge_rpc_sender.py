"""Serialized, bounded, strongly owned writes for one Bridge RPC socket."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeAlias

from ..core.errors import BridgeConnectionError
from .bridge_rpc_observability import observe_bridge_ownership_task
from .bridge_rpc_state import PendingBridgeRequest
from .bridge_websocket import BridgeSocket

BridgeTransportFailure: TypeAlias = Callable[[str], None]


class BridgeRpcSender:
    """Own write serialization, work-send tasks, and transport failure signaling."""

    def __init__(
        self,
        *,
        socket: BridgeSocket,
        send_timeout_seconds: float,
        transport_failed: BridgeTransportFailure,
    ) -> None:
        """Create an empty writer before a request can publish work."""
        if not callable(transport_failed):
            raise TypeError("Bridge transport-failure callback is invalid")
        self._socket = socket
        self._send_timeout_seconds = send_timeout_seconds
        self._transport_failed = transport_failed
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[None]] = set()

    def start(
        self,
        pending: PendingBridgeRequest,
        payload: str,
        expires_at: float,
    ) -> asyncio.Task[None]:
        """Strongly own one cancellation-safe work send."""
        task = asyncio.create_task(
            self._send_work(pending, payload, expires_at),
            name=f"toqraq-bridge-send-{pending.request_id}",
        )
        pending.send_task = task
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        task.add_done_callback(observe_bridge_ownership_task)
        return task

    async def send(self, payload: str, *, expires_at: float) -> None:
        """Serialize one socket write within operation and transport deadlines."""
        loop = asyncio.get_running_loop()
        send_deadline = min(expires_at, loop.time() + self._send_timeout_seconds)
        async with asyncio.timeout_at(send_deadline):
            async with self._lock:
                await self._socket.send(payload)

    async def wait(self) -> None:
        """Observe every strongly owned work-send task during connection cleanup."""
        tasks = tuple(self._tasks)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_work(
        self,
        pending: PendingBridgeRequest,
        payload: str,
        expires_at: float,
    ) -> None:
        """Publish dispatch only after the complete text message is written."""
        try:
            await self.send(payload, expires_at=expires_at)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._transport_failed("send_failed")
            raise BridgeConnectionError(
                details={"reason": "send_failed"},
                cause=exc,
            ) from None
        pending.dispatched = True
