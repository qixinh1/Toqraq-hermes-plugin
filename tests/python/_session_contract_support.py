"""Immutable domain snapshots used by public session-contract tests."""

from __future__ import annotations

from pathlib import Path

from toqraq.contracts.sessions import SessionResult
from toqraq.core.bridge import BridgeOwnerKey
from toqraq.core.capability_ids import (
    OBSERVE_HIERARCHY_CAPABILITY_ID,
    PLAY_PAUSE_CAPABILITY_ID,
    PREVIEW_DISPLAY_CAPABILITY_ID,
)
from toqraq.core.engine_contribution import ProjectDescription
from toqraq.core.geometry import Size
from toqraq.core.preview import PreviewSurfaceKind, PreviewSurfaceSnapshot
from toqraq.core.runtime import RuntimeIdentity
from toqraq.core.session_readiness import FeatureReadiness, FeatureReadinessSnapshot
from toqraq.core.session_snapshot import EngineSessionSnapshot, SessionProcessState

SESSION_CAPABILITIES = frozenset(
    {
        OBSERVE_HIERARCHY_CAPABILITY_ID,
        PLAY_PAUSE_CAPABILITY_ID,
        PREVIEW_DISPLAY_CAPABILITY_ID,
    }
)
BRIDGE_CAPABILITIES = frozenset(
    {
        OBSERVE_HIERARCHY_CAPABILITY_ID,
        PLAY_PAUSE_CAPABILITY_ID,
    }
)


def session_snapshot(
    project_root: Path,
    *,
    process_state: SessionProcessState = SessionProcessState.RUNNING,
    exit_code: int | None = None,
    preview_state: FeatureReadiness = FeatureReadiness.READY,
) -> EngineSessionSnapshot:
    """Build one complete lock-consistent run snapshot."""
    preview_surface = None
    if preview_state is FeatureReadiness.READY:
        preview_surface = PreviewSurfaceSnapshot(
            kind=PreviewSurfaceKind.NATIVE_WINDOW,
            viewport_size=Size(width=960, height=540),
        )
    return EngineSessionSnapshot(
        owner=BridgeOwnerKey(session_id="hermes-1", run_revision=7),
        project=ProjectDescription(
            engine_id="godot",
            project_root=project_root,
            marker_path=project_root / "project.godot",
            confidence=100,
            declared_version="4.7.1-stable",
        ),
        runtime_identity=RuntimeIdentity(
            engine_id="godot",
            version="4.7.1-stable",
            build_id="toqraq.windows.x86_64.release",
            distribution_id="toqraq.godot.windows.x86_64",
            platform="windows",
            architecture="x86_64",
        ),
        bridge_id="toqraq.godot.bridge",
        bridge_protocol="1.0",
        capability_ids=SESSION_CAPABILITIES,
        bridge_capability_ids=BRIDGE_CAPABILITIES,
        root_pid=4_242,
        started_at=1_722_000_000.25,
        process_state=process_state,
        exit_code=exit_code,
        preview=FeatureReadinessSnapshot(state=preview_state),
        preview_surface=preview_surface,
        perception=FeatureReadinessSnapshot(state=FeatureReadiness.READY),
        control=FeatureReadinessSnapshot(state=FeatureReadiness.READY),
    )


def session_result(project_root: Path) -> SessionResult:
    """Map the standard test snapshot through the sole public converter."""
    return SessionResult.from_snapshot(session_snapshot(project_root))
