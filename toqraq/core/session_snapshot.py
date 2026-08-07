"""Immutable process vocabulary and safe promoted-session snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .bridge import BridgeOwnerKey
from .engine_contribution import ProjectDescription
from .preview import PreviewSurfaceSnapshot
from .runtime import RuntimeIdentity
from .session_readiness import FeatureReadinessSnapshot


class SessionProcessState(StrEnum):
    """Process states retained after a pending start is promoted."""

    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ENDED = "ended"
    CRASHED = "crashed"


@dataclass(frozen=True, slots=True, kw_only=True)
class EngineSessionSnapshot:
    """Immutable run facts that remain valid after resource release."""

    owner: BridgeOwnerKey
    project: ProjectDescription
    runtime_identity: RuntimeIdentity
    bridge_id: str
    bridge_protocol: str
    capability_ids: frozenset[str]
    bridge_capability_ids: frozenset[str]
    root_pid: int
    started_at: float
    process_state: SessionProcessState
    exit_code: int | None
    preview: FeatureReadinessSnapshot
    preview_surface: PreviewSurfaceSnapshot | None
    perception: FeatureReadinessSnapshot
    control: FeatureReadinessSnapshot

    @property
    def alive(self) -> bool:
        """Return whether no exit has been observed for a non-terminal state."""
        return self.exit_code is None and self.process_state in {
            SessionProcessState.RUNNING,
            SessionProcessState.PAUSED,
            SessionProcessState.STOPPING,
        }
