"""Session-owned process, feature, and preview supervision."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from ..contracts.events import SessionEventType, SessionStateEventType
from ..contracts.sessions import SessionResult
from ..core.engine_contribution import PreviewLocator
from ..core.errors import (
    BridgeConnectionError,
    EmbedError,
    ProcessTerminationError,
    SessionStateError,
    ToqraqError,
)
from ..core.session import EngineSession
from ..core.session_readiness import ReadinessFailure, ReadinessFeature
from ..core.session_registry import SessionRegistry
from .events import SessionEventStream

DEFAULT_PROCESS_OBSERVATION_SECONDS = 0.25
MAX_PROCESS_OBSERVATION_SECONDS = 5.0
TerminalCallback = Callable[
    [EngineSession, int | None, ToqraqError | None],
    Coroutine[Any, Any, None],
]


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionSupervisionPolicy:
    """Bounded process-observation cadence for one live run."""

    process_observation_seconds: float = DEFAULT_PROCESS_OBSERVATION_SECONDS

    def __post_init__(self) -> None:
        """Reject disabled, non-finite, or excessively slow supervision."""
        value = self.process_observation_seconds
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            or not 0 < value <= MAX_PROCESS_OBSERVATION_SECONDS
        ):
            raise ValueError("session supervision interval is invalid")


class SessionSupervision:
    """Attach three focused workers to a promoted session task owner."""

    __slots__ = ("_events", "_policy", "_registry", "_terminal")

    def __init__(
        self,
        registry: SessionRegistry,
        events: SessionEventStream,
        terminal: TerminalCallback,
        policy: SessionSupervisionPolicy | None = None,
    ) -> None:
        """Retain shared state lookup, event publication, and terminal callback."""
        if not isinstance(registry, SessionRegistry):
            raise ValueError("session supervision registry is invalid")
        if not isinstance(events, SessionEventStream):
            raise ValueError("session supervision event stream is invalid")
        if not callable(terminal):
            raise ValueError("session supervision terminal callback is invalid")
        selected = policy or SessionSupervisionPolicy()
        if not isinstance(selected, SessionSupervisionPolicy):
            raise ValueError("session supervision policy is invalid")
        self._registry = registry
        self._events = events
        self._terminal = terminal
        self._policy = selected

    def start(self, session: EngineSession, preview_locator: PreviewLocator) -> None:
        """Transfer all workers into the session's strong task group."""
        if not isinstance(session, EngineSession):
            raise ValueError("supervised session is invalid")
        if not isinstance(preview_locator, PreviewLocator):
            raise ValueError("session preview locator is invalid")
        revision = session.owner.run_revision
        tasks = session.resources.tasks
        tasks.create(
            self._observe_process(session),
            name=f"toqraq-process-{revision}",
        )
        tasks.create(
            self._observe_features(session),
            name=f"toqraq-features-{revision}",
        )
        tasks.create(
            self._observe_preview(session, preview_locator),
            name=f"toqraq-preview-{revision}",
        )

    async def _observe_process(self, session: EngineSession) -> None:
        """Observe one exit, then transfer terminal handling to an owned task."""
        process = session.resources.process_tree
        if process is None:
            self._schedule_terminal(
                session,
                None,
                ProcessTerminationError(details={"reason": "process_owner_missing"}),
            )
            return
        try:
            while True:
                try:
                    exit_code = await asyncio.to_thread(
                        process.wait,
                        self._policy.process_observation_seconds,
                    )
                    break
                except TimeoutError:
                    continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._schedule_terminal(
                session,
                None,
                ProcessTerminationError(
                    details={"reason": "process_observation_failed"},
                    cause=exc,
                ),
            )
            return
        self._schedule_terminal(session, exit_code, None)

    def _schedule_terminal(
        self,
        session: EngineSession,
        exit_code: int | None,
        error: ToqraqError | None,
    ) -> None:
        """Transfer exit cleanup so it never waits on its observing predecessor."""
        revision = session.owner.run_revision
        try:
            session.resources.tasks.create(
                self._terminal(session, exit_code, error),
                name=f"toqraq-terminal-{revision}",
            )
        except ValueError:
            if not session.resources.tasks.sealed:
                raise

    async def _observe_features(self, session: EngineSession) -> None:
        """Publish authenticated ports and later withdraw them on disconnection."""
        connection = session.resources.connection
        if connection is None:
            await self._fail_features(
                session,
                BridgeConnectionError(details={"reason": "connection_owner_missing"}),
            )
            return
        try:
            ports = await connection.wait_ready()
            if not self._is_current(session):
                return
            session.publish_features(ports)
            self._publish(SessionEventType.READINESS, session)
            failure = await connection.wait_unavailable()
        except asyncio.CancelledError:
            raise
        except SessionStateError:
            return
        except ToqraqError as exc:
            failure = exc
        except Exception as exc:
            failure = BridgeConnectionError(
                details={"reason": "feature_supervision_failed"},
                cause=exc,
            )
        await self._fail_features(session, failure)

    async def _observe_preview(
        self,
        session: EngineSession,
        locator: PreviewLocator,
    ) -> None:
        """Locate one engine surface without owning its presentation."""
        runtime = session.resources.runtime
        process = session.resources.process_tree
        if runtime is None or process is None:
            await self._fail_preview(
                session,
                EmbedError(details={"reason": "preview_prerequisite_missing"}),
            )
            return
        try:
            surface = await locator.locate(
                session.project,
                runtime,
                process,
                session.resources.cancellation,
            )
            if not self._is_current(session):
                return
            session.publish_preview(surface)
            self._publish(SessionEventType.READINESS, session)
        except asyncio.CancelledError:
            raise
        except SessionStateError:
            return
        except ToqraqError as exc:
            await self._fail_preview(session, exc)
        except Exception as exc:
            await self._fail_preview(
                session,
                EmbedError(
                    details={"reason": "preview_supervision_failed"},
                    cause=exc,
                ),
            )

    async def _fail_features(self, session: EngineSession, error: ToqraqError) -> None:
        """Publish one cause-free failure for perception and control."""
        if not self._is_current(session):
            return
        failure = ReadinessFailure.from_error(
            error,
            features=frozenset({ReadinessFeature.PERCEPTION, ReadinessFeature.CONTROL}),
        )
        try:
            session.fail_features(failure)
        except SessionStateError:
            return
        self._publish(SessionEventType.READINESS, session)

    async def _fail_preview(self, session: EngineSession, error: ToqraqError) -> None:
        """Publish one cause-free preview discovery failure."""
        if not self._is_current(session):
            return
        failure = ReadinessFailure.from_error(
            error,
            features=frozenset({ReadinessFeature.PREVIEW}),
        )
        try:
            session.fail_preview(failure)
        except SessionStateError:
            return
        self._publish(SessionEventType.READINESS, session)

    def _is_current(self, session: EngineSession) -> bool:
        """Reject stale workers after a compare-and-swap replacement."""
        return self._registry.find(session.owner.session_id) is session

    def _publish(self, event_type: SessionStateEventType, session: EngineSession) -> None:
        """Publish one lock-consistent snapshot through the typed stream."""
        self._events.publish(event_type, SessionResult.from_snapshot(session.snapshot()))
