"""Shared public-input conversion for project-runtime selection."""

from __future__ import annotations

from pathlib import Path

from toqraq.core.runtime import HostRuntimeTarget
from toqraq.services.project_runtime_selection import project_runtime_selection_input

_HOST = HostRuntimeTarget(platform="windows", architecture="x86_64")


def test_selection_input_normalizes_one_absolute_root_and_exact_choice(tmp_path: Path) -> None:
    result = project_runtime_selection_input(
        str(tmp_path / "folder" / ".." / "game"),
        _HOST,
        engine="godot",
        version="4.7.1",
    )

    assert result is not None
    assert result.project_root == tmp_path / "game"
    assert result.host is _HOST
    assert result.workspace_choice is not None
    assert result.workspace_choice.engine_id == "godot"
    assert result.workspace_choice.version == "4.7.1"


def test_selection_input_rejects_relative_root_and_omits_empty_choice(tmp_path: Path) -> None:
    assert (
        project_runtime_selection_input(
            "relative/game",
            _HOST,
            engine=None,
            version=None,
        )
        is None
    )

    result = project_runtime_selection_input(
        str(tmp_path),
        _HOST,
        engine=None,
        version=None,
    )
    assert result is not None
    assert result.workspace_choice is None
