from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from threading import Event
from typing import cast

import pytest
from toqraq.core.bridge import BridgeListenerEndpoint
from toqraq.core.engine_contribution import (
    EngineContribution,
    EngineProjectFormat,
    ProjectDescription,
)
from toqraq.core.geometry import Size
from toqraq.core.preview import NativeWindowReference, NativeWindowSurface, PreviewSurface
from toqraq.core.process_tree import (
    ProcessBootstrap,
    ProcessEnvironment,
    ProcessLaunch,
    ProcessTree,
)
from toqraq.core.project_inventory import (
    ProjectInventoryReader,
    ProjectInventorySnapshot,
    ProjectInventoryStatistics,
)
from toqraq.core.runtime import (
    PreparedRuntime,
    RuntimeEntryPoint,
    RuntimeEntryPointBinding,
    RuntimeIdentity,
    RuntimeRelease,
)

_COMPONENT_RELEASE_ID = "1" * 64


class Probe:
    def __init__(self, engine_id: str, project: ProjectDescription) -> None:
        self._engine_id = engine_id
        self.project = project
        self.received: Path | None = None

    @property
    def engine_id(self) -> str:
        return self._engine_id

    def probe(self, project_root: Path) -> ProjectDescription | None:
        self.received = project_root
        return self.project


class InventoryReader:
    def __init__(self, engine_id: str) -> None:
        self._engine_id = engine_id
        self.received: Path | None = None

    @property
    def engine_id(self) -> str:
        return self._engine_id

    def scan(
        self,
        project_root: Path,
        scope: str | None,
        cancellation: Event,
    ) -> ProjectInventorySnapshot:
        self.received = project_root
        assert scope is None
        assert not cancellation.is_set()
        return ProjectInventorySnapshot(
            engine_id=self.engine_id,
            entries=(),
            statistics=ProjectInventoryStatistics(
                visited_entries=0,
                visited_directories=0,
                excluded_links=0,
                excluded_policy=0,
                unreadable=0,
                unclassified=0,
                complete=True,
            ),
        )


class Catalog:
    def __init__(self, engine_id: str, release: RuntimeRelease) -> None:
        self._engine_id = engine_id
        self.release = release
        self.project: ProjectDescription | None = None

    @property
    def engine_id(self) -> str:
        return self._engine_id

    def releases(self, project: ProjectDescription) -> tuple[RuntimeRelease, ...]:
        self.project = project
        return (self.release,)


class Provisioner:
    def __init__(self, engine_id: str, prepared: PreparedRuntime) -> None:
        self._engine_id = engine_id
        self.prepared = prepared
        self.release: RuntimeRelease | None = None
        self.cancellation: Event | None = None

    @property
    def engine_id(self) -> str:
        return self._engine_id

    def prepare(self, release: RuntimeRelease, cancellation: Event) -> PreparedRuntime:
        self.release = release
        self.cancellation = cancellation
        return self.prepared


class Resource:
    async def close(self) -> None:
        return None


class Planner:
    def __init__(self, engine_id: str) -> None:
        self._engine_id = engine_id
        self.project: ProjectDescription | None = None
        self.runtime: PreparedRuntime | None = None
        self.endpoint: BridgeListenerEndpoint | None = None
        self.environment: ProcessEnvironment | None = None
        self.bootstrap: ProcessBootstrap | None = None

    @property
    def engine_id(self) -> str:
        return self._engine_id

    def plan(
        self,
        project: ProjectDescription,
        runtime: PreparedRuntime,
        endpoint: BridgeListenerEndpoint,
        environment: ProcessEnvironment,
        bootstrap: ProcessBootstrap,
    ) -> ProcessLaunch:
        self.project = project
        self.runtime = runtime
        self.endpoint = endpoint
        self.environment = environment
        self.bootstrap = bootstrap
        return ProcessLaunch(
            executable=runtime.entry_point("editor"),
            arguments=("--path", str(project.project_root)),
            working_directory=project.project_root,
            environment=environment,
            bootstrap=bootstrap,
        )


class Locator:
    def __init__(self, engine_id: str) -> None:
        self._engine_id = engine_id
        self.project: ProjectDescription | None = None
        self.runtime: PreparedRuntime | None = None
        self.process_tree: ProcessTree | None = None
        self.cancellation: Event | None = None

    @property
    def engine_id(self) -> str:
        return self._engine_id

    async def locate(
        self,
        project: ProjectDescription,
        runtime: PreparedRuntime,
        process_tree: ProcessTree,
        cancellation: Event,
    ) -> PreviewSurface:
        self.project = project
        self.runtime = runtime
        self.process_tree = process_tree
        self.cancellation = cancellation
        assert project.display_size_hint is not None
        return NativeWindowSurface(
            window=NativeWindowReference(value=1),
            viewport_size=project.display_size_hint,
        )


def _project(root: Path) -> ProjectDescription:
    return ProjectDescription(
        engine_id="godot",
        project_root=root,
        marker_path=root / "project.godot",
        confidence=100,
        declared_version="4.7.1-stable",
        display_size_hint=Size(1280, 720),
    )


def _identity() -> RuntimeIdentity:
    return RuntimeIdentity(
        engine_id="godot",
        version="4.7.1-stable",
        build_id="toqraq.windows.x86_64.release",
        distribution_id="toqraq",
        platform="windows",
        architecture="x86_64",
    )


def _release(identity: RuntimeIdentity) -> RuntimeRelease:
    return RuntimeRelease(
        identity=identity,
        component_release_ids=(_COMPONENT_RELEASE_ID,),
        entry_point_bindings=(
            RuntimeEntryPointBinding(
                name="editor",
                component_release_id=_COMPONENT_RELEASE_ID,
                component_entry_point_name="editor",
            ),
        ),
        bridge_id="toqraq.godot.bridge",
        bridge_protocol="1.0",
        capability_ids=frozenset({"toqraq.play.lifecycle"}),
    )


def _prepared(release: RuntimeRelease, root: Path) -> PreparedRuntime:
    return PreparedRuntime(
        release=release,
        entry_points=(RuntimeEntryPoint(name="editor", path=root / "editor.exe"),),
        owned_resources=(Resource(),),
    )


def _contribution(
    root: Path,
) -> tuple[
    EngineContribution,
    Probe,
    Catalog,
    Provisioner,
    Planner,
    Locator,
]:
    project = _project(root)
    identity = _identity()
    release = _release(identity)
    prepared = _prepared(release, root)
    probe = Probe("godot", project)
    catalog = Catalog("godot", release)
    provisioner = Provisioner("godot", prepared)
    planner = Planner("godot")
    locator = Locator("godot")
    return (
        EngineContribution(
            project_format=EngineProjectFormat(
                engine_id="godot",
                project_probe=probe,
                project_inventory_reader=InventoryReader("godot"),
            ),
            runtime_catalog=catalog,
            runtime_provisioner=provisioner,
            game_launch_planner=planner,
            preview_locator=locator,
        ),
        probe,
        catalog,
        provisioner,
        planner,
        locator,
    )


def test_project_description_is_bounded_path_safe_and_immutable(tmp_path: Path) -> None:
    project = _project(tmp_path)

    assert project.marker_path.is_relative_to(project.project_root)
    assert project.display_size_hint == Size(1280, 720)
    with pytest.raises(FrozenInstanceError):
        project.confidence = 50


@pytest.mark.parametrize(
    "project",
    [
        lambda root: replace(_project(root), project_root=Path("relative")),
        lambda root: replace(_project(root), marker_path=root),
        lambda root: replace(_project(root), marker_path=root.parent / "other.project"),
        lambda root: replace(_project(root), confidence=0),
        lambda root: replace(_project(root), confidence=True),
        lambda root: replace(_project(root), declared_version="4.7 stable"),
        lambda root: replace(_project(root), display_size_hint="1280x720"),
    ],
)
def test_project_description_rejects_invalid_detection_facts(
    tmp_path: Path,
    project: Callable[[Path], ProjectDescription],
) -> None:
    with pytest.raises(ValueError):
        project(tmp_path)


def test_project_format_requires_both_read_only_perception_ports(tmp_path: Path) -> None:
    probe = Probe("godot", _project(tmp_path))
    reader = InventoryReader("godot")
    project_format = EngineProjectFormat(
        engine_id="godot",
        project_probe=probe,
        project_inventory_reader=reader,
    )

    assert tuple(field.name for field in fields(project_format)) == (
        "engine_id",
        "project_probe",
        "project_inventory_reader",
    )
    assert project_format.engine_id == "godot"
    with pytest.raises(FrozenInstanceError):
        project_format.project_probe = probe
    with pytest.raises(ValueError):
        EngineProjectFormat(
            engine_id="Godot",
            project_probe=probe,
            project_inventory_reader=reader,
        )
    with pytest.raises(ValueError, match="mismatched"):
        EngineProjectFormat(
            engine_id="godot",
            project_probe=Probe("unity", _project(tmp_path)),
            project_inventory_reader=reader,
        )
    with pytest.raises(ValueError, match="mismatched"):
        EngineProjectFormat(
            engine_id="godot",
            project_probe=probe,
            project_inventory_reader=InventoryReader("unity"),
        )

    class MissingScan:
        engine_id = "godot"

    with pytest.raises(ValueError, match="inventory reader is invalid"):
        EngineProjectFormat(
            engine_id="godot",
            project_probe=probe,
            project_inventory_reader=cast(ProjectInventoryReader, MissingScan()),
        )

    class AsyncReader:
        engine_id = "godot"

        async def scan(
            self,
            project_root: Path,
            scope: str | None,
            cancellation: Event,
        ) -> ProjectInventorySnapshot:
            del project_root, scope, cancellation
            raise AssertionError

    with pytest.raises(ValueError, match="must be synchronous"):
        EngineProjectFormat(
            engine_id="godot",
            project_probe=probe,
            project_inventory_reader=AsyncReader(),
        )


def test_contribution_preserves_one_exact_identity_through_every_port(tmp_path: Path) -> None:
    contribution, probe, catalog, provisioner, planner, locator = _contribution(tmp_path)
    cancellation = Event()
    endpoint = BridgeListenerEndpoint(port=49152)
    environment = ProcessEnvironment(variables=())
    bootstrap = ProcessBootstrap(payload=b"private launch bootstrap")

    project = contribution.project_format.project_probe.probe(tmp_path)
    assert project is not None
    releases = contribution.runtime_catalog.releases(project)
    release = releases[0]
    identity = release.identity
    prepared = contribution.runtime_provisioner.prepare(release, cancellation)
    launch = contribution.game_launch_planner.plan(
        project,
        prepared,
        endpoint,
        environment,
        bootstrap,
    )
    process_tree = cast(ProcessTree, object())
    surface = asyncio.run(
        contribution.preview_locator.locate(
            project,
            prepared,
            process_tree,
            cancellation,
        )
    )

    assert launch.executable == tmp_path / "editor.exe"
    assert probe.received == tmp_path
    assert catalog.project is project
    assert provisioner.release is release
    assert provisioner.cancellation is cancellation
    assert prepared.release is release
    assert prepared.release.identity is identity
    assert planner.project is project
    assert planner.runtime is prepared
    assert planner.endpoint is endpoint
    assert planner.environment is environment
    assert planner.bootstrap is bootstrap
    assert isinstance(surface, NativeWindowSurface)
    assert locator.project is project
    assert locator.runtime is prepared
    assert locator.process_tree is process_tree
    assert locator.cancellation is cancellation


def test_contribution_is_explicit_minimal_composition(tmp_path: Path) -> None:
    contribution, _, _, _, _, _ = _contribution(tmp_path)

    assert tuple(field.name for field in fields(contribution)) == (
        "project_format",
        "runtime_catalog",
        "runtime_provisioner",
        "game_launch_planner",
        "preview_locator",
    )
    with pytest.raises(FrozenInstanceError):
        contribution.game_launch_planner = Planner("godot")


def test_contribution_rejects_missing_or_cross_engine_ports(tmp_path: Path) -> None:
    contribution, _, _, _, _, _ = _contribution(tmp_path)

    with pytest.raises(ValueError):
        replace(contribution, game_launch_planner=Planner("unity"))
    with pytest.raises(ValueError):
        replace(contribution, project_format=object())
    with pytest.raises(ValueError):
        replace(contribution, preview_locator=Locator("unity"))
