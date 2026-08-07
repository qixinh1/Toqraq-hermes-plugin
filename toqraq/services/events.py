"""Owned sequencing and fan-out for session event contracts."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from contextlib import suppress
from threading import RLock

from ..contracts.errors import error_envelope
from ..contracts.events import (
    SessionEvent,
    SessionEventType,
    SessionFailedEvent,
    SessionFailurePayload,
    SessionStateEvent,
    SessionStateEventType,
)
from ..contracts.identifiers import MAX_JSON_INTEGER
from ..contracts.sessions import SessionResult
from ..core.errors import ToqraqError
from ..core.failure_diagnostics import failure_diagnostic
from ..core.trace import error_trace_id

logger = logging.getLogger(__name__)
EventCallback = Callable[[SessionEvent], None]
Clock = Callable[[], float]


class SessionEventStream:
    """Own monotonic per-Hermes-session events and synchronous subscribers."""

    def __init__(self, clock: Clock = time.time) -> None:
        """Initialize an empty stream with an injectable Unix clock."""
        self._clock = clock
        self._lock = RLock()
        self._sequences: dict[str, int] = {}
        self._subscribers: list[EventCallback] = []

    def subscribe(self, callback: EventCallback) -> Callable[[], None]:
        """Subscribe to every typed event and return an idempotent disposer."""
        with self._lock:
            self._subscribers.append(callback)

        def dispose() -> None:
            with self._lock, suppress(ValueError):
                self._subscribers.remove(callback)

        return dispose

    def publish(self, event_type: SessionStateEventType, session: SessionResult) -> SessionEvent:
        """Publish a normal session snapshot under the next sequence."""
        with self._lock:
            sequence = self._next_sequence(session.id)
            event = SessionStateEvent(
                session_id=session.id,
                sequence=sequence,
                timestamp=self._clock(),
                type=event_type,
                payload=session,
            )
            self._sequences[session.id] = sequence
            subscribers = tuple(self._subscribers)
        self._notify(event, subscribers)
        return event

    def publish_failed(
        self,
        session: SessionResult,
        error: ToqraqError,
    ) -> SessionEvent:
        """Publish a lifecycle failure with the shared public error object."""
        with self._lock:
            sequence = self._next_sequence(session.id)
            event = SessionFailedEvent(
                session_id=session.id,
                sequence=sequence,
                timestamp=self._clock(),
                type=SessionEventType.FAILED,
                payload=SessionFailurePayload(
                    session=session,
                    error=error_envelope(error).error,
                ),
            )
            self._sequences[session.id] = sequence
            subscribers = tuple(self._subscribers)
        self._notify(event, subscribers)
        return event

    def finalize(self, session_id: str) -> None:
        """Release sequence ownership after Hermes seals the session ID."""
        with self._lock:
            self._sequences.pop(session_id, None)

    def _next_sequence(self, session_id: str) -> int:
        """Return the next safe sequence without committing a failed event."""
        sequence = self._sequences.get(session_id, 0) + 1
        if sequence > MAX_JSON_INTEGER:
            raise OverflowError("session event sequence exhausted")
        return sequence

    def _notify(
        self,
        event: SessionEvent,
        subscribers: tuple[EventCallback, ...],
    ) -> None:
        """Deliver one immutable event with subscriber failure isolation."""
        for callback in subscribers:
            try:
                callback(event)
            except Exception as exc:
                _log_failure(exc)


def _log_failure(exception: BaseException) -> None:
    """Log a bounded isolated-subscriber failure."""
    diagnostic = failure_diagnostic(exception)
    logger.error(
        "unexpected event subscriber failure trace_id=%s exception_type=%s stack_locations=%s",
        error_trace_id(),
        diagnostic.exception_type,
        ",".join(diagnostic.stack_locations),
    )
