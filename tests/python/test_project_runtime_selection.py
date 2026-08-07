from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from threading import Event

import pytest
from toqraq.core.bridge import BridgeListenerEndpoint
from toqraq.core.engine_catalog import EngineCatalog
from toqraq.core.engine_contribution import (
    EngineContribution,
    EngineProjectFormat,
    ProjectDescription,
    RuntimeCatalog,
)
from toqraq.core.errors import (
    ComponentReleaseInvalidError,
    EngineNotFoundError,
    ProjectIntrospectionError,
)
from toqraq.core.preview import PreviewSurface
from toqraq.core.process_tree import (
    ProcessBootstrap,
    ProcessEnvironment,
    ProcessLaunch,
    ProcessTree,
)
from toqraq.core.project_format_catalog import ProjectFormatCatalog
from toqraq.core.project_runtime import (
    MAX_RUNTIME_RELEASES_PER_ENGINE,
    EngineChoiceRequired,
    ProjectNotDetected,
    ProjectRuntimeReady,
    ProjectRuntimeSelection,
    ProjectRuntimeSelectionInput,
    RuntimeTargetUnavailable,
    RuntimeVersionChoiceRequired,
    RuntimeVersionUnavailable,
    WorkspaceRuntimeChoice,
)
from toqraq.core.runtime import (
    HostRuntimeTarget,
    PreparedRuntime,
    RuntimeEntryPointBinding,
    RuntimeIdentity,
    RuntimeRelease,
)
from toqraq.services.project_runtime_selection import ProjectRuntimeSelectionService

from _project_format_support import EmptyProjectInventoryReader

_HOST = HostRuntimeTarget(platform="windows", architecture="x86_64")
_COMPONENT_ID = "1" * 64


class RecordingProbe:
    def __init__(self, engine_id: str, project: ProjectDescription | None) -> None:
        self._engine_id = engine_id
        self.project = project
        self.roots: list[Path] = []

    @property
    def engine_id(self) -> str:
        return self._engine_id

    def probe(self, project_root: Path) -> ProjectDescription | None:
        self.roots.append(project_root)
        return self.project


class RecordingCatalog:
    def __init__(self, engine_id: str, releases: tuple[RuntimeRelease, ...]) -> None:
        self._engine_id = engine_id
        self._releases = releases
        self.projects: list[ProjectDescription] = []

    @property
    def engine_id(self) -> str:
        return self._engine_id

    def releases(self, project: ProjectDescription) -> tuple[RuntimeRelease, ...]:
        self.projects.append(project)
        return self._releases


class UnusedProvisioner:
    def __init__(self, engine_id: str) -> None:
        self._engine_id = engine_id

    @property
    def engine_id(self) -> str:
        return self._engine_id

    def prepare(self, release: RuntimeRelease, cancellation: Event) -> PreparedRuntime:
        del release, cancellation
        raise AssertionError("selection must not prepare a runtime")


class UnusedLaunchPlanner:
    def __init__(self, engine_id: str) -> None:
        self._engine_id = engine_id

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
        del project, runtime, endpoint, environment, bootstrap
        raise AssertionError("selection must not plan a launch")


class UnusedPreviewLocator:
    def __init__(self, engine_id: str) -> None:
        self._engine_id = engine_id

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
        del project, runtime, process_tree, cancellation
        raise AssertionError("selection must not locate a preview")


def _project(
    root: Path,
    engine_id: str,
    *,
    declared_version: str | None = None,
) -> ProjectDescription:
    return ProjectDescription(
        engine_id=engine_id,
        project_root=root,
        marker_path=root / f"{engine_id}.project",
        confidence=100,
        declared_version=declared_version,
    )


def _release(
    engine_id: str,
    version: str,
    *,
    platform: str = "windows",
    architecture: str = "x86_64",
    build_id: str | None = None,
) -> RuntimeRelease:
    return RuntimeRelease(
        identity=RuntimeIdentity(
            engine_id=engine_id,
            version=version,
            build_id=build_id or f"build.{version}",
            distribution_id="toqraq",
            platform=platform,
            architecture=architecture,
        ),
        component_release_ids=(_COMPONENT_ID,),
        entry_point_bindings=(
            RuntimeEntryPointBinding(
                name="editor",
                component_release_id=_COMPONENT_ID,
                component_entry_point_name="editor",
            ),
        ),
        bridge_id=f"toqraq.{engine_id}.bridge",
        bridge_protocol="1.0",
    )


def _contribution(
    engine_id: str,
    project: ProjectDescription | None,
    releases: tuple[RuntimeRelease, ...] = (),
    *,
    catalog: RuntimeCatalog | None = None,
) -> tuple[EngineContribution, RecordingProbe, RecordingCatalog | None]:
    probe = RecordingProbe(engine_id, project)
    recording_catalog = None if catalog is not None else RecordingCatalog(engine_id, releases)
    selected_catalog = catalog or recording_catalog
    assert selected_catalog is not None
    project_format = EngineProjectFormat(
        engine_id=engine_id,
        project_probe=probe,
        project_inventory_reader=EmptyProjectInventoryReader(engine_id),
    )
    contribution = EngineContribution(
        project_format=project_format,
        runtime_catalog=selected_catalog,
        runtime_provisioner=UnusedProvisioner(engine_id),
        game_launch_planner=UnusedLaunchPlanner(engine_id),
        preview_locator=UnusedPreviewLocator(engine_id),
    )
    return contribution, probe, recording_catalog


def _select(
    contributions: tuple[EngineContribution, ...],
    root: Path,
    *,
    choice: WorkspaceRuntimeChoice | None = None,
    host: HostRuntimeTarget = _HOST,
) -> ProjectRuntimeSelection:
    return ProjectRuntimeSelectionService(
        ProjectFormatCatalog(tuple(item.project_format for item in contributions)),
        EngineCatalog(contributions),
    ).select(
        ProjectRuntimeSelectionInput(
            project_root=root,
            host=host,
            workspace_choice=choice,
        )
    )


def test_selection_input_requires_exact_normalized_values(tmp_path: Path) -> None:
    value = ProjectRuntimeSelectionInput(project_root=tmp_path, host=_HOST)

    assert value.project_root is tmp_path
    with pytest.raises(FrozenInstanceError):
        value.project_root = tmp_path / "other"
    with pytest.raises(ValueError, match="normalized"):
        ProjectRuntimeSelectionInput(project_root=Path("relative"), host=_HOST)
    with pytest.raises(ValueError, match="normalized"):
        ProjectRuntimeSelectionInput(
            project_root=tmp_path / "nested" / ".." / "project",
            host=_HOST,
        )
    with pytest.raises(ValueError, match="platform"):
        HostRuntimeTarget(platform="Windows", architecture="x86_64")
    with pytest.raises(ValueError, match="empty"):
        WorkspaceRuntimeChoice()


def test_explicit_engine_probes_only_that_contribution_and_preserves_release(
    tmp_path: Path,
) -> None:
    godot_project = _project(tmp_path, "godot", declared_version="4.1")
    selected_release = _release("godot", "4.2")
    godot, godot_probe, godot_catalog = _contribution(
        "godot",
        godot_project,
        (_release("godot", "4.1"), selected_release),
    )
    unity, unity_probe, unity_catalog = _contribution("unity", _project(tmp_path, "unity"))

    result = _select(
        (godot, unity),
        tmp_path,
        choice=WorkspaceRuntimeChoice(engine_id="godot", version="4.2"),
    )

    assert isinstance(result, ProjectRuntimeReady)
    assert result.project is godot_project
    assert result.contribution is godot
    assert result.release is selected_release
    assert godot_probe.roots == [tmp_path]
    assert unity_probe.roots == []
    assert godot_catalog is not None and godot_catalog.projects == [godot_project]
    assert unity_catalog is not None and unity_catalog.projects == []


def test_unknown_explicit_engine_fails_before_any_probe(tmp_path: Path) -> None:
    godot, probe, _ = _contribution("godot", _project(tmp_path, "godot"))

    with pytest.raises(EngineNotFoundError):
        _select(
            (godot,),
            tmp_path,
            choice=WorkspaceRuntimeChoice(engine_id="unity"),
        )

    assert probe.roots == []


def test_no_match_reports_exactly_which_engines_were_probed(tmp_path: Path) -> None:
    godot, godot_probe, _ = _contribution("godot", None)
    unity, unity_probe, _ = _contribution("unity", None)

    result = _select((godot, unity), tmp_path)

    assert result == ProjectNotDetected(
        project_root=tmp_path,
        probed_engine_ids=("godot", "unity"),
    )
    assert godot_probe.roots == [tmp_path]
    assert unity_probe.roots == [tmp_path]


def test_admitted_contribution_must_reuse_the_registered_format(tmp_path: Path) -> None:
    contribution, _, _ = _contribution("godot", _project(tmp_path, "godot"))
    separate_format = EngineProjectFormat(
        engine_id=contribution.project_format.engine_id,
        project_probe=contribution.project_format.project_probe,
        project_inventory_reader=contribution.project_format.project_inventory_reader,
    )

    with pytest.raises(ValueError, match="reuse"):
        ProjectRuntimeSelectionService(
            ProjectFormatCatalog((separate_format,)),
            EngineCatalog((contribution,)),
        )


def test_multiple_project_matches_require_engine_choice_without_catalog_reads(
    tmp_path: Path,
) -> None:
    godot_project = _project(tmp_path, "godot", declared_version="4.2")
    unity_project = _project(tmp_path, "unity", declared_version="6000.1")
    godot, _, godot_catalog = _contribution("godot", godot_project)
    unity, _, unity_catalog = _contribution("unity", unity_project)

    result = _select((godot, unity), tmp_path)

    assert result == EngineChoiceRequired(
        project_root=tmp_path,
        candidates=(godot_project, unity_project),
    )
    assert godot_catalog is not None and godot_catalog.projects == []
    assert unity_catalog is not None and unity_catalog.projects == []


@pytest.mark.parametrize(
    ("choice", "declared_version", "expected_index"),
    [
        (WorkspaceRuntimeChoice(version="4.2"), "4.1", 1),
        (None, "4.1", 0),
    ],
)
def test_exact_workspace_version_precedes_exact_project_declaration(
    tmp_path: Path,
    choice: WorkspaceRuntimeChoice | None,
    declared_version: str,
    expected_index: int,
) -> None:
    releases = (_release("godot", "4.1"), _release("godot", "4.2"))
    contribution, _, _ = _contribution(
        "godot",
        _project(tmp_path, "godot", declared_version=declared_version),
        releases,
    )

    result = _select((contribution,), tmp_path, choice=choice)

    assert isinstance(result, ProjectRuntimeReady)
    assert result.release is releases[expected_index]


def test_one_host_release_is_selected_without_a_latest_policy(tmp_path: Path) -> None:
    release = _release("godot", "4.2")
    contribution, _, _ = _contribution("godot", _project(tmp_path, "godot"), (release,))

    result = _select((contribution,), tmp_path)

    assert isinstance(result, ProjectRuntimeReady)
    assert result.release is release


def test_several_host_versions_require_an_exact_version_choice(tmp_path: Path) -> None:
    releases = (_release("godot", "4.2"), _release("godot", "4.1"))
    project = _project(tmp_path, "godot")
    contribution, _, _ = _contribution("godot", project, releases)

    result = _select((contribution,), tmp_path)

    assert result == RuntimeVersionChoiceRequired(
        project=project,
        host=_HOST,
        versions=("4.2", "4.1"),
    )


def test_no_exact_host_release_reports_target_unavailable(tmp_path: Path) -> None:
    project = _project(tmp_path, "godot")
    contribution, _, _ = _contribution(
        "godot",
        project,
        (_release("godot", "4.2", platform="linux"),),
    )

    result = _select((contribution,), tmp_path)

    assert result == RuntimeTargetUnavailable(project=project, host=_HOST)


def test_missing_required_version_precedes_sole_release_auto_selection(tmp_path: Path) -> None:
    project = _project(tmp_path, "godot", declared_version="4.0")
    contribution, _, _ = _contribution(
        "godot",
        project,
        (
            _release("godot", "4.2"),
            _release("godot", "4.3", architecture="arm64"),
        ),
    )

    result = _select((contribution,), tmp_path)

    assert result == RuntimeVersionUnavailable(
        project=project,
        host=_HOST,
        requested_version="4.0",
        available_versions=("4.2",),
    )


@pytest.mark.parametrize(
    ("project", "reason"),
    [
        ("wrong_engine", "engine_identity_mismatch"),
        ("wrong_root", "project_root_mismatch"),
    ],
)
def test_invalid_probe_identity_is_a_typed_project_failure(
    tmp_path: Path,
    project: str,
    reason: str,
) -> None:
    returned = (
        _project(tmp_path, "unity")
        if project == "wrong_engine"
        else _project(tmp_path / "other", "godot")
    )
    contribution, _, _ = _contribution("godot", returned)

    with pytest.raises(ProjectIntrospectionError) as captured:
        _select((contribution,), tmp_path)

    assert captured.value.details["reason"] == reason


def test_catalog_rejects_cross_engine_release_even_for_another_host(tmp_path: Path) -> None:
    contribution, _, _ = _contribution(
        "godot",
        _project(tmp_path, "godot"),
        (_release("unity", "6000.1", platform="linux"),),
    )

    with pytest.raises(ComponentReleaseInvalidError) as captured:
        _select((contribution,), tmp_path)

    assert captured.value.details["reason"] == "engine_identity_mismatch"


def test_catalog_rejects_ambiguous_public_version_for_one_host(tmp_path: Path) -> None:
    contribution, _, _ = _contribution(
        "godot",
        _project(tmp_path, "godot"),
        (
            _release("godot", "4.2", build_id="build.one"),
            _release("godot", "4.2", build_id="build.two"),
        ),
    )

    with pytest.raises(ComponentReleaseInvalidError) as captured:
        _select((contribution,), tmp_path)

    assert captured.value.details["reason"] == "ambiguous_public_version"


def test_same_public_version_on_another_architecture_is_not_ambiguous(tmp_path: Path) -> None:
    selected = _release("godot", "4.2", build_id="build.x86")
    contribution, _, _ = _contribution(
        "godot",
        _project(tmp_path, "godot"),
        (selected, _release("godot", "4.2", architecture="arm64", build_id="build.arm")),
    )

    result = _select((contribution,), tmp_path)

    assert isinstance(result, ProjectRuntimeReady)
    assert result.release is selected


def test_catalog_collection_must_be_bounded(tmp_path: Path) -> None:
    project = _project(tmp_path, "godot")
    release = _release("godot", "4.2")
    oversized, _, _ = _contribution(
        "godot",
        project,
        (release,) * (MAX_RUNTIME_RELEASES_PER_ENGINE + 1),
    )

    with pytest.raises(ComponentReleaseInvalidError) as captured:
        _select((oversized,), tmp_path)

    assert captured.value.details["reason"] == "release_collection_invalid"
