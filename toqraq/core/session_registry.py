"""Thread-safe compare-and-swap ownership for promoted game sessions."""

from __future__ import annotations

from threading import RLock

from .bridge import (
    MAX_BRIDGE_RUN_REVISION,
    BridgeOwnerKey,
    validate_bridge_session_id,
)
from .errors import SessionNotFoundError, SessionStateError
from .session import EngineSession


class SessionRegistry:
    """Issue monotonic run identities and reject unqualified replacement."""

    def __init__(self) -> None:
        """Create process-local state safe to call from every host event loop."""
        self._lock = RLock()
        self._sessions: dict[str, EngineSession] = {}
        self._last_issued_revision: dict[str, int] = {}

    def issue_owner(self, session_id: str) -> BridgeOwnerKey:
        """Issue the next never-reused run identity for one Hermes session."""
        validate_bridge_session_id(session_id)
        with self._lock:
            revision = self._last_issued_revision.get(session_id, 0) + 1
            if revision > MAX_BRIDGE_RUN_REVISION:
                raise SessionStateError(details={"reason": "run_revision_exhausted"})
            owner = BridgeOwnerKey(session_id=session_id, run_revision=revision)
            self._last_issued_revision[session_id] = revision
            return owner

    def compare_and_swap(
        self,
        expected: EngineSession | None,
        replacement: EngineSession,
    ) -> bool:
        """Commit only the latest issued run against the exact prior object."""
        if expected is not None and not isinstance(expected, EngineSession):
            raise ValueError("expected session is invalid")
        if not isinstance(replacement, EngineSession):
            raise ValueError("replacement session is invalid")
        session_id = replacement.owner.session_id
        if expected is not None and expected.owner.session_id != session_id:
            raise ValueError("session replacement owners differ")

        with self._lock:
            if self._last_issued_revision.get(session_id) != replacement.owner.run_revision:
                return False
            current = self._sessions.get(session_id)
            if expected is None:
                if current is not None:
                    return False
            elif current is not expected:
                return False
            elif replacement.owner.run_revision <= expected.owner.run_revision:
                raise ValueError("replacement run revision is not newer")
            elif not expected._released_registry_owner():
                return False
            with replacement._registry_commit_claim() as claimed:
                if not claimed:
                    return False
                self._sessions[session_id] = replacement
                return True

    def get(self, session_id: str) -> EngineSession:
        """Return the current exact owner or raise when it is absent."""
        validate_bridge_session_id(session_id)
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(
                parameters={"session_id": session_id},
                details={"reason": "not_owned"},
            )
        return session

    def get_owned(self, expected: BridgeOwnerKey) -> EngineSession:
        """Return only the exact current run named by an observed owner."""
        if not isinstance(expected, BridgeOwnerKey):
            raise ValueError("expected session owner is invalid")
        session = self.get(expected.session_id)
        if session.owner != expected:
            raise SessionStateError(
                parameters={"session_id": expected.session_id},
                details={
                    "reason": "run_replaced",
                    "expected_run_revision": expected.run_revision,
                    "current_run_revision": session.owner.run_revision,
                    "retryable": True,
                },
            )
        return session

    def find(self, session_id: str) -> EngineSession | None:
        """Return the current exact owner when one exists."""
        validate_bridge_session_id(session_id)
        with self._lock:
            return self._sessions.get(session_id)

    def discard_if(self, expected: EngineSession) -> bool:
        """Discard only when the same object still owns its Hermes session."""
        if not isinstance(expected, EngineSession):
            raise ValueError("expected session is invalid")
        session_id = expected.owner.session_id
        with self._lock:
            if self._sessions.get(session_id) is not expected:
                return False
            if not expected._released_registry_owner():
                return False
            del self._sessions[session_id]
            return True

    def finalize(self, session_id: str) -> None:
        """Release a completed Hermes identity's revision record."""
        validate_bridge_session_id(session_id)
        with self._lock:
            if session_id in self._sessions:
                raise SessionStateError(
                    parameters={"session_id": session_id},
                    details={"reason": "finalization_owner_remains", "retryable": True},
                )
            self._last_issued_revision.pop(session_id, None)

    def sessions(self) -> tuple[EngineSession, ...]:
        """Return one immutable point-in-time collection of current owners."""
        with self._lock:
            return tuple(self._sessions.values())
