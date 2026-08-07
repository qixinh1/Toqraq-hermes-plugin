"""Session event WebSocket ownership and cross-thread delivery tests."""

from __future__ import annotations

import asyncio
from threading import Event, Thread, get_ident
from typing import Any

from toqraq.api.events import _send_events, _SessionEventDelivery
from toqraq.contracts.events import SessionEventType
from toqraq.services.events import SessionEventStream

from _session_contract_support import session_result


class _RecordingWebSocket:
    """Record the first serialized event sent by the socket presenter."""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []
        self.sent = asyncio.Event()

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.payloads.append(payload)
        self.sent.set()


def test_host_thread_publish_reaches_sender_on_websocket_owner_loop(tmp_path) -> None:
    async def scenario() -> None:
        owner_thread = get_ident()
        publishing_threads: list[int] = []
        stream = SessionEventStream(lambda: 10.0)
        queue = asyncio.Queue(maxsize=2)
        websocket = _RecordingWebSocket()
        delivery = _SessionEventDelivery(asyncio.get_running_loop(), queue, "hermes-1")
        dispose = stream.subscribe(delivery.offer)
        sender = asyncio.create_task(_send_events(websocket, queue))  # type: ignore[arg-type]

        def publish() -> None:
            publishing_threads.append(get_ident())
            stream.publish(SessionEventType.READINESS, session_result(tmp_path))

        try:
            await asyncio.to_thread(publish)
            await asyncio.wait_for(websocket.sent.wait(), timeout=1)
            assert len(publishing_threads) == 1
            assert publishing_threads[0] != owner_thread
            assert websocket.payloads[0]["session_id"] == "hermes-1"
            assert websocket.payloads[0]["sequence"] == 1
        finally:
            delivery.close()
            dispose()
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)

    asyncio.run(scenario())


def test_close_rejects_an_offer_already_scheduled_from_a_host_thread(tmp_path) -> None:
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        stream = SessionEventStream(lambda: 10.0)
        queue = asyncio.Queue(maxsize=2)
        delivery = _SessionEventDelivery(loop, queue, "hermes-1")
        dispose = stream.subscribe(delivery.offer)
        published = Event()

        def publish() -> None:
            stream.publish(SessionEventType.READINESS, session_result(tmp_path))
            published.set()

        publisher = Thread(target=publish, daemon=True)
        publisher.start()
        assert published.wait(timeout=1)

        delivery.close()
        dispose()
        publisher.join(timeout=1)
        assert not publisher.is_alive()

        owner_loop_drained: asyncio.Future[None] = loop.create_future()
        loop.call_soon(owner_loop_drained.set_result, None)
        await asyncio.wait_for(owner_loop_drained, timeout=1)
        assert queue.empty()

    asyncio.run(scenario())
