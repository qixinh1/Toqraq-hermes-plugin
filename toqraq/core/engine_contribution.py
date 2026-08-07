"""Engine contribution values and ports for exact runtime launch planning."""

from __future__ import annotations

from dataclasses import dataclass
from inspect import iscoroutinefunction
from pathlib import Path
from threading import Event
from typing import Protocol, runtime_checkable

from .absolute_path import require_absolute_normalized_path
from .bridge import BridgeListenerEndpoint
from .geometry import Size
from .preview import PreviewSurface
from .process_tree import ProcessBootstrap, ProcessEnvironment, ProcessLaunch, ProcessTree
from .project_inventory import ProjectInventoryReader
from .runtime import (
    PreparedRuntime,
    RuntimeRelease,
    validate_engine_id,
    validate_opaque_runtime_id,
)

_MAX_DETECTION_CONFIDENCE = 100


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectDescription:
    """Bounded engine-owned facts proving one recognized project root."""

    engine_id: str
    project_root: Path
    marker_path: Path
    confidence: int
    declared_version: str | None = None
    display_size_hint: Size | None = None

    def __post_init__(self) -> None:
        """Reject ambiguous identity, paths, confidence, and version facts."""
        validate_engine_id(self.engine_id)
        require_absolute_normalized_path(self.project_root, "project root")
        require_absolute_normalized_path(self.marker_path, "project marker")
        if self.marker_path == self.project_root or not self.marker_path.is_relative_to(
            self.project_root
        ):
            raise ValueError("project marker must be below the project root")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, int)
            or not 1 <= self.confidence <= _MAX_DETECTION_CONFIDENCE
        ):
            raise ValueError("project confidence is invalid")
        if self.declared_version is not None:
            validate_opaque_runtime_id(self.declared_version)
        if self.display_size_hint is not None and not isinstance(self.display_size_hint, Size):
            raise ValueError("project display-size hint is invalid")


@runtime_checkable
class ProjectProbe(Protocol):
    """Side-effect-free recognition of one engine's project format."""

    @property
    def engine_id(self) -> str:
        """Return the contribution engine identifier."""
        ...

    def probe(self, project_root: Path) -> ProjectDescription | None:
        """Return bounded project facts, or None when the root is not recognized."""
        ...


@dataclass(frozen=True, slots=True, kw_only=True)
class EngineProjectFormat:
    """One engine identity with side-effect-free project perception ports."""

    engine_id: str
    project_probe: ProjectProbe
    project_inventory_reader: ProjectInventoryReader

    def __post_init__(self) -> None:
        """Reject missing, asynchronous, or cross-engine perception ports."""
        validate_engine_id(self.engine_id)
        if not isinstance(self.project_probe, ProjectProbe):
            raise ValueError("engine project-format probe is invalid")
        if not isinstance(self.project_inventory_reader, ProjectInventoryReader):
            raise ValueError("engine project-format inventory reader is invalid")
        if iscoroutinefunction(self.project_inventory_reader.scan):
            raise ValueError("engine project-format inventory reader must be synchronous")
        if (
            self.project_probe.engine_id != self.engine_id
            or self.project_inventory_reader.engine_id != self.engine_id
        ):
            raise ValueError("engine project-format ports have mismatched identities")


@runtime_checkable
class RuntimeCatalog(Protocol):
    """Read-only certified releases for one engine contribution."""

    @property
    def engine_id(self) -> str:
        """Return the contribution engine identifier."""
        ...

    def releases(self, project: ProjectDescription) -> tuple[RuntimeRelease, ...]:
        """Return exact selectable releases in deterministic catalog order."""
        ...


@runtime_checkable
class RuntimeProvisioner(Protocol):
    """Prepare one already-resolved certified runtime release."""

    @property
    def engine_id(self) -> str:
        """Return the contribution engine identifier."""
        ...

    def prepare(self, release: RuntimeRelease, cancellation: Event) -> PreparedRuntime:
        """Prepare exactly this release without selecting another runtime."""
        ...


@runtime_checkable
class GameLaunchPlanner(Protocol):
    """Engine-owned conversion of exact launch facts into a platform command."""

    @property
    def engine_id(self) -> str:
        """Return the contribution engine identifier."""
        ...

    def plan(
        self,
        project: ProjectDescription,
        runtime: PreparedRuntime,
        endpoint: BridgeListenerEndpoint,
        environment: ProcessEnvironment,
        bootstrap: ProcessBootstrap,
    ) -> ProcessLaunch:
        """Build one immutable command without starting or owning a process."""
        ...


@runtime_checkable
class PreviewLocator(Protocol):
    """Engine-owned discovery of one playable native or web surface."""

    @property
    def engine_id(self) -> str:
        """Return the contribution engine identifier."""
        ...

    async def locate(
        self,
        project: ProjectDescription,
        runtime: PreparedRuntime,
        process_tree: ProcessTree,
        cancellation: Event,
    ) -> PreviewSurface:
        """Return one surface without positioning or rendering it."""
        ...


@dataclass(frozen=True, slots=True, kw_only=True)
class EngineContribution:
    """Explicit composition of the engine ports with current real value types."""

    project_format: EngineProjectFormat
    runtime_catalog: RuntimeCatalog
    runtime_provisioner: RuntimeProvisioner
    game_launch_planner: GameLaunchPlanner
    preview_locator: PreviewLocator

    def __post_init__(self) -> None:
        """Reject missing ports and cross-engine contribution mismatches."""
        if not isinstance(self.project_format, EngineProjectFormat):
            raise ValueError("engine contribution project format is invalid")
        ports = (
            (self.runtime_catalog, RuntimeCatalog),
            (self.runtime_provisioner, RuntimeProvisioner),
            (self.game_launch_planner, GameLaunchPlanner),
            (self.preview_locator, PreviewLocator),
        )
        if any(not isinstance(port, contract) for port, contract in ports):
            raise ValueError("engine contribution port is invalid")
        engine_ids = (
            self.runtime_catalog.engine_id,
            self.runtime_provisioner.engine_id,
            self.game_launch_planner.engine_id,
            self.preview_locator.engine_id,
        )
        if any(engine_id != self.project_format.engine_id for engine_id in engine_ids):
            raise ValueError("engine contribution ports have mismatched identities")
        if not iscoroutinefunction(self.preview_locator.locate):
            raise ValueError("engine preview locator must be asynchronous")

    @property
    def engine_id(self) -> str:
        """Return the exact project-format identity owned by this contribution."""
        return self.project_format.engine_id
