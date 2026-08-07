"""Shared project-runtime setup projection tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError
from toqraq.contracts.setup import (
    EngineSetupResult,
    ProjectState,
    SetupAction,
    SetupRequest,
    SetupResult,
)
from toqraq.core.component import (
    ComponentKind,
    ComponentLicense,
    ComponentReadiness,
    ComponentSource,
    ManagedComponent,
)
from toqraq.core.engine_catalog import EngineCatalog
from toqraq.core.errors import ComponentReleaseInvalidError
from toqraq.core.project_format_catalog import ProjectFormatCatalog
from toqraq.services.project_runtime_selection import ProjectRuntimeSelectionService
from toqraq.services.setup import SetupService

from _session_service_support import COMPONENT_RELEASE_ID, HOST, make_fixture


class FakeInventory:
    """Return one exact managed component while recording read-only access."""

    def __init__(self, readiness: ComponentReadiness = ComponentReadiness.MISSING) -> None:
        self.readiness = readiness
        self.requested: list[str] = []

    def list_components(self) -> tuple[ManagedComponent, ...]:
        """Remain unused because setup reads only selected release IDs."""
        raise AssertionError("setup must not list or select component releases")

    def require_component(self, release_id: str) -> ManagedComponent:
        """Return readiness for the exact selected component release."""
        self.requested.append(release_id)
        return _component(release_id, self.readiness)


class UnusedInventory(FakeInventory):
    """Reject every component access for non-runtime setup outcomes."""

    def require_component(self, release_id: str) -> ManagedComponent:
        raise AssertionError(f"unexpected component read: {release_id}")


class MismatchedInventory(FakeInventory):
    """Return a different release to prove setup never accepts substitution."""

    def require_component(self, release_id: str) -> ManagedComponent:
        del release_id
        return _component("2" * 64, ComponentReadiness.READY)


def _component(release_id: str, readiness: ComponentReadiness) -> ManagedComponent:
    """Build one public-safe managed component fixture."""
    return ManagedComponent(
        release_id=release_id,
        component_id="toqraq.engine.godot",
        kind=ComponentKind.ENGINE,
        label="Godot fixture",
        version="4.7.1-stable",
        build_id="toqraq.windows.x86_64.release",
        platform="windows",
        architecture="x86_64",
        package_bytes=1,
        installed_bytes=1,
        package_sha256="1" * 64,
        source=ComponentSource(
            publisher="Fixture",
            package_url="https://example.invalid/runtime.zip",
            provenance_url="https://example.invalid/provenance",
        ),
        license=ComponentLicense(
            identifier="MIT",
            name="MIT",
            url="https://example.invalid/license",
            acceptance_required=False,
        ),
        authentication_required=False,
        capabilities=(),
        readiness=readiness,
        in_use=False,
    )


def _service(
    root: Path,
    inventory: FakeInventory,
    *,
    native_display: bool = True,
) -> SetupService:
    fixture = make_fixture(root)
    return SetupService(
        fixture.selection,
        inventory,
        HOST,
        native_display=native_display,
    )


def test_empty_format_catalog_is_serialized_as_engine_unavailable(
    tmp_path: Path,
) -> None:
    service = SetupService(
        ProjectRuntimeSelectionService(ProjectFormatCatalog(()), EngineCatalog(())),
        UnusedInventory(),
        HOST,
        native_display=True,
    )

    result = asyncio.run(
        service.check(
            SetupRequest(
                project_dir=str(tmp_path),
                engine="godot",
                version="4.7.1",
            )
        )
    )

    assert result.model_dump(mode="json") == {
        "host": {"platform": "windows", "native_display": True},
        "engine": None,
        "project": {
            "path": str(tmp_path),
            "state": "unchecked",
            "viewport_size": None,
            "probed_engine_ids": [],
        },
        "engine_choices": [],
        "action": "engine_unavailable",
    }


def test_missing_project_precedes_empty_format_catalog_selection() -> None:
    service = SetupService(
        ProjectRuntimeSelectionService(ProjectFormatCatalog(()), EngineCatalog(())),
        UnusedInventory(),
        HOST,
        native_display=True,
    )

    result = asyncio.run(service.check(SetupRequest()))

    assert result.action is SetupAction.SELECT_PROJECT
    assert result.project.state is ProjectState.MISSING


def test_recognized_project_without_admitted_runtime_never_reads_components(
    tmp_path: Path,
) -> None:
    fixture = make_fixture(tmp_path)
    service = SetupService(
        ProjectRuntimeSelectionService(
            ProjectFormatCatalog((fixture.contribution.project_format,)),
            EngineCatalog(()),
        ),
        UnusedInventory(),
        HOST,
        native_display=True,
    )

    result = asyncio.run(service.check(SetupRequest(project_dir=str(tmp_path))))

    assert result.action is SetupAction.RUNTIME_UNAVAILABLE
    assert result.project.state is ProjectState.READY
    assert result.project.probed_engine_ids == ("godot",)
    assert result.engine is not None
    assert result.engine.id == "godot"
    assert result.engine.runtime is None
    assert result.engine.available_versions == ()
    assert result.engine.required_component_release_ids == ()
    assert result.engine.runtime_install_required is False


def test_missing_or_invalid_project_never_reads_component_inventory(tmp_path: Path) -> None:
    service = _service(tmp_path, UnusedInventory())

    missing = asyncio.run(service.check(SetupRequest()))
    invalid = asyncio.run(service.check(SetupRequest(project_dir="relative/project")))

    assert missing.action is SetupAction.SELECT_PROJECT
    assert missing.project.state is ProjectState.MISSING
    assert invalid.action is SetupAction.SELECT_PROJECT
    assert invalid.project.state is ProjectState.INVALID


def test_unrecognized_project_reports_the_exact_probed_engine(tmp_path: Path) -> None:
    service = _service(tmp_path / "game", UnusedInventory())

    result = asyncio.run(service.check(SetupRequest(project_dir=str(tmp_path / "other"))))

    assert result.action is SetupAction.SELECT_PROJECT
    assert result.project.state is ProjectState.NOT_DETECTED
    assert result.project.probed_engine_ids == ("godot",)
    assert result.engine is None


@pytest.mark.parametrize(
    ("readiness", "expected_action", "install_required"),
    [
        (ComponentReadiness.MISSING, SetupAction.INSTALL, True),
        (ComponentReadiness.INVALID, SetupAction.INSTALL, True),
        (ComponentReadiness.READY, SetupAction.START, False),
    ],
)
def test_selected_runtime_projects_exact_component_readiness(
    tmp_path: Path,
    readiness: ComponentReadiness,
    expected_action: SetupAction,
    install_required: bool,
) -> None:
    inventory = FakeInventory(readiness)

    result = asyncio.run(
        _service(tmp_path, inventory).check(SetupRequest(project_dir=str(tmp_path)))
    )

    assert result.action is expected_action
    assert result.project.state is ProjectState.READY
    assert result.project.viewport_size is not None
    assert result.project.viewport_size.model_dump() == {"width": 960, "height": 540}
    assert result.engine is not None
    assert result.engine.runtime is not None
    assert result.engine.runtime.version == "4.7.1-stable"
    assert result.engine.required_component_release_ids == (COMPONENT_RELEASE_ID,)
    assert result.engine.runtime_install_required is install_required
    assert inventory.requested == [COMPONENT_RELEASE_ID]


def test_web_capable_release_is_not_blocked_by_global_native_display_state(
    tmp_path: Path,
) -> None:
    result = asyncio.run(
        _service(
            tmp_path,
            FakeInventory(ComponentReadiness.READY),
            native_display=False,
        ).check(SetupRequest(project_dir=str(tmp_path)))
    )

    assert result.action is SetupAction.START
    assert result.host.native_display is False
    assert result.engine is not None and result.engine.runtime is not None


def test_component_inventory_cannot_substitute_the_selected_release(tmp_path: Path) -> None:
    with pytest.raises(ComponentReleaseInvalidError) as caught:
        asyncio.run(
            _service(tmp_path, MismatchedInventory()).check(SetupRequest(project_dir=str(tmp_path)))
        )

    assert caught.value.details["reason"] == "inventory_identity_mismatch"


def test_setup_contract_rejects_an_engine_for_empty_format_state(tmp_path: Path) -> None:
    valid = asyncio.run(
        SetupService(
            ProjectRuntimeSelectionService(ProjectFormatCatalog(()), EngineCatalog(())),
            UnusedInventory(),
            HOST,
            native_display=True,
        ).check(SetupRequest(project_dir=str(tmp_path)))
    )

    with pytest.raises(ValidationError, match="cannot select or offer an engine"):
        SetupResult(
            host=valid.host,
            engine=EngineSetupResult(
                id="godot",
                runtime=None,
                available_versions=(),
                required_component_release_ids=(),
                runtime_install_required=False,
            ),
            project=valid.project,
            engine_choices=(),
            action=SetupAction.ENGINE_UNAVAILABLE,
        )
