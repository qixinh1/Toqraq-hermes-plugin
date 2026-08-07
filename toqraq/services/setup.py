"""Read-only setup projection over shared project and runtime selection."""

from __future__ import annotations

import asyncio

from ..contracts.geometry import SizeValue
from ..contracts.setup import (
    EngineChoiceResult,
    EngineSetupResult,
    HostSetupResult,
    ProjectSetupResult,
    ProjectState,
    SelectedRuntimeResult,
    SetupAction,
    SetupRequest,
    SetupResult,
)
from ..core.component import ComponentInventory, ComponentReadiness, ManagedComponent
from ..core.engine_contribution import ProjectDescription
from ..core.errors import ComponentReleaseInvalidError
from ..core.project_runtime import (
    EngineChoiceRequired,
    EngineRuntimeUnavailable,
    ProjectFormatCatalogUnavailable,
    ProjectNotDetected,
    ProjectRuntimeReady,
    ProjectRuntimeSelection,
    RuntimeTargetUnavailable,
    RuntimeVersionChoiceRequired,
    RuntimeVersionUnavailable,
)
from ..core.runtime import HostRuntimeTarget, RuntimeRelease
from .project_runtime_selection import (
    ProjectRuntimeSelectionService,
    project_runtime_selection_input,
)


class SetupService:
    """Describe one next setup action without mutating a project or component."""

    def __init__(
        self,
        selection: ProjectRuntimeSelectionService,
        inventory: ComponentInventory,
        host: HostRuntimeTarget,
        *,
        native_display: bool,
    ) -> None:
        """Bind the shared selection policy and read-only host/component facts."""
        if not isinstance(selection, ProjectRuntimeSelectionService):
            raise ValueError("setup project-runtime selection is invalid")
        if not isinstance(host, HostRuntimeTarget):
            raise ValueError("setup host runtime target is invalid")
        if type(native_display) is not bool:
            raise ValueError("setup native-display availability is invalid")
        self._selection = selection
        self._inventory = inventory
        self._host = host
        self._native_display = native_display

    async def check(self, request: SetupRequest) -> SetupResult:
        """Return one deterministic readiness snapshot without acquiring resources."""
        if not isinstance(request, SetupRequest):
            raise ValueError("setup request is invalid")
        if request.project_dir is None:
            return self._project_required()
        selection_input = project_runtime_selection_input(
            request.project_dir,
            self._host,
            engine=request.engine,
            version=request.version,
        )
        if selection_input is None:
            return self._invalid_project(request.project_dir)
        selected = await asyncio.to_thread(
            self._selection.select,
            selection_input,
        )
        if isinstance(selected, ProjectFormatCatalogUnavailable):
            return self._engine_unavailable(request)
        return await self._project_selection(selected)

    def _engine_unavailable(self, request: SetupRequest) -> SetupResult:
        """Project a plugin build with no recognized project format."""
        return SetupResult(
            host=self._host_result(),
            engine=None,
            project=ProjectSetupResult(
                path=request.project_dir,
                state=ProjectState.UNCHECKED,
                viewport_size=None,
                probed_engine_ids=(),
            ),
            engine_choices=(),
            action=SetupAction.ENGINE_UNAVAILABLE,
        )

    def _project_required(self) -> SetupResult:
        """Project the absence of a workspace project candidate."""
        return SetupResult(
            host=self._host_result(),
            engine=None,
            project=ProjectSetupResult(
                path=None,
                state=ProjectState.MISSING,
                viewport_size=None,
                probed_engine_ids=(),
            ),
            engine_choices=(),
            action=SetupAction.SELECT_PROJECT,
        )

    def _invalid_project(self, path: str) -> SetupResult:
        """Project a path that cannot enter deterministic selection."""
        return SetupResult(
            host=self._host_result(),
            engine=None,
            project=ProjectSetupResult(
                path=path,
                state=ProjectState.INVALID,
                viewport_size=None,
                probed_engine_ids=(),
            ),
            engine_choices=(),
            action=SetupAction.SELECT_PROJECT,
        )

    async def _project_selection(self, value: ProjectRuntimeSelection) -> SetupResult:
        """Project every project or runtime selection outcome for Desktop."""
        if isinstance(value, ProjectNotDetected):
            return SetupResult(
                host=self._host_result(),
                engine=None,
                project=ProjectSetupResult(
                    path=str(value.project_root),
                    state=ProjectState.NOT_DETECTED,
                    viewport_size=None,
                    probed_engine_ids=value.probed_engine_ids,
                ),
                engine_choices=(),
                action=SetupAction.SELECT_PROJECT,
            )
        if isinstance(value, EngineChoiceRequired):
            return SetupResult(
                host=self._host_result(),
                engine=None,
                project=ProjectSetupResult(
                    path=str(value.project_root),
                    state=ProjectState.AMBIGUOUS,
                    viewport_size=None,
                    probed_engine_ids=tuple(item.engine_id for item in value.candidates),
                ),
                engine_choices=tuple(
                    EngineChoiceResult(
                        id=item.engine_id,
                        declared_version=item.declared_version,
                        confidence=item.confidence,
                    )
                    for item in value.candidates
                ),
                action=SetupAction.SELECT_ENGINE,
            )
        if isinstance(value, EngineRuntimeUnavailable):
            return self._runtime_outcome(
                value.project,
                available_versions=(),
                action=SetupAction.RUNTIME_UNAVAILABLE,
            )
        if isinstance(value, RuntimeTargetUnavailable):
            return self._runtime_outcome(
                value.project,
                available_versions=(),
                action=SetupAction.UNSUPPORTED_HOST,
            )
        if isinstance(value, RuntimeVersionUnavailable):
            return self._runtime_outcome(
                value.project,
                available_versions=value.available_versions,
                action=SetupAction.SELECT_VERSION,
            )
        if isinstance(value, RuntimeVersionChoiceRequired):
            return self._runtime_outcome(
                value.project,
                available_versions=value.versions,
                action=SetupAction.SELECT_VERSION,
            )
        if isinstance(value, ProjectRuntimeReady):
            return await self._ready_runtime(value)
        raise TypeError("project-runtime selection result is invalid")

    async def _ready_runtime(self, selected: ProjectRuntimeReady) -> SetupResult:
        """Read exact component readiness for one catalog-owned release."""
        components = await asyncio.to_thread(
            _required_components,
            self._inventory,
            selected.release,
        )
        install_required = any(
            component.readiness is not ComponentReadiness.READY for component in components
        )
        action = SetupAction.INSTALL if install_required else SetupAction.START
        return SetupResult(
            host=self._host_result(),
            engine=EngineSetupResult(
                id=selected.project.engine_id,
                runtime=SelectedRuntimeResult(version=selected.release.identity.version),
                available_versions=(),
                required_component_release_ids=selected.release.component_release_ids,
                runtime_install_required=install_required,
            ),
            project=_ready_project(selected.project),
            engine_choices=(),
            action=action,
        )

    def _runtime_outcome(
        self,
        project: ProjectDescription,
        *,
        available_versions: tuple[str, ...],
        action: SetupAction,
    ) -> SetupResult:
        """Project one recognized engine whose exact runtime is unresolved."""
        return SetupResult(
            host=self._host_result(),
            engine=EngineSetupResult(
                id=project.engine_id,
                runtime=None,
                available_versions=available_versions,
                required_component_release_ids=(),
                runtime_install_required=False,
            ),
            project=_ready_project(project),
            engine_choices=(),
            action=action,
        )

    def _host_result(self) -> HostSetupResult:
        """Return the immutable host facts used by every setup outcome."""
        return HostSetupResult(
            platform=self._host.platform,
            native_display=self._native_display,
        )


def _ready_project(project: ProjectDescription) -> ProjectSetupResult:
    """Project safe recognized-project facts without exposing its marker path."""
    return ProjectSetupResult(
        path=str(project.project_root),
        state=ProjectState.READY,
        viewport_size=(
            SizeValue.from_core(project.display_size_hint)
            if project.display_size_hint is not None
            else None
        ),
        probed_engine_ids=(project.engine_id,),
    )


def _required_components(
    inventory: ComponentInventory,
    release: RuntimeRelease,
) -> tuple[ManagedComponent, ...]:
    """Read and validate exact component identities in runtime order."""
    components = tuple(
        inventory.require_component(release_id) for release_id in release.component_release_ids
    )
    for expected, component in zip(release.component_release_ids, components, strict=True):
        if not isinstance(component, ManagedComponent) or component.release_id != expected:
            raise ComponentReleaseInvalidError(
                parameters={"release_id": expected},
                details={"reason": "inventory_identity_mismatch"},
            )
    return components
