"""Godot-owned project inventory classifications and exclusions."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import PurePosixPath

from ...core.project_inventory import (
    ProjectInventoryCategory,
    ProjectInventoryEntry,
    validate_project_inventory_name,
)
from .project import GODOT_PROJECT_FILE_NAME, GodotProjectFile

_GENERATED_DIRECTORY_NAMES = frozenset({".git", ".godot", ".hg", ".import", ".mono", ".svn"})
_GENERATED_FILE_SUFFIXES = (".import", ".uid")
_SECRET_FILE_SUFFIXES = (
    ".jks",
    ".key",
    ".keystore",
    ".p12",
    ".pem",
    ".pfx",
)
_SECRET_STEMS = frozenset(
    {
        ".env",
        "api_key",
        "apikey",
        "credential",
        "credentials",
        "id_ed25519",
        "id_rsa",
        "private_key",
        "secret",
        "secrets",
        "token",
    }
)
_SCENE_SUFFIXES = frozenset({".scn", ".tscn"})
_SCRIPT_SUFFIXES = frozenset({".cs", ".gd"})
_RESOURCE_SUFFIXES = frozenset(
    {
        ".ase",
        ".aseprite",
        ".bmp",
        ".dae",
        ".exr",
        ".fbx",
        ".glb",
        ".gltf",
        ".gdshader",
        ".hdr",
        ".jpeg",
        ".jpg",
        ".mesh",
        ".mp3",
        ".mp4",
        ".obj",
        ".ogg",
        ".ogv",
        ".otf",
        ".png",
        ".res",
        ".svg",
        ".tga",
        ".tres",
        ".ttf",
        ".wav",
        ".webm",
        ".webp",
    }
)
_DEPENDENCY_FILE_NAMES = frozenset({"extension_list.cfg", "plugin.cfg"})
_SETTING_FILE_NAMES = frozenset({GODOT_PROJECT_FILE_NAME, "export_presets.cfg", "override.cfg"})
_DEPENDENCY_SECTIONS = frozenset({"autoload", "editor_plugins"})


def excludes_inventory_name(name: str, *, directory: bool) -> bool:
    """Return whether policy prevents exposing or descending into one name."""
    folded = name.casefold()
    if not name or name.startswith("."):
        return True
    if directory:
        return folded in _GENERATED_DIRECTORY_NAMES or folded in _SECRET_STEMS
    if folded.endswith(_GENERATED_FILE_SUFFIXES):
        return True
    suffix = PurePosixPath(folded).suffix
    stem = folded[: -len(suffix)] if suffix else folded
    return suffix in _SECRET_FILE_SUFFIXES or stem in _SECRET_STEMS


def classify_inventory_file(path: str) -> ProjectInventoryCategory | None:
    """Classify one already-safe relative file path by Godot-native meaning."""
    candidate = PurePosixPath(path.casefold())
    name = candidate.name
    suffix = candidate.suffix
    if name in _DEPENDENCY_FILE_NAMES or suffix == ".gdextension":
        return ProjectInventoryCategory.DEPENDENCY
    if name in _SETTING_FILE_NAMES:
        return ProjectInventoryCategory.SETTING
    if suffix in _SCENE_SUFFIXES:
        return ProjectInventoryCategory.SCENE
    if suffix in _SCRIPT_SUFFIXES:
        return ProjectInventoryCategory.SCRIPT
    if suffix in _RESOURCE_SUFFIXES:
        return ProjectInventoryCategory.RESOURCE
    return None


def marker_declaration_entries(
    project: GodotProjectFile,
) -> Iterator[ProjectInventoryEntry | None]:
    """Project only input and dependency names, never general keys or values."""
    for section, values in project.sections.items():
        if section == "input":
            category = ProjectInventoryCategory.INPUT
        elif section in _DEPENDENCY_SECTIONS:
            category = ProjectInventoryCategory.DEPENDENCY
        else:
            continue
        for key in values:
            yield _declaration_entry(category, f"{section}/{key}")


def _declaration_entry(
    category: ProjectInventoryCategory,
    name: str,
) -> ProjectInventoryEntry | None:
    """Exclude secret-like key identities before constructing a public value."""
    final_segment = name.rsplit("/", 1)[-1].casefold()
    if final_segment in _SECRET_STEMS:
        return None
    try:
        validate_project_inventory_name(name)
    except ValueError:
        return None
    return ProjectInventoryEntry(
        path=GODOT_PROJECT_FILE_NAME,
        category=category,
        name=name,
    )
