"""Session-scoped event WebSocket presenter."""

from __future__ import annotations

import asyncio
import contextlib
from threading import Lock
from typing import TYPE_CHECKING

from fastapi.routing import APIRouter
from starlette.websockets import WebSocket, WebSocketDisconnect

from ..contracts.events import SessionEvent
from ..contracts.identifiers import HermesSessionId

if TYPE_CHECKING:
    from ..services.container import Container

SESSION_EVENT_SOCKET_QUEUE_LIMIT = 64


def router_for(container: Container) -> APIRouter:
    """Build the bounded event stream bound to one process-local service graph."""
    router = APIRouter()

    @router.websocket("/sessions/{session_id}/events")
    async def events(websocket: WebSocket, session_id: HermesSessionId) -> None:
        """Stream only events owned by the selected Hermes session."""
        await websocket.accept()
        queue: asyncio.Queue[SessionEvent] = asyncio.Queue(maxsize=SESSION_EVENT_SOCKET_QUEUE_LIMIT)
        delivery = _SessionEventDelivery(asyncio.get_running_loop(), queue, session_id)
        dispose = container.events.subscribe(delivery.offer)
        tasks = (
            asyncio.create_task(_send_events(websocket, queue), name="toqraq-events-send"),
            asyncio.create_task(_wait_disconnect(websocket), name="toqraq-events-receive"),
        )
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            delivery.close()
            dispose()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            with contextlib.suppress(Exception):
                await websocket.close()

    return router


class _SessionEventDelivery:
    """Own cross-thread delivery into one WebSocket event loop and queue."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue[SessionEvent],
        session_id: str,
    ) -> None:
        self._loop = loop
        self._queue = queue
        self._session_id = session_id
        self._lock = Lock()
        self._closed = False

    def offer(self, event: SessionEvent) -> None:
        """Schedule one matching event on the queue's owning event loop."""
        if event.session_id != self._session_id:
            return
        with self._lock:
            if self._closed:
                return
            self._loop.call_soon_threadsafe(self._offer_on_owner_loop, event)

    def close(self) -> None:
        """Reject callbacks captured before or after subscriber disposal."""
        with self._lock:
            self._closed = True

    def _offer_on_owner_loop(self, event: SessionEvent) -> None:
        """Apply bounded overflow policy only from the queue's event loop."""
        with self._lock:
            if self._closed:
                return
            _offer_event(self._queue, event)


async def _wait_disconnect(websocket: WebSocket) -> None:
    """Consume client messages until its WebSocket disconnects."""
    try:
        while True:
            await websocket.receive()
    except (WebSocketDisconnect, RuntimeError):
        return


def _offer_event(
    queue: asyncio.Queue[SessionEvent],
    event: SessionEvent,
) -> None:
    """Enqueue one owned event and make sequence gaps detectable on overflow."""
    if queue.full():
        with contextlib.suppress(asyncio.QueueEmpty):
            queue.get_nowait()
    with contextlib.suppress(asyncio.QueueFull):
        queue.put_nowait(event)


async def _send_events(websocket: WebSocket, queue: asyncio.Queue[SessionEvent]) -> None:
    """Serialize validated envelopes sequentially until disconnect."""
    while True:
        event = await queue.get()
        await websocket.send_json(event.model_dump(mode="json"))
