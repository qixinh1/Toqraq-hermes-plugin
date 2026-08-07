"""Stable public facts for one Hermes-owned engine run."""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import Field, RootModel, field_validator, model_validator

from ..core.preview import PreviewSurfaceKind, PreviewSurfaceSnapshot
from ..core.runtime import RuntimeIdentity
from ..core.session_capacity import MAX_CONCURRENT_GAME_SESSIONS
from ..core.session_readiness import (
    FeatureReadiness,
    FeatureReadinessSnapshot,
    ReadinessFeature,
)
from ..core.session_snapshot import EngineSessionSnapshot, SessionProcessState
from ..core.simulation_control import MAX_SIMULATION_STEP_FRAMES
from .base import ContractModel
from .errors import PublicError, public_error
from .geometry import SizeValue
from .identifiers import (
    MAX_JSON_INTEGER,
    CapabilityId,
    EngineId,
    EngineVersion,
    HermesSessionId,
    ProcessId,
    ProjectPath,
    RunRevision,
    RuntimeOpaqueId,
    RuntimeSymbolicId,
)

MAX_SESSION_CAPABILITIES = 64
MAX_UNIX_TIMESTAMP = 100_000_000_000.0


class GameStartRequest(ContractModel):
    """Start arguments whose owner comes from the Hermes tool context."""

    project_dir: ProjectPath = Field(
        description="Absolute engine-project directory; use the current workspace when implied."
    )
    engine: EngineId | None = Field(
        default=None,
        description="Exact engine ID, or omit for deterministic project detection.",
    )
    version: EngineVersion | None = Field(
        default=None,
        description="Exact public engine version, or omit for deterministic catalog selection.",
    )


class OwnedGameStartRequest(GameStartRequest):
    """HTTP start arguments with an explicit host-owned session ID."""

    hermes_session: HermesSessionId = Field(
        description="Hermes session that exclusively owns the game run."
    )

    def to_command(self) -> GameStartRequest:
        """Remove the HTTP-owned identity from the shared start command."""
        return GameStartRequest(
            project_dir=self.project_dir,
            engine=self.engine,
            version=self.version,
        )


class SessionStopRequest(ContractModel):
    """Exact run observed by a Desktop stop action."""

    run_revision: RunRevision = Field(
        description="Run revision that must still own the Hermes session."
    )


class SetPausedRequest(ContractModel):
    """Requested simulation state for the HTTP pause endpoint."""

    paused: bool = Field(description="True pauses simulation; false resumes it.")


class StepFramesRequest(ContractModel):
    """Exact bounded work requested while simulation is paused."""

    frame_count: int = Field(ge=1, le=MAX_SIMULATION_STEP_FRAMES)


class RuntimeIdentityResult(ContractModel):
    """Complete certified engine-build identity without component paths."""

    engine: EngineId
    version: RuntimeOpaqueId
    build_id: RuntimeOpaqueId
    distribution_id: RuntimeSymbolicId
    platform: RuntimeSymbolicId
    architecture: RuntimeSymbolicId

    @classmethod
    def from_core(cls, value: RuntimeIdentity) -> RuntimeIdentityResult:
        """Copy every field that distinguishes one exact managed build."""
        return cls(
            engine=value.engine_id,
            version=value.version,
            build_id=value.build_id,
            distribution_id=value.distribution_id,
            platform=value.platform,
            architecture=value.architecture,
        )


class BridgeIdentityResult(ContractModel):
    """Authenticated bridge identity and exact native capability subset."""

    id: CapabilityId
    protocol: RuntimeOpaqueId
    capabilities: tuple[CapabilityId, ...] = Field(max_length=MAX_SESSION_CAPABILITIES)

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Require one unique canonical capability sequence."""
        return _validate_capability_sequence(value)


class FeatureReadinessResult(ContractModel):
    """Independent feature state and its public-safe terminal failure."""

    state: FeatureReadiness
    error: PublicError | None = None

    @model_validator(mode="after")
    def validate_error(self) -> Self:
        """Carry an error exactly when this feature has failed."""
        if (self.state is FeatureReadiness.FAILED) != (self.error is not None):
            raise ValueError("failed feature readiness must carry exactly one error")
        return self

    @classmethod
    def from_core(
        cls,
        value: FeatureReadinessSnapshot,
        *,
        feature: ReadinessFeature,
    ) -> FeatureReadinessResult:
        """Convert one feature-bound immutable readiness snapshot."""
        failure = value.failure
        if failure is not None and feature not in failure.features:
            raise ValueError("readiness failure does not own this feature")
        return cls(
            state=value.state,
            error=public_error(failure) if failure is not None else None,
        )


class PreviewSurfaceResult(ContractModel):
    """Preview geometry with all locator and authorization facts removed."""

    kind: PreviewSurfaceKind
    viewport_size: SizeValue

    @classmethod
    def from_core(cls, value: PreviewSurfaceSnapshot) -> PreviewSurfaceResult:
        """Copy only the safe surface kind and authoritative viewport size."""
        return cls(
            kind=value.kind,
            viewport_size=SizeValue.from_core(value.viewport_size),
        )


class PreviewReadinessResult(FeatureReadinessResult):
    """Independent preview state plus its safe surface after discovery."""

    surface: PreviewSurfaceResult | None = None

    @model_validator(mode="after")
    def validate_surface(self) -> Self:
        """Expose a surface exactly when preview discovery is ready."""
        if (self.state is FeatureReadiness.READY) != (self.surface is not None):
            raise ValueError("ready preview must carry exactly one safe surface")
        return self

    @classmethod
    def from_core_preview(
        cls,
        value: FeatureReadinessSnapshot,
        *,
        surface: PreviewSurfaceSnapshot | None,
    ) -> PreviewReadinessResult:
        """Convert preview readiness and its already-redacted surface facts."""
        failure = value.failure
        if failure is not None and ReadinessFeature.PREVIEW not in failure.features:
            raise ValueError("readiness failure does not own preview")
        return cls(
            state=value.state,
            error=public_error(failure) if failure is not None else None,
            surface=PreviewSurfaceResult.from_core(surface) if surface is not None else None,
        )


class SessionResult(ContractModel):
    """Authoritative immutable public snapshot of one engine run."""

    id: HermesSessionId
    run_revision: RunRevision
    runtime: RuntimeIdentityResult
    project_dir: ProjectPath
    root_pid: ProcessId
    process_state: SessionProcessState
    alive: bool
    exit_code: int | None = Field(ge=-MAX_JSON_INTEGER, le=MAX_JSON_INTEGER)
    started_at: float = Field(ge=0, le=MAX_UNIX_TIMESTAMP, allow_inf_nan=False)
    bridge: BridgeIdentityResult
    capabilities: tuple[CapabilityId, ...] = Field(max_length=MAX_SESSION_CAPABILITIES)
    preview: PreviewReadinessResult
    perception: FeatureReadinessResult
    control: FeatureReadinessResult

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Require one unique canonical contribution capability sequence."""
        return _validate_capability_sequence(value)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        """Reject contradictory lifecycle, engine, and bridge capability facts."""
        if self.process_state in {SessionProcessState.RUNNING, SessionProcessState.PAUSED}:
            if not self.alive or self.exit_code is not None:
                raise ValueError("live session cannot carry an exit code")
        elif self.process_state in {SessionProcessState.ENDED, SessionProcessState.CRASHED}:
            if self.alive or self.exit_code is None:
                raise ValueError("terminal session must carry exactly one exit code")
        elif self.alive != (self.exit_code is None):
            raise ValueError("stopping session alive fact contradicts its exit code")
        if not set(self.bridge.capabilities).issubset(self.capabilities):
            raise ValueError("bridge capabilities must be session capabilities")
        return self

    @classmethod
    def from_snapshot(cls, snapshot: EngineSessionSnapshot) -> SessionResult:
        """Map one lock-consistent domain snapshot without reading live resources."""
        return cls(
            id=snapshot.owner.session_id,
            run_revision=snapshot.owner.run_revision,
            runtime=RuntimeIdentityResult.from_core(snapshot.runtime_identity),
            project_dir=str(snapshot.project.project_root),
            root_pid=snapshot.root_pid,
            process_state=snapshot.process_state,
            alive=snapshot.alive,
            exit_code=snapshot.exit_code,
            started_at=snapshot.started_at,
            bridge=BridgeIdentityResult(
                id=snapshot.bridge_id,
                protocol=snapshot.bridge_protocol,
                capabilities=tuple(sorted(snapshot.bridge_capability_ids)),
            ),
            capabilities=tuple(sorted(snapshot.capability_ids)),
            preview=PreviewReadinessResult.from_core_preview(
                snapshot.preview,
                surface=snapshot.preview_surface,
            ),
            perception=FeatureReadinessResult.from_core(
                snapshot.perception,
                feature=ReadinessFeature.PERCEPTION,
            ),
            control=FeatureReadinessResult.from_core(
                snapshot.control,
                feature=ReadinessFeature.CONTROL,
            ),
        )


class SessionListResult(
    RootModel[Annotated[tuple[SessionResult, ...], Field(max_length=MAX_CONCURRENT_GAME_SESSIONS)]]
):
    """Immutable public sequence of active session snapshots."""

    model_config = {"frozen": True, "strict": True}


def _validate_capability_sequence(value: tuple[str, ...]) -> tuple[str, ...]:
    """Reject duplicate or order-unstable capability sequences."""
    if len(set(value)) != len(value) or tuple(sorted(value)) != value:
        raise ValueError("capabilities must be unique and sorted")
    return value
