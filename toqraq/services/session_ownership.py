"""Synchronized ownership records for unfinished session lifecycle work."""

from __future__ import annotations

from collections.abc import Iterable
from threading import RLock

from ..core.bridge import BridgeOwnerKey, validate_bridge_session_id
from ..core.bridge_launch import BridgeLaunchBootstrap
from ..core.errors import SessionStateError
from ..core.pending_start import PendingStart
from ..core.run_resources import RunCleanupPolicy
from ..core.session import EngineSession
from ..core.session_capacity import MAX_CONCURRENT_GAME_SESSIONS
from .session_cleanup import pending_cleanup_error, release_orphan_session


class SessionOwnership:
    """Retain every pending or unregistered run until its cleanup succeeds."""

    __slots__ = (
        "_cleanup_policy",
        "_closing",
        "_finalized",
        "_lock",
        "_orphans",
        "_pending",
        "_reserved_session_ids",
    )

    def __init__(self, cleanup_policy: RunCleanupPolicy) -> None:
        """Create the process-local owner ledger for one lifecycle service."""
        if not isinstance(cleanup_policy, RunCleanupPolicy):
            raise ValueError("session cleanup policy is invalid")
        self._cleanup_policy = cleanup_policy
        self._lock = RLock()
        self._pending: dict[str, PendingStart] = {}
        self._orphans: dict[BridgeOwnerKey, EngineSession] = {}
        self._finalized: set[str] = set()
        self._reserved_session_ids: set[str] = set()
        self._closing = False

    def reserve_start(self, session_id: str) -> None:
        """Reserve one public-list slot before a new session can acquire resources."""
        validate_bridge_session_id(session_id)
        with self._lock:
            self._require_start_allowed_locked(session_id)
            if session_id in self._reserved_session_ids:
                return
            if len(self._reserved_session_ids) >= MAX_CONCURRENT_GAME_SESSIONS:
                raise SessionStateError(
                    details={"reason": "session_capacity_exhausted", "retryable": True}
                )
            self._reserved_session_ids.add(session_id)

    def release_if_idle(self, session_id: str, *, active: bool) -> None:
        """Release a slot only after no active or unfinished owner remains."""
        with self._lock:
            if active or session_id in self._pending:
                return
            if any(owner.session_id == session_id for owner in self._orphans):
                return
            self._reserved_session_ids.discard(session_id)

    def create_pending(self, bootstrap: BridgeLaunchBootstrap) -> PendingStart:
        """Publish a pending acquisition for finalization and shutdown cancellation."""
        if not isinstance(bootstrap, BridgeLaunchBootstrap):
            raise ValueError("bridge launch bootstrap is invalid")
        pending = PendingStart(bootstrap, self._cleanup_policy)
        with self._lock:
            self._require_start_allowed_locked(pending.owner.session_id)
            if pending.owner.session_id not in self._reserved_session_ids:
                raise SessionStateError(details={"reason": "session_capacity_not_reserved"})
            if pending.owner.session_id in self._pending:
                raise SessionStateError(details={"reason": "pending_start_already_owned"})
            self._pending[pending.owner.session_id] = pending
        return pending

    def remove_pending(self, pending: PendingStart) -> None:
        """Release a settled acquisition only when this owner still records it."""
        session_id = pending.owner.session_id
        with self._lock:
            if self._pending.get(session_id) is pending:
                del self._pending[session_id]

    async def retry_pending(self, session_id: str) -> None:
        """Retry retained pending cleanup before another lifecycle mutation."""
        with self._lock:
            pending = self._pending.get(session_id)
        if pending is None:
            return
        try:
            await pending.close()
        except BaseException as exc:
            raise pending_cleanup_error(pending, exc) from exc
        self.remove_pending(pending)

    def retain_orphan(self, session: EngineSession) -> None:
        """Retain a promoted run before its first cleanup await."""
        with self._lock:
            if session.owner.session_id not in self._reserved_session_ids:
                raise SessionStateError(details={"reason": "session_capacity_not_reserved"})
            self._orphans[session.owner] = session

    async def release_orphan(self, session: EngineSession) -> None:
        """Release one promoted run that never entered the active registry."""
        await release_orphan_session(session)
        with self._lock:
            self._orphans.pop(session.owner, None)

    async def release_orphans(self, session_id: str) -> list[Exception]:
        """Attempt each independently owned orphan for one Hermes session."""
        with self._lock:
            orphans = tuple(
                session
                for owner, session in self._orphans.items()
                if owner.session_id == session_id
            )
        failures: list[Exception] = []
        for orphan in orphans:
            try:
                await self.release_orphan(orphan)
            except Exception as exc:
                failures.append(exc)
        return failures

    def finalize(self, session_id: str) -> None:
        """Seal one Hermes identity and immediately cancel its pending owner."""
        validate_bridge_session_id(session_id)
        with self._lock:
            self._finalized.add(session_id)
            pending = self._pending.get(session_id)
            if pending is not None:
                pending.cancel()

    def complete_finalization(self, session_id: str) -> None:
        """Release a finalized identity's capacity only after every owner drained."""
        with self._lock:
            if session_id in self._pending or any(
                owner.session_id == session_id for owner in self._orphans
            ):
                raise SessionStateError(
                    parameters={"session_id": session_id},
                    details={"reason": "finalization_owners_remain", "retryable": True},
                )
            self._reserved_session_ids.discard(session_id)

    def release_close_tombstones(self) -> None:
        """Discard finalized identity records after irreversible plugin closure."""
        with self._lock:
            if not self._closing:
                raise SessionStateError(details={"reason": "plugin_close_not_started"})
            if self._pending or self._orphans:
                raise SessionStateError(
                    details={"reason": "plugin_close_owners_remain", "retryable": True}
                )
            self._finalized.clear()
            self._reserved_session_ids.clear()

    def begin_close(self, active_session_ids: Iterable[str]) -> None:
        """Seal all known identities and cancel every pending acquisition."""
        with self._lock:
            self._closing = True
            self._finalized.update(active_session_ids)
            self._finalized.update(self._pending)
            self._finalized.update(owner.session_id for owner in self._orphans)
            for pending in self._pending.values():
                pending.cancel()

    def close_session_ids(self) -> tuple[str, ...]:
        """Return the complete owned shutdown set in deterministic order."""
        with self._lock:
            session_ids = set(self._finalized)
            session_ids.update(self._pending)
            session_ids.update(owner.session_id for owner in self._orphans)
        return tuple(sorted(session_ids))

    @property
    def has_unsettled(self) -> bool:
        """Report whether failed-start cleanup remains strongly owned."""
        with self._lock:
            return bool(self._pending or self._orphans)

    def require_start_allowed(self, session_id: str) -> None:
        """Reject start work after plugin or Hermes-session finalization."""
        with self._lock:
            self._require_start_allowed_locked(session_id)

    def _require_start_allowed_locked(self, session_id: str) -> None:
        """Check lifecycle admission while the ownership lock is held."""
        if self._closing:
            raise SessionStateError(
                parameters={"session_id": session_id},
                details={"reason": "plugin_closing"},
            )
        if session_id in self._finalized:
            raise SessionStateError(
                parameters={"session_id": session_id},
                details={"reason": "session_finalized"},
            )
