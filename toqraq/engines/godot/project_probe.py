"""Side-effect-free recognition of a standard Godot project."""

from __future__ import annotations

from pathlib import Path

from ...core.engine_contribution import ProjectDescription
from ...core.errors import ProjectIntrospectionError
from ...core.geometry import Size
from .identity import GODOT_ENGINE_ID
from .project import GODOT_PROJECT_FILE_NAME, GodotProjectFile

_SUPPORTED_CONFIG_VERSION = 5
_DETECTION_CONFIDENCE = 100
_MAX_VIEWPORT_DIMENSION = 32_768


class GodotProjectProbe:
    """Recognize and describe one standard Godot project root."""

    @property
    def engine_id(self) -> str:
        """Return the stable Godot contribution identity."""
        return GODOT_ENGINE_ID

    def probe(self, project_root: Path) -> ProjectDescription | None:
        """Return project facts, or None when the Godot marker is absent."""
        marker = project_root / GODOT_PROJECT_FILE_NAME
        if not marker.is_file():
            return None
        project = GodotProjectFile.load(project_root)
        if project.header.get("config_version") != _SUPPORTED_CONFIG_VERSION:
            raise ProjectIntrospectionError(
                parameters={
                    "engine": GODOT_ENGINE_ID,
                    "required_config_version": _SUPPORTED_CONFIG_VERSION,
                },
                details={"reason": "unsupported_project_config_version"},
            )
        return ProjectDescription(
            engine_id=GODOT_ENGINE_ID,
            project_root=project_root,
            marker_path=marker,
            confidence=_DETECTION_CONFIDENCE,
            display_size_hint=_display_size(project),
        )


def _display_size(project: GodotProjectFile) -> Size | None:
    """Return a complete bounded viewport hint when both dimensions are valid."""
    width = _viewport_dimension(project.value("display", "window/size/viewport_width"))
    height = _viewport_dimension(project.value("display", "window/size/viewport_height"))
    return Size(width, height) if width is not None and height is not None else None


def _viewport_dimension(value: object) -> int | None:
    """Return a usable project-owned viewport dimension."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 < value <= _MAX_VIEWPORT_DIMENSION else None
