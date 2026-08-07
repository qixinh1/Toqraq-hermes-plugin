"""First-cause arbitration and bounded transport teardown for Bridge RPC."""

from __future__ import annotations

import asyncio

from ..core.errors import BridgeConnectionError
from .bridge_rpc_observability import observe_bridge_ownership_task
from .bridge_rpc_state import BridgeDisconnection, BridgeDisconnectionKind
from .bridge_websocket import BridgeSocket

_CLOSE_CODE = 1001
_CLOSE_REASON = "bridge connection closing"


class BridgeConnectionTermination:
    """Own one terminal cause, transport-close task, and published final fact."""

    def __init__(self, *, socket: BridgeSocket, close_timeout_seconds: float) -> None:
        """Create terminal state before the sole reader can observe a frame."""
        self._socket = socket
        self._close_timeout_seconds = close_timeout_seconds
        loop = asyncio.get_running_loop()
        self._disconnection: asyncio.Future[BridgeDisconnection] = loop.create_future()
        self._started = asyncio.Event()
        self._kind: BridgeDisconnectionKind | None = None
        self._failure: BridgeConnectionError | None = None
        self._transport_task: asyncio.Task[None] | None = None

    @property
    def started_event(self) -> asyncio.Event:
        """Expose the terminal signal used to wake capacity waiters."""
        return self._started

    @property
    def started(self) -> bool:
        """Report whether one first cause has already won arbitration."""
        return self._kind is not None

    @property
    def disconnected(self) -> bool:
        """Report whether bounded transport teardown published its final fact."""
        return self._disconnection.done()

    @property
    def failure(self) -> BridgeConnectionError | None:
        """Return the immutable first failure for per-waiter copies."""
        return self._failure

    def begin(
        self,
        kind: BridgeDisconnectionKind,
        failure: BridgeConnectionError,
    ) -> bool:
        """Choose exactly one cause and start transport teardown without awaiting."""
        if not isinstance(kind, BridgeDisconnectionKind):
            raise TypeError("bridge disconnection kind is invalid")
        if not isinstance(failure, BridgeConnectionError):
            raise TypeError("bridge disconnection failure is invalid")
        if self._kind is not None:
            return False
        self._kind = kind
        self._failure = failure
        self._started.set()
        self.ensure_transport()
        return True

    def ensure_transport(self) -> asyncio.Task[None]:
        """Return the successful close owner or start one retry after failure."""
        if self._kind is None:
            raise RuntimeError("bridge transport close started before termination")
        task = self._transport_task
        if task is not None and not task.done():
            return task
        if task is not None and not task.cancelled() and task.exception() is None:
            return task
        task = asyncio.create_task(
            self._close_transport(),
            name="toqraq-bridge-transport-close",
        )
        task.add_done_callback(observe_bridge_ownership_task)
        self._transport_task = task
        return task

    async def wait(self) -> BridgeDisconnection:
        """Wait without allowing caller cancellation to consume the final fact."""
        return await asyncio.shield(self._disconnection)

    async def _close_transport(self) -> None:
        """Complete the closing handshake before publishing disconnection."""
        try:
            async with asyncio.timeout(self._close_timeout_seconds):
                await self._socket.close(_CLOSE_CODE, _CLOSE_REASON)
                await self._socket.wait_closed()
        except TimeoutError as exc:
            raise BridgeConnectionError(
                details={"reason": "connection_cleanup_timeout"},
                cause=exc,
            ) from None
        except Exception as exc:
            raise BridgeConnectionError(
                details={"reason": "connection_cleanup_failed"},
                cause=exc,
            ) from None
        if not self._disconnection.done():
            kind = self._kind
            if kind is None:
                raise RuntimeError("bridge termination cause was lost")
            self._disconnection.set_result(BridgeDisconnection(kind=kind))
