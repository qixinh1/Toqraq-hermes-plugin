"""Start-request conversion and focused project-runtime selection failures."""

from __future__ import annotations

from ..contracts.sessions import GameStartRequest
from ..core.error_values import MAX_ERROR_SEQUENCE_ITEMS
from ..core.errors import (
    EngineChoiceRequiredError,
    EngineUnavailableError,
    ProjectIntrospectionError,
    RuntimeReleaseNotFoundError,
    RuntimeVersionChoiceRequiredError,
)
from ..core.project_runtime import (
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
)
from ..core.runtime import HostRuntimeTarget
from .project_runtime_selection import project_runtime_selection_input


def start_selection_input(
    request: GameStartRequest,
    host: HostRuntimeTarget,
) -> ProjectRuntimeSelectionInput:
    """Convert one strict public request into the shared deterministic input."""
    if not isinstance(request, GameStartRequest):
        raise ValueError("game start request is invalid")
    if not isinstance(host, HostRuntimeTarget):
        raise ValueError("session host runtime target is invalid")
    selection_input = project_runtime_selection_input(
        request.project_dir,
        host,
        engine=request.engine,
        version=request.version,
    )
    if selection_input is None:
        exc = ValueError("project path is not absolute")
        raise ProjectIntrospectionError(
            details={"reason": "project_path_invalid"},
            cause=exc,
        ) from exc
    return selection_input


def require_start_selection(value: ProjectRuntimeSelection) -> ProjectRuntimeReady:
    """Return the exact ready selection or raise one recoverable application error."""
    if isinstance(value, ProjectRuntimeReady):
        return value
    if isinstance(value, ProjectFormatCatalogUnavailable):
        raise EngineUnavailableError(
            details={"reason": "no_project_format"},
        )
    if isinstance(value, EngineRuntimeUnavailable):
        raise EngineUnavailableError(
            parameters={"engine": value.project.engine_id},
            details={"reason": "no_certified_runtime"},
        )
    if isinstance(value, ProjectNotDetected):
        raise ProjectIntrospectionError(
            details={
                "reason": "project_not_detected",
                "probed_engines": value.probed_engine_ids,
            }
        )
    if isinstance(value, EngineChoiceRequired):
        candidates = tuple(candidate.engine_id for candidate in value.candidates)
        raise EngineChoiceRequiredError(
            details={"engines": candidates},
        )
    if isinstance(value, RuntimeTargetUnavailable):
        raise RuntimeReleaseNotFoundError(
            parameters={"engine": value.project.engine_id},
            details={
                "reason": "host_target_unavailable",
                "platform": value.host.platform,
                "architecture": value.host.architecture,
            },
        )
    if isinstance(value, RuntimeVersionUnavailable):
        choices, truncated = _bounded_choices(value.available_versions)
        raise RuntimeReleaseNotFoundError(
            parameters={
                "engine": value.project.engine_id,
                "version": value.requested_version,
            },
            details={
                "reason": "version_unavailable",
                "available_versions": choices,
                "truncated": truncated,
            },
        )
    if isinstance(value, RuntimeVersionChoiceRequired):
        choices, truncated = _bounded_choices(value.versions)
        raise RuntimeVersionChoiceRequiredError(
            parameters={"engine": value.project.engine_id},
            details={
                "versions": choices,
                "truncated": truncated,
            },
        )
    raise TypeError("project-runtime selection result is invalid")


def _bounded_choices(values: tuple[str, ...]) -> tuple[tuple[str, ...], bool]:
    """Fit recovery choices into the shared safe-error sequence bound."""
    return values[:MAX_ERROR_SEQUENCE_ITEMS], len(values) > MAX_ERROR_SEQUENCE_ITEMS
