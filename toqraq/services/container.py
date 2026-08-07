"""Process-local composition root for the standard Hermes plugin."""

from __future__ import annotations

import asyncio
import contextlib
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from ..bridge.bridge_feature_connection import BridgeRuntimeFeatureConnectionFactory
from ..components.catalog import CertifiedComponentCatalog
from ..components.download import ComponentDownloader
from ..components.layout import ComponentStoreLayout
from ..components.managed import (
    CertifiedComponentInventory,
    CertifiedComponentPreparation,
    CertifiedComponentRemoval,
)
from ..components.mutation import ComponentMutationOwner
from ..components.provisioner import ComponentProvisioner
from ..components.settings import ComponentSettings, component_settings
from ..components.space import SystemComponentSpaceProbe
from ..components.store import ComponentStore
from ..components.strategy import ComponentStrategyCatalog
from ..components.zip_strategy import ZipComponentInstallStrategy
from ..core.component import ComponentInventory
from ..core.engine_catalog import EngineCatalog
from ..core.native_display import NativeDisplay
from ..core.process_tree import ProcessEnvironment, ProcessTreeLauncher
from ..core.project_format_catalog import ProjectFormatCatalog
from ..core.runtime import HostRuntimeTarget
from ..core.session_registry import SessionRegistry
from ..engines.godot.project_format import GODOT_PROJECT_FORMAT
from ..hermes.paths import component_store_dir
from ..platforms.unavailable import UnavailableProcessTreeLauncher
from ..version import PLUGIN_VERSION
from .component_jobs import ComponentJobService, component_job_policy
from .diagnostics import DiagnosticsService
from .display import NativeDisplayService
from .events import SessionEventStream
from .frame_capture import FrameCaptureService
from .hierarchy import HierarchyService
from .input import InputService
from .metrics import MetricsService
from .object_inspection import ObjectInspectionService
from .process_output import ProcessOutputService
from .project_inventory import ProjectInventoryService
from .project_runtime_selection import ProjectRuntimeSelectionService
from .session_gate import SessionOperationGate
from .sessions import SessionService
from .setup import SetupService
from .simulation import SimulationService
from .workspace_context import WorkspaceContextService

UNAVAILABLE_HOST_RUNTIME_TARGET = HostRuntimeTarget(
    platform="unsupported",
    architecture="unsupported",
)


@dataclass(slots=True)
class Container:
    """Own the explicitly composed application services for one plugin instance."""

    events: SessionEventStream
    session_service: SessionService
    simulation_service: SimulationService
    display_service: NativeDisplayService
    hierarchy_service: HierarchyService
    object_inspection_service: ObjectInspectionService
    process_output_service: ProcessOutputService
    diagnostics_service: DiagnosticsService
    metrics_service: MetricsService
    frame_capture_service: FrameCaptureService
    input_service: InputService
    component_jobs: ComponentJobService
    setup_service: SetupService
    workspace_context_service: WorkspaceContextService
    project_inventory_service: ProjectInventoryService

    async def close(self) -> None:
        """Seal both mutable owners and settle both cleanup paths."""
        self.session_service.begin_close()
        self.component_jobs.begin_close()
        self.workspace_context_service.close()
        cleanup = asyncio.create_task(self._close_owners(), name="toqraq-plugin-cleanup")
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await cleanup
            raise

    async def _close_owners(self) -> None:
        """Attempt independent session and component cleanup without short circuiting."""
        results = await asyncio.gather(
            self.session_service.close(),
            self.component_jobs.close(),
            return_exceptions=True,
        )
        failures = [result for result in results if isinstance(result, BaseException)]
        if failures:
            raise BaseExceptionGroup("Toqraq plugin shutdown failed", failures)


def build_container() -> Container:
    """Assemble one loadable graph without claiming an uncertified engine."""
    managed_root = component_store_dir()
    host, launcher, native_display, environment = _host_process_services(managed_root)
    formats = ProjectFormatCatalog((GODOT_PROJECT_FORMAT,))
    engines = EngineCatalog(())
    selection = ProjectRuntimeSelectionService(formats, engines)
    component_jobs, component_inventory = _component_services(managed_root)
    events = SessionEventStream()
    sessions = SessionRegistry()
    gate = SessionOperationGate()
    lifecycle = SessionService(
        selection=selection,
        registry=sessions,
        events=events,
        host=host,
        connection_factory=BridgeRuntimeFeatureConnectionFactory(),
        launcher=launcher,
        environment=environment,
        gate=gate,
    )
    setup = SetupService(
        selection,
        component_inventory,
        host,
        native_display=native_display is not None,
    )
    workspace_context = WorkspaceContextService(setup)
    return Container(
        events=events,
        session_service=lifecycle,
        simulation_service=SimulationService(sessions, gate, events),
        display_service=NativeDisplayService(sessions, gate, native_display),
        hierarchy_service=HierarchyService(sessions, gate),
        object_inspection_service=ObjectInspectionService(sessions, gate),
        process_output_service=ProcessOutputService(sessions, gate),
        diagnostics_service=DiagnosticsService(sessions, gate),
        metrics_service=MetricsService(sessions, gate),
        frame_capture_service=FrameCaptureService(sessions, gate),
        input_service=InputService(sessions, gate),
        component_jobs=component_jobs,
        setup_service=setup,
        workspace_context_service=workspace_context,
        project_inventory_service=ProjectInventoryService(
            formats,
            sessions,
            workspace_context,
        ),
    )


def _host_process_services(
    managed_root: Path,
) -> tuple[
    HostRuntimeTarget,
    ProcessTreeLauncher,
    NativeDisplay | None,
    ProcessEnvironment,
]:
    """Compose the one platform launcher available in this plugin build."""
    if sys.platform != "win32":
        return (
            UNAVAILABLE_HOST_RUNTIME_TARGET,
            UnavailableProcessTreeLauncher(),
            None,
            ProcessEnvironment(variables=()),
        )
    from ..platforms.windows.child_environment import windows_managed_child_environment
    from ..platforms.windows.native_display import WindowsNativeDisplay
    from ..platforms.windows.process_launcher import WindowsProcessTreeLauncher
    from ..platforms.windows.runtime_target import windows_runtime_target

    return (
        windows_runtime_target(),
        WindowsProcessTreeLauncher(),
        WindowsNativeDisplay(),
        windows_managed_child_environment(managed_root),
    )


def _component_services(managed_root: Path) -> tuple[ComponentJobService, ComponentInventory]:
    """Compose one exact catalog, inventory, mutation service, and job owner."""
    settings = component_settings(PLUGIN_VERSION)
    layout = ComponentStoreLayout(managed_root)
    store = ComponentStore(layout, settings.lock)
    mutations = ComponentMutationOwner(layout, settings.lock)
    strategies = ComponentStrategyCatalog((ZipComponentInstallStrategy(settings.zip),))
    catalog = CertifiedComponentCatalog(())
    inventory = CertifiedComponentInventory(catalog, store, strategies)
    provisioner = _component_provisioner(
        settings,
        layout,
        store,
        mutations,
        strategies,
    )
    jobs = ComponentJobService(
        inventory,
        CertifiedComponentPreparation(catalog, provisioner),
        CertifiedComponentRemoval(catalog, store, mutations),
        component_job_policy(),
    )
    return jobs, inventory


def _component_provisioner(
    settings: ComponentSettings,
    layout: ComponentStoreLayout,
    store: ComponentStore,
    mutations: ComponentMutationOwner,
    strategies: ComponentStrategyCatalog,
) -> ComponentProvisioner:
    """Compose exact download, storage, install, and publication ownership."""
    return ComponentProvisioner(
        layout,
        mutations,
        ComponentDownloader(layout, settings.download),
        store,
        strategies,
        SystemComponentSpaceProbe(),
        settings.space,
    )


_instance: Container | None = None
_instance_lock = threading.Lock()


async def dispose_container(container: Container) -> None:
    """Close and release one exact process-local plugin instance."""
    global _instance
    await container.close()
    with _instance_lock:
        if _instance is container:
            _instance = None


def get_container() -> Container:
    """Return the one graph shared by Hermes tools and Dashboard routes."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = build_container()
    return _instance
