"""Minimal typed session event sequencing and fan-out tests."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock, Thread

import pytest
from pydantic import ValidationError
from toqraq.contracts.errors import error_envelope
from toqraq.contracts.events import SESSION_EVENT_ADAPTER, SessionEvent, SessionEventType
from toqraq.core.errors import ProtocolError
from toqraq.services.events import SessionEventStream

from _session_contract_support import session_result


def test_event_stream_sequences_one_hermes_owner_until_finalization(tmp_path) -> None:
    timestamps = iter((10.0, 11.0, 12.0))
    stream = SessionEventStream(lambda: next(timestamps))
    received: list[SessionEvent] = []
    stream.subscribe(received.append)
    session = session_result(tmp_path)

    first = stream.publish(SessionEventType.STARTED, session)
    second = stream.publish(SessionEventType.READINESS, session)
    stream.finalize("hermes-1")
    after_finalize = stream.publish(SessionEventType.READINESS, session)

    assert (first.sequence, second.sequence, after_finalize.sequence) == (1, 2, 1)
    assert [event.timestamp for event in received] == [10.0, 11.0, 12.0]
    assert second.payload == session


def test_event_stream_fanout_is_failure_isolated(tmp_path) -> None:
    stream = SessionEventStream(lambda: 10.0)
    received: list[SessionEvent] = []

    def broken(_event: SessionEvent) -> None:
        raise RuntimeError("broken subscriber")

    stream.subscribe(broken)
    stream.subscribe(received.append)
    stream.publish(SessionEventType.STARTED, session_result(tmp_path))

    assert len(received) == 1


def test_event_disposer_is_idempotent(tmp_path) -> None:
    stream = SessionEventStream(lambda: 10.0)
    received: list[SessionEvent] = []
    dispose = stream.subscribe(received.append)
    dispose()
    dispose()
    stream.publish(SessionEventType.STARTED, session_result(tmp_path))
    assert received == []


def test_invalid_event_does_not_consume_a_sequence_number(tmp_path) -> None:
    timestamps = iter((float("nan"), 10.0))
    stream = SessionEventStream(lambda: next(timestamps))
    session = session_result(tmp_path)

    with pytest.raises(ValidationError):
        stream.publish(SessionEventType.STARTED, session)

    assert stream.publish(SessionEventType.STARTED, session).sequence == 1


def test_event_contract_round_trips_and_rejects_invalid_ownership(tmp_path) -> None:
    stream = SessionEventStream(lambda: 10.0)
    event = stream.publish(SessionEventType.PROCESS_STATE, session_result(tmp_path))
    payload = event.model_dump(mode="json")

    restored = SESSION_EVENT_ADAPTER.validate_json(json.dumps(payload))
    assert SESSION_EVENT_ADAPTER.dump_python(restored, mode="json") == payload

    with pytest.raises(ValidationError):
        SESSION_EVENT_ADAPTER.validate_json(json.dumps({**payload, "unexpected": True}))
    with pytest.raises(ValidationError, match="session identity"):
        SESSION_EVENT_ADAPTER.validate_json(json.dumps({**payload, "session_id": "hermes-2"}))
    with pytest.raises(ValidationError):
        SESSION_EVENT_ADAPTER.validate_json(json.dumps({**payload, "sequence": 0}))


def test_failure_event_uses_the_shared_public_error_contract(tmp_path) -> None:
    stream = SessionEventStream(lambda: 10.0)
    error = ProtocolError(parameters={"operation": "stop"}, details={"retryable": True})
    public_error = error_envelope(error).error
    event = stream.publish_failed(session_result(tmp_path), error)
    payload = SESSION_EVENT_ADAPTER.dump_python(event, mode="json")

    assert payload["type"] == "session.failed"
    assert payload["payload"]["error"] == public_error.model_dump(mode="json")


def test_unknown_event_topic_is_rejected(tmp_path) -> None:
    event = SessionEventStream(lambda: 10.0).publish(
        SessionEventType.READINESS,
        session_result(tmp_path),
    )
    payload = event.model_dump(mode="json")

    with pytest.raises(ValidationError):
        SESSION_EVENT_ADAPTER.validate_json(json.dumps({**payload, "type": "session.unknown"}))


def test_publish_is_sequence_safe_across_host_threads(tmp_path) -> None:
    stream = SessionEventStream(lambda: 10.0)
    session = session_result(tmp_path)
    observed: list[int] = []
    observed_lock = Lock()

    def observe(event: SessionEvent) -> None:
        with observed_lock:
            observed.append(event.sequence)

    stream.subscribe(observe)
    with ThreadPoolExecutor(max_workers=8) as executor:
        events = tuple(
            executor.map(
                lambda _index: stream.publish(SessionEventType.READINESS, session),
                range(128),
            )
        )

    assert sorted(event.sequence for event in events) == list(range(1, 129))
    assert sorted(observed) == list(range(1, 129))


def test_callbacks_can_reenter_subscription_without_holding_stream_lock(tmp_path) -> None:
    stream = SessionEventStream(lambda: 10.0)
    session = session_result(tmp_path)
    observed: list[int] = []

    def no_op() -> None:
        pass

    dispose = no_op

    def reenter(event: SessionEvent) -> None:
        dispose()
        stream.subscribe(lambda nested: observed.append(nested.sequence))
        observed.append(event.sequence)

    dispose = stream.subscribe(reenter)
    stream.publish(SessionEventType.READINESS, session)
    stream.publish(SessionEventType.READINESS, session)

    assert observed == [1, 2]


def test_callback_notification_releases_the_stream_lock(tmp_path) -> None:
    stream = SessionEventStream(lambda: 10.0)
    completed = Event()
    blocked: list[bool] = []

    def subscribe_from_another_host_thread() -> None:
        stream.subscribe(lambda _event: None)
        completed.set()

    def observe(_event: SessionEvent) -> None:
        thread = Thread(target=subscribe_from_another_host_thread, daemon=True)
        thread.start()
        thread.join(timeout=1)
        if not completed.is_set():
            blocked.append(True)

    stream.subscribe(observe)
    stream.publish(SessionEventType.READINESS, session_result(tmp_path))

    assert blocked == []
