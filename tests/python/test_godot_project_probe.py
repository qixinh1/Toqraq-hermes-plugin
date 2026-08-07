"""Godot project contribution recognition tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from toqraq.core.errors import ProjectIntrospectionError
from toqraq.core.geometry import Size
from toqraq.engines.godot.identity import GODOT_ENGINE_ID
from toqraq.engines.godot.project_probe import GodotProjectProbe


def _write_project(root: Path, body: str) -> None:
    (root / "project.godot").write_text(body, encoding="utf-8")


def test_probe_returns_none_only_when_project_marker_is_absent(tmp_path: Path) -> None:
    probe = GodotProjectProbe()

    assert probe.engine_id == GODOT_ENGINE_ID
    assert probe.probe(tmp_path) is None


def test_probe_returns_complete_bounded_project_facts(tmp_path: Path) -> None:
    _write_project(
        tmp_path,
        """config_version=5

[display]
window/size/viewport_width=1280
window/size/viewport_height=720
""",
    )

    description = GodotProjectProbe().probe(tmp_path)

    assert description is not None
    assert description.engine_id == GODOT_ENGINE_ID
    assert description.project_root == tmp_path
    assert description.marker_path == tmp_path / "project.godot"
    assert description.confidence == 100
    assert description.declared_version is None
    assert description.display_size_hint == Size(1280, 720)


@pytest.mark.parametrize(
    "dimensions",
    [
        "window/size/viewport_width=1280",
        "window/size/viewport_width=true\nwindow/size/viewport_height=720",
        "window/size/viewport_width=0\nwindow/size/viewport_height=720",
        "window/size/viewport_width=1280\nwindow/size/viewport_height=32769",
    ],
)
def test_probe_omits_incomplete_or_invalid_viewport_hints(
    tmp_path: Path,
    dimensions: str,
) -> None:
    _write_project(tmp_path, f"config_version=5\n[display]\n{dimensions}\n")

    description = GodotProjectProbe().probe(tmp_path)

    assert description is not None
    assert description.display_size_hint is None


def test_probe_rejects_recognized_unsupported_project_format(tmp_path: Path) -> None:
    _write_project(tmp_path, "config_version=4\n")

    with pytest.raises(ProjectIntrospectionError) as caught:
        GodotProjectProbe().probe(tmp_path)

    assert caught.value.parameters == {
        "engine": GODOT_ENGINE_ID,
        "required_config_version": 5,
    }
    assert caught.value.details == {"reason": "unsupported_project_config_version"}
