"""Pure values and the focused engine project-inventory port."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Event
from typing import Protocol, runtime_checkable

from .runtime import validate_engine_id

DEFAULT_PROJECT_INVENTORY_PAGE_ENTRIES = 32
MAX_PROJECT_INVENTORY_PAGE_ENTRIES = 64
MAX_PROJECT_INVENTORY_RECORDS = 16_384
MAX_PROJECT_INVENTORY_SCAN_NODES = 16_384
MAX_PROJECT_INVENTORY_DIRECTORIES = 2_048
MAX_PROJECT_INVENTORY_DEPTH = 64
MAX_PROJECT_INVENTORY_PATH_BYTES = 512
MAX_PROJECT_INVENTORY_NAME_BYTES = 256
MAX_PROJECT_INVENTORY_CURSOR_BYTES = 1_024
_PORTABLE_PATH_FORBIDDEN_CHARACTERS = frozenset('<>:"|?*')
_PORTABLE_RESERVED_PATH_STEMS = frozenset(
    {
        "aux",
        "clock$",
        "con",
        "conin$",
        "conout$",
        "nul",
        "prn",
        *(f"com{index}" for index in range(1, 10)),
        *(f"lpt{index}" for index in range(1, 10)),
        "com¹",
        "com²",
        "com³",
        "lpt¹",
        "lpt²",
        "lpt³",
    }
)


class ProjectInventoryCategory(StrEnum):
    """Closed baseline categories returned by project-format readers."""

    SCENE = "scene"
    SCRIPT = "script"
    RESOURCE = "resource"
    SETTING = "setting"
    DEPENDENCY = "dependency"
    INPUT = "input"


PROJECT_INVENTORY_CATEGORIES = tuple(ProjectInventoryCategory)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectInventoryEntry:
    """One project-relative file or value-free declaration identity."""

    path: str
    category: ProjectInventoryCategory
    name: str | None = None

    def __post_init__(self) -> None:
        """Reject unsafe paths, unknown categories, and unbounded names."""
        validate_project_inventory_path(self.path)
        if not isinstance(self.category, ProjectInventoryCategory):
            raise ValueError("project inventory category is invalid")
        if self.name is not None:
            validate_project_inventory_name(self.name)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectInventorySnapshot:
    """One bounded immutable engine-owned project shape."""

    engine_id: str
    entries: tuple[ProjectInventoryEntry, ...]
    statistics: ProjectInventoryStatistics

    def __post_init__(self) -> None:
        """Require one bounded unique value graph for the declared engine."""
        validate_engine_id(self.engine_id)
        if (
            not isinstance(self.entries, tuple)
            or len(self.entries) > MAX_PROJECT_INVENTORY_RECORDS
            or any(not isinstance(entry, ProjectInventoryEntry) for entry in self.entries)
        ):
            raise ValueError("project inventory entries are invalid")
        identities = tuple((entry.path, entry.category, entry.name) for entry in self.entries)
        if len(set(identities)) != len(identities):
            raise ValueError("project inventory entries are duplicated")
        if not isinstance(self.statistics, ProjectInventoryStatistics):
            raise ValueError("project inventory statistics are invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectInventoryStatistics:
    """Observed lower-bound scan counts and explicit completeness."""

    visited_entries: int
    visited_directories: int
    excluded_links: int
    excluded_policy: int
    unreadable: int
    unclassified: int
    complete: bool

    def __post_init__(self) -> None:
        """Reject negative or out-of-policy observation counts."""
        values = (
            self.visited_entries,
            self.visited_directories,
            self.excluded_links,
            self.excluded_policy,
            self.unreadable,
            self.unclassified,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values
        ):
            raise ValueError("project inventory statistic is invalid")
        if self.visited_entries > MAX_PROJECT_INVENTORY_SCAN_NODES:
            raise ValueError("project inventory visited-entry count is invalid")
        if self.visited_directories > MAX_PROJECT_INVENTORY_DIRECTORIES:
            raise ValueError("project inventory visited-directory count is invalid")
        if type(self.complete) is not bool:
            raise ValueError("project inventory completeness is invalid")


@runtime_checkable
class ProjectInventoryReader(Protocol):
    """Engine-owned synchronous metadata scan suitable for one worker thread."""

    @property
    def engine_id(self) -> str:
        """Return the project-format engine identifier."""
        ...

    def scan(
        self,
        project_root: Path,
        scope: str | None,
        cancellation: Event,
    ) -> ProjectInventorySnapshot:
        """Return one bounded snapshot without following links or changing files."""
        ...


def project_inventory_entry_key(
    entry: ProjectInventoryEntry,
) -> tuple[str, str, str]:
    """Return the one service and contract ordering key."""
    if not isinstance(entry, ProjectInventoryEntry):
        raise TypeError("project inventory entry is invalid")
    return entry.path, entry.category.value, entry.name or ""


def validate_project_inventory_path(value: str) -> str:
    """Return one canonical project-relative slash path."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("project inventory path is invalid")
    if value.startswith("/") or value.endswith("/"):
        raise ValueError("project inventory path is invalid")
    segments = value.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError("project inventory path is invalid")
    if any(_invalid_portable_path_segment(segment) for segment in segments):
        raise ValueError("project inventory path is invalid")
    _require_bounded_printable_text(
        value,
        maximum_bytes=MAX_PROJECT_INVENTORY_PATH_BYTES,
        label="project inventory path",
    )
    return value


def _invalid_portable_path_segment(segment: str) -> bool:
    """Reject filesystem aliases that are unsafe on the Windows Desktop target."""
    if segment.endswith((".", " ")):
        return True
    if any(character in _PORTABLE_PATH_FORBIDDEN_CHARACTERS for character in segment):
        return True
    stem = segment.split(".", 1)[0].rstrip(" .").casefold()
    return stem in _PORTABLE_RESERVED_PATH_STEMS


def validate_project_inventory_name(value: str) -> str:
    """Return one bounded printable declaration name."""
    _require_bounded_printable_text(
        value,
        maximum_bytes=MAX_PROJECT_INVENTORY_NAME_BYTES,
        label="project inventory name",
    )
    return value


def _require_bounded_printable_text(
    value: str,
    *,
    maximum_bytes: int,
    label: str,
) -> None:
    """Reject empty, control-bearing, unencodable, or oversized text."""
    if not isinstance(value, str) or not value or not value.isprintable():
        raise ValueError(f"{label} is invalid")
    try:
        length = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label} is invalid") from exc
    if length > maximum_bytes:
        raise ValueError(f"{label} is too large")
