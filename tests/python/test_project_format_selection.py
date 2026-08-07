"""Production project-format recognition without runtime admission."""

from __future__ import annotations

from pathlib import Path

from toqraq.core.engine_catalog import EngineCatalog
from toqraq.core.project_format_catalog import ProjectFormatCatalog
from toqraq.core.project_runtime import EngineRuntimeUnavailable, ProjectRuntimeSelectionInput
from toqraq.core.runtime import HostRuntimeTarget
from toqraq.engines.godot.project_format import GODOT_PROJECT_FORMAT
from toqraq.services.project_runtime_selection import ProjectRuntimeSelectionService


def test_standard_godot_format_preserves_project_facts_without_a_runtime(
    tmp_path: Path,
) -> None:
    (tmp_path / "project.godot").write_text(
        """config_version=5
[display]
window/size/viewport_width=960
window/size/viewport_height=540
""",
        encoding="utf-8",
    )
    selected = ProjectRuntimeSelectionService(
        ProjectFormatCatalog((GODOT_PROJECT_FORMAT,)),
        EngineCatalog(()),
    ).select(
        ProjectRuntimeSelectionInput(
            project_root=tmp_path,
            host=HostRuntimeTarget(platform="windows", architecture="x86_64"),
        )
    )

    assert isinstance(selected, EngineRuntimeUnavailable)
    assert selected.project.engine_id == "godot"
    assert selected.project.project_root == tmp_path
    assert selected.project.display_size_hint is not None
    assert (
        selected.project.display_size_hint.width,
        selected.project.display_size_hint.height,
    ) == (
        960,
        540,
    )
