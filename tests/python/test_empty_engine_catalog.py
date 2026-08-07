"""Empty certified-engine catalog behavior across shared selection boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest
from toqraq.core.engine_catalog import EngineCatalog
from toqraq.core.engine_contribution import (
    EngineProjectFormat,
    ProjectDescription,
)
from toqraq.core.errors import EngineUnavailableError, ErrorCategory
from toqraq.core.project_format_catalog import ProjectFormatCatalog
from toqraq.core.project_runtime import (
    EngineRuntimeUnavailable,
    ProjectFormatCatalogUnavailable,
    ProjectRuntimeSelectionInput,
    WorkspaceRuntimeChoice,
)
from toqraq.core.runtime import HostRuntimeTarget
from toqraq.services.project_runtime_selection import ProjectRuntimeSelectionService
from toqraq.services.session_selection import require_start_selection

from _project_format_support import EmptyProjectInventoryReader

_HOST = HostRuntimeTarget(platform="windows", architecture="x86_64")


class _Probe:
    engine_id = "godot"

    def __init__(self, project: ProjectDescription) -> None:
        self._project = project

    def probe(self, project_root: Path) -> ProjectDescription | None:
        assert project_root == self._project.project_root
        return self._project


def _format(root: Path) -> tuple[EngineProjectFormat, ProjectDescription]:
    project = ProjectDescription(
        engine_id="godot",
        project_root=root,
        marker_path=root / "project.godot",
        confidence=100,
        declared_version="4.7.1",
    )
    return (
        EngineProjectFormat(
            engine_id="godot",
            project_probe=_Probe(project),
            project_inventory_reader=EmptyProjectInventoryReader("godot"),
        ),
        project,
    )


@pytest.mark.parametrize(
    "choice",
    [None, WorkspaceRuntimeChoice(engine_id="godot", version="4.7.1")],
)
def test_empty_format_catalog_returns_one_state_before_choice_lookup(
    tmp_path: Path,
    choice: WorkspaceRuntimeChoice | None,
) -> None:
    selection = ProjectRuntimeSelectionService(
        ProjectFormatCatalog(()),
        EngineCatalog(()),
    ).select(
        ProjectRuntimeSelectionInput(
            project_root=tmp_path,
            host=_HOST,
            workspace_choice=choice,
        )
    )

    assert selection == ProjectFormatCatalogUnavailable()


def test_start_translates_empty_format_state_to_stable_safe_failure() -> None:
    with pytest.raises(EngineUnavailableError) as caught:
        require_start_selection(ProjectFormatCatalogUnavailable())

    assert caught.value.code == "engine.unavailable"
    assert caught.value.category is ErrorCategory.UNAVAILABLE
    assert caught.value.parameters == {}
    assert caught.value.details == {"reason": "no_project_format"}


def test_recognized_project_without_runtime_has_focused_state_and_start_failure(
    tmp_path: Path,
) -> None:
    project_format, project = _format(tmp_path)
    selected = ProjectRuntimeSelectionService(
        ProjectFormatCatalog((project_format,)),
        EngineCatalog(()),
    ).select(ProjectRuntimeSelectionInput(project_root=tmp_path, host=_HOST))

    assert selected == EngineRuntimeUnavailable(project=project)
    with pytest.raises(EngineUnavailableError) as caught:
        require_start_selection(selected)

    assert caught.value.parameters == {"engine": "godot"}
    assert caught.value.details == {"reason": "no_certified_runtime"}
