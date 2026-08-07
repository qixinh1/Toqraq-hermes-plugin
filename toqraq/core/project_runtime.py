"""Pure inputs and focused outcomes for project-runtime selection."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from .engine_contribution import EngineContribution, ProjectDescription
from .project_format_catalog import MAX_PROJECT_FORMATS
from .runtime import (
    HostRuntimeTarget,
    RuntimeRelease,
    validate_engine_id,
    validate_opaque_runtime_id,
)

MAX_RUNTIME_RELEASES_PER_ENGINE = 128


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkspaceRuntimeChoice:
    """Optional exact engine and version choices owned by one workspace."""

    engine_id: str | None = None
    version: str | None = None

    def __post_init__(self) -> None:
        """Require at least one valid explicit choice."""
        if self.engine_id is None and self.version is None:
            raise ValueError("workspace runtime choice is empty")
        if self.engine_id is not None:
            validate_engine_id(self.engine_id)
        if self.version is not None:
            validate_opaque_runtime_id(self.version)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectRuntimeSelectionInput:
    """Complete deterministic input shared by Setup and Start."""

    project_root: Path
    host: HostRuntimeTarget
    workspace_choice: WorkspaceRuntimeChoice | None = None

    def __post_init__(self) -> None:
        """Reject implicit paths and untyped host or workspace values."""
        if not isinstance(self.project_root, Path) or self.project_root != Path(
            os.path.abspath(self.project_root)
        ):
            raise ValueError("project root must be absolute and normalized")
        if not isinstance(self.host, HostRuntimeTarget):
            raise ValueError("host runtime target is invalid")
        if self.workspace_choice is not None and not isinstance(
            self.workspace_choice, WorkspaceRuntimeChoice
        ):
            raise ValueError("workspace runtime choice is invalid")


@dataclass(frozen=True, slots=True)
class ProjectFormatCatalogUnavailable:
    """This plugin build cannot recognize any engine project format."""


@dataclass(frozen=True, slots=True, kw_only=True)
class EngineRuntimeUnavailable:
    """A recognized project has no admitted runtime contribution."""

    project: ProjectDescription

    def __post_init__(self) -> None:
        """Require the exact recognized project facts."""
        if not isinstance(self.project, ProjectDescription):
            raise ValueError("runtime-unavailable project is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectNotDetected:
    """No selected engine contribution recognized the project root."""

    project_root: Path
    probed_engine_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        """Keep the no-match result bounded and attributable."""
        _require_project_root(self.project_root)
        _require_unique_engine_ids(self.probed_engine_ids)


@dataclass(frozen=True, slots=True, kw_only=True)
class EngineChoiceRequired:
    """Several engine contributions recognized the same project root."""

    project_root: Path
    candidates: tuple[ProjectDescription, ...]

    def __post_init__(self) -> None:
        """Require at least two distinct, root-consistent candidates."""
        _require_project_root(self.project_root)
        if (
            not isinstance(self.candidates, tuple)
            or len(self.candidates) < 2
            or any(not isinstance(candidate, ProjectDescription) for candidate in self.candidates)
            or any(candidate.project_root != self.project_root for candidate in self.candidates)
        ):
            raise ValueError("engine choice candidates are invalid")
        _require_unique_engine_ids(tuple(candidate.engine_id for candidate in self.candidates))


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeTargetUnavailable:
    """The recognized engine has no certified release for the exact host."""

    project: ProjectDescription
    host: HostRuntimeTarget

    def __post_init__(self) -> None:
        """Require typed project and host facts."""
        _require_project_and_host(self.project, self.host)


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeVersionUnavailable:
    """An exact workspace or project version is not certified for the host."""

    project: ProjectDescription
    host: HostRuntimeTarget
    requested_version: str
    available_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        """Expose only valid unique public versions for recovery."""
        _require_project_and_host(self.project, self.host)
        validate_opaque_runtime_id(self.requested_version)
        _require_versions(self.available_versions, minimum=1)
        if self.requested_version in self.available_versions:
            raise ValueError("unavailable runtime version is listed as available")


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeVersionChoiceRequired:
    """Several certified host releases require one exact workspace choice."""

    project: ProjectDescription
    host: HostRuntimeTarget
    versions: tuple[str, ...]

    def __post_init__(self) -> None:
        """Require a real bounded choice between unique public versions."""
        _require_project_and_host(self.project, self.host)
        _require_versions(self.versions, minimum=2)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectRuntimeReady:
    """One project and the exact catalog-owned release ready for preparation."""

    project: ProjectDescription
    contribution: EngineContribution
    host: HostRuntimeTarget
    release: RuntimeRelease

    def __post_init__(self) -> None:
        """Prevent cross-engine or cross-host selection results."""
        _require_project_and_host(self.project, self.host)
        if not isinstance(self.contribution, EngineContribution):
            raise ValueError("selected engine contribution is invalid")
        if not isinstance(self.release, RuntimeRelease):
            raise ValueError("selected runtime release is invalid")
        engine_id = self.contribution.engine_id
        if self.project.engine_id != engine_id or self.release.identity.engine_id != engine_id:
            raise ValueError("project-runtime selection has mismatched engine identities")
        if (
            self.release.identity.platform != self.host.platform
            or self.release.identity.architecture != self.host.architecture
        ):
            raise ValueError("project-runtime selection has a mismatched host identity")


ProjectRuntimeSelection: TypeAlias = (
    ProjectFormatCatalogUnavailable
    | EngineRuntimeUnavailable
    | ProjectNotDetected
    | EngineChoiceRequired
    | RuntimeTargetUnavailable
    | RuntimeVersionUnavailable
    | RuntimeVersionChoiceRequired
    | ProjectRuntimeReady
)


def _require_project_root(value: Path) -> None:
    """Require the same lexical project-root invariant as the selection input."""
    if not isinstance(value, Path) or value != Path(os.path.abspath(value)):
        raise ValueError("project root must be absolute and normalized")


def _require_project_and_host(
    project: ProjectDescription,
    host: HostRuntimeTarget,
) -> None:
    """Require typed project and host selection facts."""
    if not isinstance(project, ProjectDescription):
        raise ValueError("project description is invalid")
    if not isinstance(host, HostRuntimeTarget):
        raise ValueError("host runtime target is invalid")


def _require_unique_engine_ids(engine_ids: tuple[str, ...]) -> None:
    """Require one bounded non-empty tuple of distinct engine identifiers."""
    if (
        not isinstance(engine_ids, tuple)
        or not engine_ids
        or len(engine_ids) > MAX_PROJECT_FORMATS
        or any(not isinstance(engine_id, str) for engine_id in engine_ids)
        or len(set(engine_ids)) != len(engine_ids)
    ):
        raise ValueError("engine identifier collection is invalid")
    for engine_id in engine_ids:
        validate_engine_id(engine_id)


def _require_versions(versions: tuple[str, ...], *, minimum: int) -> None:
    """Require a bounded ordered set of public engine versions."""
    if (
        not isinstance(versions, tuple)
        or len(versions) < minimum
        or len(versions) > MAX_RUNTIME_RELEASES_PER_ENGINE
        or any(not isinstance(version, str) for version in versions)
        or len(set(versions)) != len(versions)
    ):
        raise ValueError("runtime version choices are invalid")
    for version in versions:
        validate_opaque_runtime_id(version)
