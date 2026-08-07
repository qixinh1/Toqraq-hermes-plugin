"""Task-owned cached workspace facts for synchronous Hermes context."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Protocol

from ..contracts.geometry import SizeValue
from ..contracts.identifiers import HermesSessionId
from ..contracts.setup import ProjectState, SetupAction, SetupRequest, SetupResult
from ..core.bridge import validate_bridge_session_id


class WorkspaceSetupReader(Protocol):
    """Read-only setup operation required by workspace synchronization."""

    async def check(self, request: SetupRequest) -> SetupResult:
        """Return authoritative setup facts without mutating the project."""
        ...


@dataclass(frozen=True, slots=True)
class WorkspaceContextSnapshot:
    """Bounded recognized-project facts already observed outside the LLM hook."""

    owner_id: str
    project_path: str
    engine_id: str
    runtime_version: str | None
    setup_action: SetupAction
    viewport_size: SizeValue | None


class WorkspaceContextService:
    """Own task-keyed workspace observations and stale-update suppression."""

    def __init__(self, setup: WorkspaceSetupReader) -> None:
        """Bind the read-only setup use case used to produce observations."""
        self._setup = setup
        self._lock = threading.Lock()
        self._updates: dict[str, object] = {}
        self._snapshots: dict[str, WorkspaceContextSnapshot] = {}
        self._closed = False

    async def update(
        self,
        owner_id: HermesSessionId,
        request: SetupRequest,
    ) -> SetupResult | None:
        """Replace one task binding with the newest read-only workspace probe."""
        validate_bridge_session_id(owner_id)
        if not isinstance(request, SetupRequest):
            raise ValueError("workspace context request is invalid")
        token = self._begin_update(owner_id)
        if request.project_dir is None:
            self._settle(owner_id, token, None)
            return None
        try:
            result = await self._setup.check(request)
            snapshot = _recognized_snapshot(owner_id, result)
        except BaseException:
            self._settle(owner_id, token, None)
            raise
        self._settle(owner_id, token, snapshot)
        return result

    def find(self, owner_id: HermesSessionId) -> WorkspaceContextSnapshot | None:
        """Return the exact task's current immutable summary without I/O."""
        validate_bridge_session_id(owner_id)
        with self._lock:
            return self._snapshots.get(owner_id)

    def clear(self, owner_id: HermesSessionId) -> None:
        """Invalidate one task and prevent its in-flight probes from publishing."""
        validate_bridge_session_id(owner_id)
        with self._lock:
            self._updates.pop(owner_id, None)
            self._snapshots.pop(owner_id, None)

    def close(self) -> None:
        """Seal the owner and invalidate every current or in-flight binding."""
        with self._lock:
            self._closed = True
            self._updates.clear()
            self._snapshots.clear()

    def _begin_update(self, owner_id: str) -> object:
        """Withdraw old facts before any potentially slow project work begins."""
        with self._lock:
            if self._closed:
                raise RuntimeError("workspace context service is closed")
            token = object()
            self._updates[owner_id] = token
            self._snapshots.pop(owner_id, None)
            return token

    def _settle(
        self,
        owner_id: str,
        token: object,
        snapshot: WorkspaceContextSnapshot | None,
    ) -> None:
        """Finish only the task's current probe and release its identity token."""
        with self._lock:
            if self._closed or self._updates.get(owner_id) is not token:
                return
            self._updates.pop(owner_id)
            if snapshot is None:
                self._snapshots.pop(owner_id, None)
            else:
                self._snapshots[owner_id] = snapshot


def _recognized_snapshot(
    owner_id: str,
    result: SetupResult,
) -> WorkspaceContextSnapshot | None:
    """Project only one ready recognized project into the context cache."""
    project = result.project
    engine = result.engine
    if project.state is not ProjectState.READY or project.path is None or engine is None:
        return None
    runtime = engine.runtime
    return WorkspaceContextSnapshot(
        owner_id=owner_id,
        project_path=project.path,
        engine_id=engine.id,
        runtime_version=runtime.version if runtime is not None else None,
        setup_action=result.action,
        viewport_size=project.viewport_size,
    )
