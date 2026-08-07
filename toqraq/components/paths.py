"""Portable path-name policy shared by managed component storage."""

from __future__ import annotations

import os
import stat
import unicodedata
from collections.abc import Iterable
from enum import StrEnum

_WINDOWS_INVALID_CHARACTERS = frozenset('<>:"|?*')
_WINDOWS_RESERVED_STEMS = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", "CLOCK$"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
    | {f"COM{index}" for index in "¹²³"}
    | {f"LPT{index}" for index in "¹²³"}
)


class ComponentPathConflict(StrEnum):
    """Closed namespace conflicts shared by extraction and verification."""

    DUPLICATE = "duplicate"
    TYPE = "type"


class ComponentPathConflictError(ValueError):
    """A portable path still conflicts with another component path."""

    def __init__(self, conflict: ComponentPathConflict) -> None:
        """Retain only the stable conflict reason."""
        self.conflict = conflict
        super().__init__(f"component path conflict: {conflict.value}")


class ComponentPathNamespace:
    """Track case-insensitive file and directory ownership for one tree."""

    def __init__(self) -> None:
        """Create an empty path namespace."""
        self._known: dict[tuple[str, ...], bool] = {}
        self._required_directories: set[tuple[str, ...]] = set()

    def add(self, parts: tuple[str, ...], *, is_directory: bool) -> None:
        """Register one path or raise its stable namespace conflict."""
        key = component_path_collision_key(parts)
        if key in self._known:
            raise ComponentPathConflictError(ComponentPathConflict.DUPLICATE)
        parents = tuple(key[:depth] for depth in range(1, len(key)))
        if any(parent in self._known and not self._known[parent] for parent in parents):
            raise ComponentPathConflictError(ComponentPathConflict.TYPE)
        if not is_directory and key in self._required_directories:
            raise ComponentPathConflictError(ComponentPathConflict.TYPE)
        self._known[key] = is_directory
        self._required_directories.update(parents)


def is_portable_component_part(part: str) -> bool:
    """Return whether one path segment is unambiguous on supported filesystems."""
    if not part or unicodedata.normalize("NFC", part) != part or part[-1] in {" ", "."}:
        return False
    if any(ord(character) < 32 or ord(character) == 127 for character in part):
        return False
    if _WINDOWS_INVALID_CHARACTERS.intersection(part):
        return False
    stem = part.split(".", 1)[0].rstrip(" .").upper()
    return stem not in _WINDOWS_RESERVED_STEMS


def component_path_collision_key(parts: Iterable[str]) -> tuple[str, ...]:
    """Return the case- and Unicode-insensitive key used by the component store."""
    return tuple(unicodedata.normalize("NFC", part).casefold() for part in parts)


def is_link_or_reparse(info: os.stat_result) -> bool:
    """Return whether one lstat result redirects filesystem ownership."""
    attributes = getattr(info, "st_file_attributes", 0)
    return stat.S_ISLNK(info.st_mode) or bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )
