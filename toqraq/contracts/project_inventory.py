"""Strict public contracts for task-bound project inventory reads."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    StringConstraints,
    model_validator,
)

from ..core.project_inventory import (
    DEFAULT_PROJECT_INVENTORY_PAGE_ENTRIES,
    MAX_PROJECT_INVENTORY_CURSOR_BYTES,
    MAX_PROJECT_INVENTORY_NAME_BYTES,
    MAX_PROJECT_INVENTORY_PAGE_ENTRIES,
    MAX_PROJECT_INVENTORY_PATH_BYTES,
    PROJECT_INVENTORY_CATEGORIES,
    ProjectInventoryCategory,
    ProjectInventoryEntry,
    project_inventory_entry_key,
    validate_project_inventory_name,
    validate_project_inventory_path,
)
from .base import ContractModel, freeze_sequence
from .identifiers import MAX_JSON_INTEGER, EngineId, Sha256Value

ProjectInventoryPath = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_PROJECT_INVENTORY_PATH_BYTES),
    AfterValidator(validate_project_inventory_path),
]
ProjectInventoryName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_PROJECT_INVENTORY_NAME_BYTES),
    AfterValidator(validate_project_inventory_name),
]
ProjectInventoryCursor = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=MAX_PROJECT_INVENTORY_CURSOR_BYTES,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
]


class ProjectInventorySource(StrEnum):
    """Exact task binding that supplied one inventory page."""

    LIVE = "live"
    WORKSPACE = "workspace"


def _unique_categories(
    values: tuple[ProjectInventoryCategory, ...],
) -> tuple[ProjectInventoryCategory, ...]:
    """Reject duplicate public category selections."""
    if len(set(values)) != len(values):
        raise ValueError("project inventory categories must be unique")
    return values


ProjectInventoryCategories = Annotated[
    tuple[ProjectInventoryCategory, ...],
    BeforeValidator(freeze_sequence),
    Field(min_length=1, max_length=len(PROJECT_INVENTORY_CATEGORIES)),
    AfterValidator(_unique_categories),
]


class ProjectInventoryRequest(ContractModel):
    """One bounded metadata query for the caller's bound project."""

    scope: ProjectInventoryPath | None = None
    categories: ProjectInventoryCategories | None = None
    cursor: ProjectInventoryCursor | None = None
    limit: int = Field(
        default=DEFAULT_PROJECT_INVENTORY_PAGE_ENTRIES,
        ge=1,
        le=MAX_PROJECT_INVENTORY_PAGE_ENTRIES,
    )


class ProjectInventoryEntryValue(ContractModel):
    """One project-relative file or value-free declaration."""

    path: ProjectInventoryPath
    category: ProjectInventoryCategory
    name: ProjectInventoryName | None = None

    def to_core(self) -> ProjectInventoryEntry:
        """Convert one strict public value to its pure counterpart."""
        return ProjectInventoryEntry(
            path=self.path,
            category=self.category,
            name=self.name,
        )

    @classmethod
    def from_core(cls, value: ProjectInventoryEntry) -> ProjectInventoryEntryValue:
        """Project one pure entry without adding filesystem metadata."""
        if not isinstance(value, ProjectInventoryEntry):
            raise TypeError("project inventory entry is invalid")
        return cls(path=value.path, category=value.category, name=value.name)


class ProjectInventoryCategoryCounts(ContractModel):
    """Observed record counts for every fixed inventory category."""

    scene: int = Field(ge=0, le=MAX_JSON_INTEGER)
    script: int = Field(ge=0, le=MAX_JSON_INTEGER)
    resource: int = Field(ge=0, le=MAX_JSON_INTEGER)
    setting: int = Field(ge=0, le=MAX_JSON_INTEGER)
    dependency: int = Field(ge=0, le=MAX_JSON_INTEGER)
    input: int = Field(ge=0, le=MAX_JSON_INTEGER)

    def selected_total(
        self,
        categories: tuple[ProjectInventoryCategory, ...],
    ) -> int:
        """Return the exact observed total for one effective selection."""
        return sum(getattr(self, category.value) for category in categories)


class ProjectInventoryScanResult(ContractModel):
    """Observed scan work, exclusions, and completeness."""

    visited_entries: int = Field(ge=0, le=MAX_JSON_INTEGER)
    visited_directories: int = Field(ge=0, le=MAX_JSON_INTEGER)
    excluded_links: int = Field(ge=0, le=MAX_JSON_INTEGER)
    excluded_policy: int = Field(ge=0, le=MAX_JSON_INTEGER)
    unreadable: int = Field(ge=0, le=MAX_JSON_INTEGER)
    unclassified: int = Field(ge=0, le=MAX_JSON_INTEGER)
    complete: bool


class ProjectInventoryResult(ContractModel):
    """One stable page from an exact task-bound project shape."""

    engine: EngineId
    source: ProjectInventorySource
    revision: Sha256Value
    scope: ProjectInventoryPath | None
    categories: ProjectInventoryCategories
    counts: ProjectInventoryCategoryCounts
    scan: ProjectInventoryScanResult
    total_count: int = Field(ge=0, le=MAX_JSON_INTEGER)
    entries: Annotated[
        tuple[ProjectInventoryEntryValue, ...],
        BeforeValidator(freeze_sequence),
        Field(max_length=MAX_PROJECT_INVENTORY_PAGE_ENTRIES),
    ]
    truncated: bool
    next_cursor: ProjectInventoryCursor | None

    @model_validator(mode="after")
    def validate_page(self) -> ProjectInventoryResult:
        """Require canonical selection, stable order, and exact truncation shape."""
        effective = tuple(
            category for category in PROJECT_INVENTORY_CATEGORIES if category in self.categories
        )
        if self.categories != effective:
            raise ValueError("project inventory categories are not canonical")
        core_entries = tuple(entry.to_core() for entry in self.entries)
        if core_entries != tuple(sorted(core_entries, key=project_inventory_entry_key)):
            raise ValueError("project inventory entries are not sorted")
        if len(set(core_entries)) != len(core_entries):
            raise ValueError("project inventory page entries are duplicated")
        if any(entry.category not in self.categories for entry in core_entries):
            raise ValueError("project inventory page contains an unselected category")
        if self.total_count < len(core_entries):
            raise ValueError("project inventory total count is too small")
        if self.total_count != self.counts.selected_total(self.categories):
            raise ValueError("project inventory total count contradicts category counts")
        if self.truncated != (self.next_cursor is not None):
            raise ValueError("project inventory truncation is inconsistent")
        if self.truncated and self.total_count <= len(core_entries):
            raise ValueError("project inventory truncated page needs more entries")
        return self
