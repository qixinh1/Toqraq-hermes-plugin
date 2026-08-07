"""Hermes-owned engine session lifecycle use cases."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from ..contracts.events import SessionEventType
from ..contracts.identifiers import HermesSessionId
from ..contracts.sessions import (
    GameStartRequest,
    SessionListResult,
    SessionResult,
)
from ..core.bridge import (
    COMMON_BRIDGE_LIMITS,
    BridgeHandshakeExpectation,
    BridgeOwnerKey,
)
from ..core.bridge_launch import BridgeLaunchBootstrap
from ..core.errors import (
    ProcessTerminationError,
    SessionCleanupError,
    SessionStateError,
    ToqraqError,
)
from ..core.pending_start import PendingStart
from ..core.process_tree import ProcessEnvironment, ProcessTreeLauncher
from ..core.run_resources import RunCleanupPolicy
from ..core.runtime import HostRuntimeTarget
from ..core.runtime_features import RuntimeFeatureConnectionFactory
from ..core.session import EngineSession
from ..core.session_registry import SessionRegistry
from .events import SessionEventStream
from .project_runtime_selection import ProjectRuntimeSelectionService
from .session_cleanup import (
    close_process_launcher,
    release_registered_session,
    start_rollback_error,
)
from .session_gate import SessionOperationGate
from .session_ownership import SessionOwnership
from .session_selection import require_start_selection, start_selection_input
from .session_start import SessionStartTransaction, new_bridge_credential
from .session_supervision import SessionSupervision, SessionSupervisionPolicy

Clock = Callable[[], float]
CredentialFactory = Callable[[], str]
ExceptionList = list[Exception]
SESSION_SERVICE_CLOSE_GATE_KEY = "toqraq.plugin.lifecycle"


class SessionService:
    """Own one exact game run and every pending acquisition per Hermes session."""

    __slots__ = (
        "_clock",
        "_close_gate",
        "_connection_factory",
        "_credential_factory",
        "_environment",
        "_events",
        "_gate",
        "_host",
        "_launcher",
        "_launcher_closed",
        "_ownership",
        "_registry",
        "_selection",
        "_supervision",
    )

    def __init__(
        self,
        *,
        selection: ProjectRuntimeSelectionService,
        registry: SessionRegistry,
        events: SessionEventStream,
        host: HostRuntimeTarget,
        connection_factory: RuntimeFeatureConnectionFactory,
        launcher: ProcessTreeLauncher,
        environment: ProcessEnvironment,
        gate: SessionOperationGate | None = None,
        cleanup_policy: RunCleanupPolicy | None = None,
        supervision_policy: SessionSupervisionPolicy | None = None,
        credential_factory: CredentialFactory | None = None,
        clock: Clock = time.time,
    ) -> None:
        """Compose concrete external owners behind transport-neutral ports."""
        if not isinstance(selection, ProjectRuntimeSelectionService):
            raise ValueError("session project-runtime selection is invalid")
        if not isinstance(registry, SessionRegistry):
            raise ValueError("session registry is invalid")
        if not isinstance(events, SessionEventStream):
            raise ValueError("session event stream is invalid")
        if not isinstance(host, HostRuntimeTarget):
            raise ValueError("session host runtime target is invalid")
        if not isinstance(connection_factory, RuntimeFeatureConnectionFactory):
            raise ValueError("session feature connection factory is invalid")
        if not isinstance(launcher, ProcessTreeLauncher):
            raise ValueError("session process launcher is invalid")
        if not isinstance(environment, ProcessEnvironment):
            raise ValueError("session process environment is invalid")
        selected_gate = gate or SessionOperationGate()
        selected_cleanup = cleanup_policy or RunCleanupPolicy()
        if not isinstance(selected_gate, SessionOperationGate):
            raise ValueError("session operation gate is invalid")
        if not isinstance(selected_cleanup, RunCleanupPolicy):
            raise ValueError("session cleanup policy is invalid")
        selected_credential = credential_factory or new_bridge_credential
        if not callable(selected_credential) or not callable(clock):
            raise ValueError("session factories are invalid")
        self._selection = selection
        self._registry = registry
        self._events = events
        self._host = host
        self._connection_factory = connection_factory
        self._launcher = launcher
        self._environment = environment
        self._gate = selected_gate
        self._close_gate = SessionOperationGate()
        self._credential_factory = selected_credential
        self._clock = clock
        self._ownership = SessionOwnership(selected_cleanup)
        self._launcher_closed = False
        self._supervision = SessionSupervision(
            registry,
            events,
            self._on_terminal,
            supervision_policy,
        )

    async def start(
        self,
        session_id: HermesSessionId,
        request: GameStartRequest,
    ) -> SessionResult:
        """Prepare before replacement, then atomically commit one new run."""
        lease = await self._gate.acquire(session_id)
        async with lease:
            return await self._start_locked(session_id, request)

    async def _start_locked(self, session_id: str, request: GameStartRequest) -> SessionResult:
        """Execute one complete start transaction under the keyed operation gate."""
        self._ownership.require_start_allowed(session_id)
        await self._ownership.retry_pending(session_id)
        selection_input = start_selection_input(request, self._host)
        selected = await asyncio.to_thread(self._selection.select, selection_input)
        ready = require_start_selection(selected)
        self._ownership.require_start_allowed(session_id)
        self._ownership.reserve_start(session_id)
        try:
            owner = self._registry.issue_owner(session_id)
            credential = self._credential_factory()
            pending = self._ownership.create_pending(
                BridgeLaunchBootstrap(
                    credential=credential,
                    session_id=owner.session_id,
                    run_revision=owner.run_revision,
                ),
            )
        except BaseException:
            self._release_capacity_if_idle(session_id)
            raise
        existing: EngineSession | None = None
        promoted: EngineSession | None = None
        committed = False
        try:
            transaction = SessionStartTransaction(
                selection=ready,
                pending=pending,
                expectation=BridgeHandshakeExpectation(
                    credential=credential,
                    owner=owner,
                    release=ready.release,
                    limits=COMMON_BRIDGE_LIMITS,
                ),
                connection_factory=self._connection_factory,
                launcher=self._launcher,
                environment=self._environment,
            )
            await transaction.prepare()
            self._ownership.require_start_allowed(session_id)
            existing = self._registry.find(session_id)
            if existing is not None:
                await self._release_registered(existing, discard=False, publish=True)
            self._ownership.require_start_allowed(session_id)
            promoted = await transaction.launch(self._clock)
            self._ownership.require_start_allowed(session_id)
            if not self._registry.compare_and_swap(existing, promoted):
                raise SessionStateError(
                    parameters={"session_id": session_id},
                    details={"reason": "session_commit_rejected", "retryable": True},
                )
            committed = True
            self._ownership.remove_pending(pending)
            self._supervision.start(promoted, ready.contribution.preview_locator)
            result = SessionResult.from_snapshot(promoted.snapshot())
            self._events.publish(SessionEventType.STARTED, result)
            return result
        except BaseException as primary:
            cleanup = await self._rollback_start(
                pending=pending,
                promoted=promoted,
                committed=committed,
                existing=existing,
            )
            self._release_capacity_if_idle(session_id)
            if cleanup is not None:
                raise start_rollback_error(pending, primary, cleanup) from None
            raise

    async def stop(
        self,
        session_id: HermesSessionId,
        *,
        expected_owner: BridgeOwnerKey | None = None,
    ) -> SessionResult:
        """Release the current run, optionally only for one observed owner."""
        if expected_owner is not None and (
            not isinstance(expected_owner, BridgeOwnerKey)
            or expected_owner.session_id != session_id
        ):
            raise ValueError("expected stop owner is invalid")
        lease = await self._gate.acquire(session_id)
        async with lease:
            await self._ownership.retry_pending(session_id)
            session = (
                self._registry.get(session_id)
                if expected_owner is None
                else self._registry.get_owned(expected_owner)
            )
            result = await self._release_registered(session, discard=True, publish=True)
            self._release_capacity_if_idle(session_id)
            return result

    async def finalize(self, session_id: HermesSessionId) -> None:
        """Seal one Hermes identity and drain all of its resource owners."""
        self._ownership.finalize(session_id)
        lease = await self._gate.acquire(session_id)
        async with lease:
            failures = await self._drain_session(session_id)
            if failures:
                raise SessionCleanupError(
                    parameters={"session_id": session_id},
                    details={"reason": "finalization_incomplete", "retryable": True},
                    cause=ExceptionGroup("session finalization cleanup failed", failures),
                )
            self._registry.finalize(session_id)
            self._ownership.complete_finalization(session_id)
            self._events.finalize(session_id)

    def get(self, session_id: HermesSessionId) -> SessionResult:
        """Return one authoritative current snapshot."""
        return SessionResult.from_snapshot(self._registry.get(session_id).snapshot())

    def find(self, session_id: HermesSessionId) -> SessionResult | None:
        """Return one authoritative snapshot when this session owns a run."""
        session = self._registry.find(session_id)
        return SessionResult.from_snapshot(session.snapshot()) if session is not None else None

    def list(self) -> SessionListResult:
        """Return current owned sessions in deterministic Hermes-ID order."""
        sessions = sorted(self._registry.sessions(), key=lambda value: value.owner.session_id)
        return SessionListResult(
            root=tuple(SessionResult.from_snapshot(session.snapshot()) for session in sessions)
        )

    def begin_close(self) -> None:
        """Reject new starts and synchronously cancel every pending acquisition."""
        self._ownership.begin_close(
            session.owner.session_id for session in self._registry.sessions()
        )

    async def close(self) -> None:
        """Drain every owner, then release the process launcher exactly once."""
        lease = await self._close_gate.acquire(SESSION_SERVICE_CLOSE_GATE_KEY)
        async with lease:
            await self._close_locked()

    async def _close_locked(self) -> None:
        """Perform one serialized, idempotent shutdown attempt."""
        self.begin_close()
        results = await asyncio.gather(
            *(self.finalize(session_id) for session_id in self._ownership.close_session_ids()),
            return_exceptions=True,
        )
        failures = [result for result in results if isinstance(result, BaseException)]
        if self._registry.sessions() or self._ownership.has_unsettled:
            failures.append(
                SessionCleanupError(
                    details={"reason": "plugin_session_owners_remain", "retryable": True}
                )
            )
        if not failures and not self._launcher_closed:
            try:
                await close_process_launcher(self._launcher)
            except Exception as exc:
                failures.append(exc)
            else:
                self._launcher_closed = True
        if failures:
            raise BaseExceptionGroup("Toqraq session shutdown failed", failures)
        self._ownership.release_close_tombstones()

    async def _on_terminal(
        self,
        session: EngineSession,
        exit_code: int | None,
        observation_error: ToqraqError | None,
    ) -> None:
        """Serialize natural exit or observation failure with explicit cleanup."""
        session_id = session.owner.session_id
        lease = await self._gate.acquire(session_id)
        async with lease:
            if self._registry.find(session_id) is not session:
                return
            if observation_error is not None:
                self._events.publish_failed(
                    SessionResult.from_snapshot(session.snapshot()),
                    observation_error,
                )
            else:
                try:
                    if exit_code is None:
                        raise ValueError("process exit code is absent")
                    session.record_exit(exit_code)
                except Exception as exc:
                    observation_error = ProcessTerminationError(
                        details={"reason": "process_exit_invalid"},
                        cause=exc,
                    )
                    self._events.publish_failed(
                        SessionResult.from_snapshot(session.snapshot()),
                        observation_error,
                    )
                else:
                    self._events.publish(
                        SessionEventType.PROCESS_STATE,
                        SessionResult.from_snapshot(session.snapshot()),
                    )
            try:
                await self._release_registered(session, discard=True, publish=True)
            except SessionCleanupError:
                return
            self._release_capacity_if_idle(session_id)

    async def _release_registered(
        self,
        session: EngineSession,
        *,
        discard: bool,
        publish: bool,
    ) -> SessionResult:
        """Delegate cleanup with this service's registry and event owners."""
        return await release_registered_session(
            session,
            registry=self._registry,
            events=self._events,
            discard=discard,
            publish=publish,
        )

    async def _rollback_start(
        self,
        *,
        pending: PendingStart,
        promoted: EngineSession | None,
        committed: bool,
        existing: EngineSession | None,
    ) -> BaseException | None:
        """Retain and settle every unpublished or partially published owner."""
        failures: list[BaseException] = []
        if promoted is not None:
            self._ownership.remove_pending(pending)
            if committed:
                try:
                    await self._release_registered(promoted, discard=True, publish=False)
                except BaseException as exc:
                    failures.append(exc)
            else:
                self._ownership.retain_orphan(promoted)
                try:
                    await self._ownership.release_orphan(promoted)
                except BaseException as exc:
                    failures.append(exc)
        else:
            try:
                await self._ownership.retry_pending(pending.owner.session_id)
            except BaseException as exc:
                failures.append(exc)
        if (
            existing is not None
            and self._registry.find(existing.owner.session_id) is existing
            and existing.resources.empty
        ):
            self._registry.discard_if(existing)
        if not failures:
            return None
        return BaseExceptionGroup("session start rollback cleanup failed", failures)

    async def _drain_session(self, session_id: str) -> ExceptionList:
        """Attempt every independent owner for one finalized Hermes session."""
        failures: list[Exception] = []
        try:
            await self._ownership.retry_pending(session_id)
        except Exception as exc:
            failures.append(exc)
        session = self._registry.find(session_id)
        if session is not None:
            try:
                await self._release_registered(session, discard=True, publish=True)
            except Exception as exc:
                failures.append(exc)
        failures.extend(await self._ownership.release_orphans(session_id))
        return failures

    def _release_capacity_if_idle(self, session_id: str) -> None:
        """Return a public-list slot after this identity owns no live work."""
        self._ownership.release_if_idle(
            session_id,
            active=self._registry.find(session_id) is not None,
        )
