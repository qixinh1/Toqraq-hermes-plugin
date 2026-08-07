"""Reusable exact-runtime, Bridge, process, and engine fakes for session tests."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from toqraq.core.bridge import (
    COMMON_BRIDGE_LIMITS,
    BridgeHandshakeExpectation,
    BridgeListenerEndpoint,
    BridgeOwnerKey,
)
from toqraq.core.bridge_launch import BridgeLaunchBootstrap
from toqraq.core.capability_ids import (
    MANDATORY_BRIDGE_CAPABILITY_IDS,
    MANDATORY_ENGINE_CAPABILITY_IDS,
)
from toqraq.core.engine_catalog import EngineCatalog
from toqraq.core.engine_contribution import (
    EngineContribution,
    EngineProjectFormat,
    ProjectDescription,
)
from toqraq.core.errors import BridgeConnectionError, ToqraqError
from toqraq.core.geometry import Size
from toqraq.core.observation import ObservationRevision
from toqraq.core.pending_start import PendingStart
from toqraq.core.preview import NativeWindowReference, NativeWindowSurface
from toqraq.core.process_tree import (
    ProcessEnvironment,
    ProcessLaunch,
    ProcessOutputSnapshot,
)
from toqraq.core.project_format_catalog import ProjectFormatCatalog
from toqraq.core.project_runtime import ProjectRuntimeReady
from toqraq.core.runtime import (
    HostRuntimeTarget,
    PreparedRuntime,
    RuntimeEntryPoint,
    RuntimeEntryPointBinding,
    RuntimeIdentity,
    RuntimeRelease,
)
from toqraq.core.runtime_features import RuntimeFeaturePorts
from toqraq.core.simulation_control import (
    SetPausedAcknowledgement,
    SetPausedCommand,
    StepFramesAcknowledgement,
    StepFramesCommand,
)
from toqraq.services.project_runtime_selection import ProjectRuntimeSelectionService
from toqraq.services.session_start import SessionStartTransaction

from _project_format_support import EmptyProjectInventoryReader

OWNER = BridgeOwnerKey(session_id="hermes-session", run_revision=1)
CREDENTIAL = "a" * 64
COMPONENT_RELEASE_ID = "1" * 64
HOST = HostRuntimeTarget(platform="windows", architecture="x86_64")


class FakeLease:
    """Record release of one prepared-runtime lease."""

    def __init__(self) -> None:
        self.closed = 0

    async def close(self) -> None:
        self.closed += 1


class FakeProvisioner:
    """Create a fresh prepared runtime for the selected or substituted release."""

    engine_id = "godot"

    def __init__(
        self,
        root: Path,
        returned_release: RuntimeRelease,
        *,
        entered: threading.Event | None = None,
        release: threading.Event | None = None,
    ) -> None:
        self.root = root
        self.returned_release = returned_release
        self.entered = entered
        self.release = release
        self.selected: list[RuntimeRelease] = []
        self.cancellations: list[threading.Event] = []
        self.runtimes: list[PreparedRuntime] = []
        self.leases: list[FakeLease] = []

    def prepare(self, release: RuntimeRelease, cancellation: threading.Event) -> PreparedRuntime:
        self.selected.append(release)
        self.cancellations.append(cancellation)
        if self.entered is not None:
            self.entered.set()
        if self.release is not None:
            assert self.release.wait(2)
        lease = FakeLease()
        runtime = prepared_runtime(self.root, self.returned_release, lease)
        self.leases.append(lease)
        self.runtimes.append(runtime)
        return runtime


class FakeProjectProbe:
    """Recognize only the exact fixture root."""

    engine_id = "godot"

    def __init__(self, project: ProjectDescription) -> None:
        self.project = project

    def probe(self, project_root: Path) -> ProjectDescription | None:
        return self.project if project_root == self.project.project_root else None


class FakeRuntimeCatalog:
    """Expose one exact selectable release."""

    engine_id = "godot"

    def __init__(self, release: RuntimeRelease) -> None:
        self.release = release

    def releases(self, project: ProjectDescription) -> tuple[RuntimeRelease, ...]:
        del project
        return (self.release,)


class FakePlanner:
    """Record exact inputs while returning a valid platform command."""

    engine_id = "godot"

    def __init__(self) -> None:
        self.runtimes: list[PreparedRuntime] = []
        self.endpoints: list[BridgeListenerEndpoint] = []
        self.commands: list[ProcessLaunch] = []

    def plan(
        self,
        project: ProjectDescription,
        runtime: PreparedRuntime,
        endpoint: BridgeListenerEndpoint,
        environment: ProcessEnvironment,
        bootstrap,
    ) -> ProcessLaunch:
        command = ProcessLaunch(
            executable=runtime.entry_point("editor"),
            arguments=("--project", str(project.project_root)),
            working_directory=project.project_root,
            environment=environment,
            bootstrap=bootstrap,
        )
        self.runtimes.append(runtime)
        self.endpoints.append(endpoint)
        self.commands.append(command)
        return command


class FakePreviewLocator:
    """Return one safe native preview surface after an optional release signal."""

    engine_id = "godot"

    def __init__(self) -> None:
        self.calls = 0
        self.entered: asyncio.Event | None = None
        self.release: asyncio.Event | None = None

    async def locate(self, project, runtime, process_tree, cancellation):
        del project, runtime, process_tree, cancellation
        self.calls += 1
        if self.entered is not None:
            self.entered.set()
        if self.release is not None:
            await self.release.wait()
        return NativeWindowSurface(
            window=NativeWindowReference(value=99),
            viewport_size=Size(960, 540),
        )


class FakeSimulation:
    """Acknowledge pause and frame-step commands exactly."""

    def __init__(self) -> None:
        self.paused = False
        self.steps: list[int] = []
        self.revision = 0

    async def set_paused(self, command: SetPausedCommand) -> SetPausedAcknowledgement:
        changed = self.paused != command.paused
        self.paused = command.paused
        self.revision += 1
        return SetPausedAcknowledgement(
            paused=self.paused,
            changed=changed,
            simulation_revision=self._revision("simulation"),
            frame_revision=self._revision("frame"),
        )

    async def step(self, command: StepFramesCommand) -> StepFramesAcknowledgement:
        self.steps.append(command.frame_count)
        self.revision += 1
        return StepFramesAcknowledgement(
            frame_count=command.frame_count,
            paused=self.paused,
            simulation_revision=self._revision("simulation"),
            frame_revision=self._revision("frame"),
        )

    def _revision(self, family: str) -> ObservationRevision:
        return ObservationRevision(value=f"{family}-{self.revision}")


class FakePorts:
    """Structurally complete borrowed capability aggregate."""

    hierarchy = object()
    objects = object()
    diagnostics = object()
    metrics = object()
    input = object()
    frame = object()

    def __init__(self) -> None:
        self.simulation = FakeSimulation()


class FakeConnection:
    """Authenticate immediately and retain one terminal-loss signal."""

    endpoint = BridgeListenerEndpoint(port=49_152)

    def __init__(self, owner: BridgeOwnerKey) -> None:
        self.owner = owner
        self.ports = FakePorts()
        self.closed = 0
        self.unavailable = asyncio.Event()

    async def wait_ready(self) -> RuntimeFeaturePorts:
        return cast(RuntimeFeaturePorts, self.ports)

    async def wait_unavailable(self) -> ToqraqError:
        await self.unavailable.wait()
        return BridgeConnectionError(details={"reason": "test_connection_closed"})

    async def close(self) -> None:
        self.closed += 1
        self.unavailable.set()


class FakeConnectionFactory:
    """Create one connection for each exact expectation."""

    def __init__(
        self,
        *,
        entered: asyncio.Event | None = None,
        release: asyncio.Event | None = None,
    ) -> None:
        self.entered = entered
        self.release = release
        self.expectations: list[BridgeHandshakeExpectation] = []
        self.connections: list[FakeConnection] = []

    async def open(self, expectation: BridgeHandshakeExpectation) -> FakeConnection:
        self.expectations.append(expectation)
        if self.entered is not None:
            self.entered.set()
        if self.release is not None:
            await self.release.wait()
        connection = FakeConnection(expectation.owner)
        self.connections.append(connection)
        return connection


class FakeProcessTree:
    """Expose bounded waiting, natural exit, and retryable close."""

    root_pid = 4_242

    def __init__(self, *, close_failures: int = 0) -> None:
        self.close_failures = close_failures
        self.exit_code: int | None = None
        self.closed = 0
        self.terminal = threading.Event()

    def poll(self) -> int | None:
        return self.exit_code

    def wait(self, timeout: float) -> int:
        if not self.terminal.wait(timeout):
            raise TimeoutError
        if self.exit_code is None:
            raise OSError("terminal process has no result")
        return self.exit_code

    def output(self) -> ProcessOutputSnapshot:
        return ProcessOutputSnapshot(
            chunks=(), next_sequence=1, truncated=False, failed_streams=frozenset()
        )

    def close(self, *, graceful_timeout: float, forced_timeout: float) -> None:
        del graceful_timeout, forced_timeout
        self.closed += 1
        if self.closed <= self.close_failures:
            raise OSError("process close failed")
        if self.exit_code is None:
            self.exit_code = 0
        self.terminal.set()

    def exit(self, code: int) -> None:
        self.exit_code = code
        self.terminal.set()


class FakeLauncher:
    """Create one independent process tree for each launch."""

    def __init__(self, *, close_failures: int = 0) -> None:
        self.process_close_failures = close_failures
        self.commands: list[ProcessLaunch] = []
        self.processes: list[FakeProcessTree] = []
        self.closed = 0

    def launch(self, command: ProcessLaunch) -> FakeProcessTree:
        process = FakeProcessTree(close_failures=self.process_close_failures)
        self.commands.append(command)
        self.processes.append(process)
        return process

    def close(self) -> None:
        self.closed += 1


@dataclass(slots=True)
class SessionFixture:
    """Complete fake contribution and concrete runtime owners."""

    root: Path
    release: RuntimeRelease
    project: ProjectDescription
    provisioner: FakeProvisioner
    planner: FakePlanner
    preview: FakePreviewLocator
    contribution: EngineContribution
    selection: ProjectRuntimeSelectionService
    connections: FakeConnectionFactory
    launcher: FakeLauncher


def runtime_release() -> RuntimeRelease:
    """Return one complete candidate release fixture."""
    return RuntimeRelease(
        identity=RuntimeIdentity(
            engine_id="godot",
            version="4.7.1-stable",
            build_id="toqraq.windows.x86_64.release",
            distribution_id="toqraq",
            platform="windows",
            architecture="x86_64",
        ),
        component_release_ids=(COMPONENT_RELEASE_ID,),
        entry_point_bindings=(
            RuntimeEntryPointBinding(
                name="editor",
                component_release_id=COMPONENT_RELEASE_ID,
                component_entry_point_name="editor",
            ),
        ),
        bridge_id="toqraq.godot.bridge",
        bridge_protocol="1.0",
        capability_ids=MANDATORY_ENGINE_CAPABILITY_IDS,
        bridge_capability_ids=MANDATORY_BRIDGE_CAPABILITY_IDS,
    )


def prepared_runtime(root: Path, release: RuntimeRelease, lease: FakeLease) -> PreparedRuntime:
    """Bind one exact release to its explicit editor entry point and lease."""
    return PreparedRuntime(
        release=release,
        entry_points=(RuntimeEntryPoint(name="editor", path=root / "godot.exe"),),
        owned_resources=(lease,),
    )


def make_fixture(
    root: Path,
    *,
    selected_release: RuntimeRelease | None = None,
    returned_release: RuntimeRelease | None = None,
    provisioner_events: tuple[threading.Event, threading.Event] | None = None,
    connection_events: tuple[asyncio.Event, asyncio.Event] | None = None,
    process_close_failures: int = 0,
) -> SessionFixture:
    """Compose one complete fake engine contribution and platform boundary."""
    selected = selected_release or runtime_release()
    returned = returned_release or selected
    project = ProjectDescription(
        engine_id="godot",
        project_root=root,
        marker_path=root / "project.godot",
        confidence=100,
        declared_version=selected.identity.version,
        display_size_hint=Size(960, 540),
    )
    provisioner = FakeProvisioner(
        root,
        returned,
        entered=provisioner_events[0] if provisioner_events else None,
        release=provisioner_events[1] if provisioner_events else None,
    )
    planner = FakePlanner()
    preview = FakePreviewLocator()
    project_format = EngineProjectFormat(
        engine_id="godot",
        project_probe=FakeProjectProbe(project),
        project_inventory_reader=EmptyProjectInventoryReader("godot"),
    )
    contribution = EngineContribution(
        project_format=project_format,
        runtime_catalog=FakeRuntimeCatalog(selected),
        runtime_provisioner=provisioner,
        game_launch_planner=planner,
        preview_locator=preview,
    )
    return SessionFixture(
        root=root,
        release=selected,
        project=project,
        provisioner=provisioner,
        planner=planner,
        preview=preview,
        contribution=contribution,
        selection=ProjectRuntimeSelectionService(
            ProjectFormatCatalog((project_format,)),
            EngineCatalog((contribution,)),
        ),
        connections=FakeConnectionFactory(
            entered=connection_events[0] if connection_events else None,
            release=connection_events[1] if connection_events else None,
        ),
        launcher=FakeLauncher(close_failures=process_close_failures),
    )


def make_transaction(
    fixture: SessionFixture,
    *,
    owner: BridgeOwnerKey = OWNER,
) -> SessionStartTransaction:
    """Create one pending start transaction from a fixture contribution."""
    bootstrap = BridgeLaunchBootstrap(
        credential=CREDENTIAL,
        session_id=owner.session_id,
        run_revision=owner.run_revision,
    )
    pending = PendingStart(bootstrap)
    expectation = BridgeHandshakeExpectation(
        credential=CREDENTIAL,
        owner=owner,
        release=fixture.release,
        limits=COMMON_BRIDGE_LIMITS,
    )
    selection = ProjectRuntimeReady(
        project=fixture.project,
        contribution=fixture.contribution,
        host=HOST,
        release=fixture.release,
    )
    return SessionStartTransaction(
        selection=selection,
        pending=pending,
        expectation=expectation,
        connection_factory=fixture.connections,
        launcher=fixture.launcher,
        environment=ProcessEnvironment(variables=()),
    )
