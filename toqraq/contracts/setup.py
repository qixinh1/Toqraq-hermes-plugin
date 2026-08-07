"""Read-only project and exact-runtime setup contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from ..core.project_format_catalog import MAX_PROJECT_FORMATS
from ..core.project_runtime import MAX_RUNTIME_RELEASES_PER_ENGINE
from .base import ContractModel
from .geometry import SizeValue
from .identifiers import ComponentReleaseId, EngineId, EngineVersion, PlatformId, ProjectPath


class SetupAction(StrEnum):
    """Next useful action selected by the shared runtime policy."""

    ENGINE_UNAVAILABLE = "engine_unavailable"
    RUNTIME_UNAVAILABLE = "runtime_unavailable"
    INSTALL = "install"
    START = "start"
    SELECT_PROJECT = "select_project"
    SELECT_ENGINE = "select_engine"
    SELECT_VERSION = "select_version"
    UNSUPPORTED_HOST = "unsupported_host"


class ProjectState(StrEnum):
    """Read-only classification of the workspace project candidate."""

    UNCHECKED = "unchecked"
    MISSING = "missing"
    INVALID = "invalid"
    NOT_DETECTED = "not_detected"
    AMBIGUOUS = "ambiguous"
    READY = "ready"


class SetupRequest(ContractModel):
    """Workspace project and optional exact public runtime choice."""

    project_dir: ProjectPath | None = None
    engine: EngineId | None = None
    version: EngineVersion | None = None


class HostSetupResult(ContractModel):
    """Relevant immutable host and preview capability facts."""

    platform: PlatformId
    native_display: bool


class SelectedRuntimeResult(ContractModel):
    """Exact public version selected from the bundled certified catalog."""

    version: EngineVersion


class EngineSetupResult(ContractModel):
    """One selected engine and its exact runtime-readiness projection."""

    id: EngineId
    runtime: SelectedRuntimeResult | None
    available_versions: tuple[EngineVersion, ...] = Field(
        max_length=MAX_RUNTIME_RELEASES_PER_ENGINE
    )
    required_component_release_ids: tuple[ComponentReleaseId, ...] = Field(max_length=32)
    runtime_install_required: bool

    @model_validator(mode="after")
    def validate_runtime(self) -> Self:
        """Keep runtime choice, components, and readiness mutually coherent."""
        if len(set(self.available_versions)) != len(self.available_versions):
            raise ValueError("setup runtime versions must be unique")
        if self.runtime is None and self.required_component_release_ids:
            raise ValueError("unselected setup runtime cannot require components")
        if self.runtime is not None and not self.required_component_release_ids:
            raise ValueError("selected setup runtime requires exact components")
        if self.runtime_install_required and self.runtime is None:
            raise ValueError("runtime installation requires one selected runtime")
        if self.runtime is not None and self.available_versions:
            raise ValueError("selected setup runtime cannot also offer a version choice")
        return self


class EngineChoiceResult(ContractModel):
    """Bounded evidence for one project format recognized in the workspace."""

    id: EngineId
    declared_version: EngineVersion | None
    confidence: int = Field(ge=1, le=100)


class ProjectSetupResult(ContractModel):
    """Safe project facts needed by the setup surface."""

    path: ProjectPath | None
    state: ProjectState
    viewport_size: SizeValue | None
    probed_engine_ids: tuple[EngineId, ...] = Field(max_length=MAX_PROJECT_FORMATS)

    @model_validator(mode="after")
    def validate_project(self) -> Self:
        """Keep path, state, viewport, and probe evidence coherent."""
        if len(set(self.probed_engine_ids)) != len(self.probed_engine_ids):
            raise ValueError("setup probed engine identifiers must be unique")
        if self.state is ProjectState.MISSING and self.path is not None:
            raise ValueError("missing setup project cannot have a path")
        if self.state not in {ProjectState.MISSING, ProjectState.UNCHECKED} and self.path is None:
            raise ValueError("checked setup project requires a path")
        if self.state is not ProjectState.READY and self.viewport_size is not None:
            raise ValueError("only a ready setup project has a viewport hint")
        probe_count = len(self.probed_engine_ids)
        if (
            self.state
            in {
                ProjectState.UNCHECKED,
                ProjectState.MISSING,
                ProjectState.INVALID,
            }
            and probe_count
        ):
            raise ValueError("unprobed setup project cannot name probed engines")
        if self.state is ProjectState.NOT_DETECTED and probe_count < 1:
            raise ValueError("undetected setup project requires probe evidence")
        if self.state is ProjectState.AMBIGUOUS and probe_count < 2:
            raise ValueError("ambiguous setup project requires several probed engines")
        if self.state is ProjectState.READY and probe_count != 1:
            raise ValueError("ready setup project requires one probed engine")
        return self


class SetupResult(ContractModel):
    """Complete read-only projection of the shared project-runtime policy."""

    host: HostSetupResult
    engine: EngineSetupResult | None
    project: ProjectSetupResult
    engine_choices: tuple[EngineChoiceResult, ...] = Field(max_length=MAX_PROJECT_FORMATS)
    action: SetupAction

    @model_validator(mode="after")
    def validate_action(self) -> Self:
        """Reject contradictory actions before they reach Desktop."""
        _validate_engine_choices(self)
        if self.action is SetupAction.ENGINE_UNAVAILABLE:
            _validate_engine_unavailable(self)
            return self
        if self.action is SetupAction.SELECT_PROJECT:
            _validate_project_selection(self)
            return self
        if self.action is SetupAction.SELECT_ENGINE:
            _validate_engine_selection(self)
            return self
        _validate_runtime_action(self)
        return self


def _validate_engine_choices(result: SetupResult) -> None:
    """Reject duplicate public engine choices before action-specific validation."""
    if len({choice.id for choice in result.engine_choices}) != len(result.engine_choices):
        raise ValueError("setup engine choices must be unique")


def _validate_engine_unavailable(result: SetupResult) -> None:
    """Require the uninspected no-engine projection."""
    if result.engine is not None or result.engine_choices:
        raise ValueError("unavailable engine setup cannot select or offer an engine")
    if result.project.state is not ProjectState.UNCHECKED:
        raise ValueError("unavailable engine setup cannot claim project inspection")


def _validate_project_selection(result: SetupResult) -> None:
    """Require an unresolved project without an engine choice."""
    if result.engine is not None or result.engine_choices:
        raise ValueError("project selection cannot select or offer an engine")
    if result.project.state not in {
        ProjectState.MISSING,
        ProjectState.INVALID,
        ProjectState.NOT_DETECTED,
    }:
        raise ValueError("project selection requires an unresolved project")


def _validate_engine_selection(result: SetupResult) -> None:
    """Require ordered ambiguous-project evidence for a public engine choice."""
    if result.engine is not None or len(result.engine_choices) < 2:
        raise ValueError("engine selection requires several unselected engines")
    if result.project.state is not ProjectState.AMBIGUOUS:
        raise ValueError("engine selection requires an ambiguous project")
    if tuple(choice.id for choice in result.engine_choices) != result.project.probed_engine_ids:
        raise ValueError("engine choices must match probed engines in order")


def _validate_runtime_action(result: SetupResult) -> None:
    """Validate all actions that need one selected engine and ready project."""
    engine = _runtime_engine(result)
    if result.action in {SetupAction.RUNTIME_UNAVAILABLE, SetupAction.UNSUPPORTED_HOST}:
        _validate_unavailable_runtime(engine)
        return
    if result.action is SetupAction.SELECT_VERSION:
        _validate_version_selection(engine)
        return
    if result.action in {SetupAction.INSTALL, SetupAction.START}:
        _validate_launch_action(engine, result.action)
        return
    raise ValueError("setup action is invalid")


def _runtime_engine(result: SetupResult) -> EngineSetupResult:
    """Return the sole engine allowed by a runtime action after shared checks."""
    engine = result.engine
    if engine is None or result.engine_choices:
        raise ValueError("runtime setup action requires one selected engine")
    if result.project.state is not ProjectState.READY:
        raise ValueError("runtime setup action requires one ready project")
    if result.project.probed_engine_ids != (engine.id,):
        raise ValueError("selected setup engine must match the probed project engine")
    return engine


def _validate_unavailable_runtime(engine: EngineSetupResult) -> None:
    """Keep unavailable-runtime actions from implying installation or launch work."""
    if (
        engine.runtime is not None
        or engine.available_versions
        or engine.required_component_release_ids
        or engine.runtime_install_required
    ):
        raise ValueError("unavailable runtime setup cannot offer preparation")


def _validate_version_selection(engine: EngineSetupResult) -> None:
    """Require unselected public versions for an explicit version choice."""
    if engine.runtime is not None or not engine.available_versions:
        raise ValueError("version selection requires available unselected versions")


def _validate_launch_action(engine: EngineSetupResult, action: SetupAction) -> None:
    """Align selected runtime readiness with the install or start action."""
    if engine.runtime is None:
        raise ValueError("launch setup action requires one selected runtime")
    if engine.runtime_install_required is not (action is SetupAction.INSTALL):
        raise ValueError("launch setup action contradicts component readiness")
