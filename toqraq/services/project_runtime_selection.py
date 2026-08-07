"""Shared deterministic selection of one project and certified runtime."""

from __future__ import annotations

import os
from pathlib import Path

from ..core.engine_catalog import EngineCatalog
from ..core.engine_contribution import (
    EngineContribution,
    EngineProjectFormat,
    ProjectDescription,
)
from ..core.errors import ComponentReleaseInvalidError, ProjectIntrospectionError
from ..core.project_format_catalog import ProjectFormatCatalog
from ..core.project_runtime import (
    MAX_RUNTIME_RELEASES_PER_ENGINE,
    EngineChoiceRequired,
    EngineRuntimeUnavailable,
    ProjectFormatCatalogUnavailable,
    ProjectNotDetected,
    ProjectRuntimeReady,
    ProjectRuntimeSelection,
    ProjectRuntimeSelectionInput,
    RuntimeTargetUnavailable,
    RuntimeVersionChoiceRequired,
    RuntimeVersionUnavailable,
    WorkspaceRuntimeChoice,
)
from ..core.runtime import HostRuntimeTarget, RuntimeRelease


def project_runtime_selection_input(
    project_dir: str,
    host: HostRuntimeTarget,
    *,
    engine: str | None,
    version: str | None,
) -> ProjectRuntimeSelectionInput | None:
    """Convert one public project choice into the shared typed selection input."""
    try:
        candidate = Path(project_dir)
        if not candidate.is_absolute():
            return None
        project_root = Path(os.path.abspath(candidate))
    except (OSError, RuntimeError, ValueError):
        return None
    choice = (
        WorkspaceRuntimeChoice(engine_id=engine, version=version)
        if engine is not None or version is not None
        else None
    )
    return ProjectRuntimeSelectionInput(
        project_root=project_root,
        host=host,
        workspace_choice=choice,
    )


class ProjectRuntimeSelectionService:
    """Apply the one project-runtime policy used by Setup and Start."""

    def __init__(self, formats: ProjectFormatCatalog, engines: EngineCatalog) -> None:
        """Bind independent recognition and admitted-runtime catalogs."""
        if not isinstance(formats, ProjectFormatCatalog):
            raise ValueError("project-runtime selection requires a project format catalog")
        if not isinstance(engines, EngineCatalog):
            raise ValueError("project-runtime selection requires an engine catalog")
        for contribution in engines.list():
            if formats.find(contribution.engine_id) is not contribution.project_format:
                raise ValueError("engine contribution must reuse its registered project format")
        self._formats = formats
        self._engines = engines

    def select(self, request: ProjectRuntimeSelectionInput) -> ProjectRuntimeSelection:
        """Return one exact release or one focused user-choice/readiness result."""
        if not isinstance(request, ProjectRuntimeSelectionInput):
            raise ValueError("project-runtime selection input is invalid")
        if not self._formats.list():
            return ProjectFormatCatalogUnavailable()
        formats = self._formats_for(request)
        matches = self._probe(formats, request)
        if not matches:
            return ProjectNotDetected(
                project_root=request.project_root,
                probed_engine_ids=tuple(project_format.engine_id for project_format in formats),
            )
        if len(matches) > 1:
            return EngineChoiceRequired(
                project_root=request.project_root,
                candidates=tuple(project for _, project in matches),
            )

        project_format, project = matches[0]
        contribution = self._engines.find(project_format.engine_id)
        if contribution is None:
            return EngineRuntimeUnavailable(project=project)
        releases = self._host_releases(contribution, project, request)
        if not releases:
            return RuntimeTargetUnavailable(project=project, host=request.host)

        requested_version = _requested_version(request, project)
        if requested_version is not None:
            selected = next(
                (release for release in releases if release.identity.version == requested_version),
                None,
            )
            if selected is None:
                return RuntimeVersionUnavailable(
                    project=project,
                    host=request.host,
                    requested_version=requested_version,
                    available_versions=tuple(release.identity.version for release in releases),
                )
            return ProjectRuntimeReady(
                project=project,
                contribution=contribution,
                host=request.host,
                release=selected,
            )

        if len(releases) > 1:
            return RuntimeVersionChoiceRequired(
                project=project,
                host=request.host,
                versions=tuple(release.identity.version for release in releases),
            )
        return ProjectRuntimeReady(
            project=project,
            contribution=contribution,
            host=request.host,
            release=releases[0],
        )

    def _formats_for(
        self,
        request: ProjectRuntimeSelectionInput,
    ) -> tuple[EngineProjectFormat, ...]:
        """Limit project probing to an explicit engine when selected."""
        choice = request.workspace_choice
        if choice is not None and choice.engine_id is not None:
            return (self._formats.require(choice.engine_id),)
        return self._formats.list()

    @staticmethod
    def _probe(
        formats: tuple[EngineProjectFormat, ...],
        request: ProjectRuntimeSelectionInput,
    ) -> tuple[tuple[EngineProjectFormat, ProjectDescription], ...]:
        """Probe in composition order and validate each adapter-owned result."""
        matches: list[tuple[EngineProjectFormat, ProjectDescription]] = []
        for project_format in formats:
            project = project_format.project_probe.probe(request.project_root)
            if project is None:
                continue
            if not isinstance(project, ProjectDescription):
                raise _project_contract_failure(project_format, "description_invalid")
            if project.engine_id != project_format.engine_id:
                raise _project_contract_failure(project_format, "engine_identity_mismatch")
            if project.project_root != request.project_root:
                raise _project_contract_failure(project_format, "project_root_mismatch")
            matches.append((project_format, project))
        return tuple(matches)

    @staticmethod
    def _host_releases(
        contribution: EngineContribution,
        project: ProjectDescription,
        request: ProjectRuntimeSelectionInput,
    ) -> tuple[RuntimeRelease, ...]:
        """Validate catalog identity and retain only exact-host releases."""
        catalog_releases = contribution.runtime_catalog.releases(project)
        if (
            not isinstance(catalog_releases, tuple)
            or len(catalog_releases) > MAX_RUNTIME_RELEASES_PER_ENGINE
        ):
            raise _catalog_contract_failure(contribution, "release_collection_invalid")

        host_releases: list[RuntimeRelease] = []
        public_versions: set[str] = set()
        for release in catalog_releases:
            if not isinstance(release, RuntimeRelease):
                raise _catalog_contract_failure(contribution, "release_invalid")
            if release.identity.engine_id != contribution.engine_id:
                raise _catalog_contract_failure(contribution, "engine_identity_mismatch")
            if (
                release.identity.platform != request.host.platform
                or release.identity.architecture != request.host.architecture
            ):
                continue
            if release.identity.version in public_versions:
                raise _catalog_contract_failure(contribution, "ambiguous_public_version")
            public_versions.add(release.identity.version)
            host_releases.append(release)
        return tuple(host_releases)


def _requested_version(
    request: ProjectRuntimeSelectionInput,
    project: ProjectDescription,
) -> str | None:
    """Apply exact workspace version before an exact project declaration."""
    choice = request.workspace_choice
    if choice is not None and choice.version is not None:
        return choice.version
    return project.declared_version


def _project_contract_failure(
    project_format: EngineProjectFormat,
    reason: str,
) -> ProjectIntrospectionError:
    """Return one typed failure for an invalid project-probe contribution."""
    return ProjectIntrospectionError(
        parameters={"engine": project_format.engine_id},
        details={"reason": reason},
    )


def _catalog_contract_failure(
    contribution: EngineContribution,
    reason: str,
) -> ComponentReleaseInvalidError:
    """Return one typed failure for an invalid certified runtime catalog."""
    return ComponentReleaseInvalidError(
        parameters={"engine": contribution.engine_id},
        details={"reason": reason},
    )
