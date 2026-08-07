"""Pure bounded hierarchy values and the focused read port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .observation import (
    EngineFact,
    ObservationCursor,
    ObservationRevision,
    ObservationStamp,
    RunObjectReference,
    validate_engine_facts,
    validate_observation_count,
    validate_observation_label,
)

MAX_HIERARCHY_DEPTH = 16
MAX_HIERARCHY_FILTER_TYPES = 32
MAX_HIERARCHY_PAGE_ENTRIES = 256
MAX_HIERARCHY_COMPONENT_TYPES = 32
MAX_HIERARCHY_NAME_BYTES = 256
MAX_HIERARCHY_NATIVE_TYPE_BYTES = 256


@dataclass(frozen=True, slots=True, kw_only=True)
class HierarchyQuery:
    """Explicit hierarchy selection for one run-scoped revision."""

    root: RunObjectReference | None
    depth: int
    name_contains: str | None
    native_types: tuple[str, ...]
    revision: ObservationRevision | None
    cursor: ObservationCursor | None
    limit: int

    def __post_init__(self) -> None:
        """Reject ambiguous paging, unbounded filters, and mutable sequences."""
        if self.root is not None and not isinstance(self.root, RunObjectReference):
            raise ValueError("hierarchy root reference is invalid")
        if (
            isinstance(self.depth, bool)
            or not isinstance(self.depth, int)
            or not 0 <= self.depth <= MAX_HIERARCHY_DEPTH
        ):
            raise ValueError("hierarchy depth is invalid")
        if self.name_contains is not None:
            validate_observation_label(
                self.name_contains,
                maximum_bytes=MAX_HIERARCHY_NAME_BYTES,
            )
        _validate_native_types(self.native_types, maximum=MAX_HIERARCHY_FILTER_TYPES)
        if self.revision is not None and not isinstance(self.revision, ObservationRevision):
            raise ValueError("hierarchy revision is invalid")
        if self.cursor is not None and not isinstance(self.cursor, ObservationCursor):
            raise ValueError("hierarchy cursor is invalid")
        if self.cursor is not None and self.revision is None:
            raise ValueError("hierarchy cursor requires its revision")
        if (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or not 1 <= self.limit <= MAX_HIERARCHY_PAGE_ENTRIES
        ):
            raise ValueError("hierarchy entry limit is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class HierarchyEntry:
    """One flat runtime entity with bounded native summaries."""

    reference: RunObjectReference
    display_name: str
    native_type: str
    parent: RunObjectReference | None
    child_count: int
    component_type_count: int
    component_types: tuple[str, ...]
    components_truncated: bool
    extensions: tuple[EngineFact, ...]

    def __post_init__(self) -> None:
        """Keep hierarchy entries flat, unique in shape, and explicitly bounded."""
        if not isinstance(self.reference, RunObjectReference):
            raise ValueError("hierarchy entry reference is invalid")
        validate_observation_label(
            self.display_name,
            maximum_bytes=MAX_HIERARCHY_NAME_BYTES,
        )
        validate_observation_label(
            self.native_type,
            maximum_bytes=MAX_HIERARCHY_NATIVE_TYPE_BYTES,
        )
        if self.parent is not None and not isinstance(self.parent, RunObjectReference):
            raise ValueError("hierarchy parent reference is invalid")
        if self.parent == self.reference:
            raise ValueError("hierarchy entry cannot parent itself")
        validate_observation_count(self.child_count, label="hierarchy child count")
        validate_observation_count(
            self.component_type_count,
            label="hierarchy component-type count",
        )
        _validate_native_types(
            self.component_types,
            maximum=MAX_HIERARCHY_COMPONENT_TYPES,
        )
        if self.component_type_count < len(self.component_types):
            raise ValueError("hierarchy component-type count is too small")
        if type(self.components_truncated) is not bool or self.components_truncated != (
            self.component_type_count > len(self.component_types)
        ):
            raise ValueError("hierarchy component truncation is inconsistent")
        validate_engine_facts(self.extensions)


@dataclass(frozen=True, slots=True, kw_only=True)
class HierarchyPage:
    """One revision-consistent flat hierarchy page."""

    stamp: ObservationStamp
    entries: tuple[HierarchyEntry, ...]
    truncated: bool
    next_cursor: ObservationCursor | None

    def __post_init__(self) -> None:
        """Require explicit exact counts and cursor-backed truncation."""
        if not isinstance(self.stamp, ObservationStamp):
            raise ValueError("hierarchy observation stamp is invalid")
        if (
            not isinstance(self.entries, tuple)
            or len(self.entries) > MAX_HIERARCHY_PAGE_ENTRIES
            or any(not isinstance(entry, HierarchyEntry) for entry in self.entries)
        ):
            raise ValueError("hierarchy page entries are invalid")
        references = tuple(entry.reference for entry in self.entries)
        if len(set(references)) != len(references):
            raise ValueError("hierarchy page references must be unique")
        if self.next_cursor is not None and not isinstance(
            self.next_cursor,
            ObservationCursor,
        ):
            raise ValueError("hierarchy continuation cursor is invalid")
        if type(self.truncated) is not bool or self.truncated != (self.next_cursor is not None):
            raise ValueError("hierarchy truncation is inconsistent")


def validate_hierarchy_page(page: HierarchyPage, query: HierarchyQuery) -> None:
    """Correlate one hierarchy page with the exact query that owns it."""
    if not isinstance(page, HierarchyPage):
        raise TypeError("hierarchy page is invalid")
    if not isinstance(query, HierarchyQuery):
        raise TypeError("hierarchy query is invalid")
    if len(page.entries) > query.limit:
        raise ValueError("hierarchy page exceeds its requested limit")
    if query.revision is not None and page.stamp.revision != query.revision:
        raise ValueError("hierarchy page revision does not match its query")


@runtime_checkable
class HierarchyReader(Protocol):
    """Read-only engine boundary for a bounded live hierarchy page."""

    async def read(self, query: HierarchyQuery) -> HierarchyPage:
        """Read one page without changing engine or project state."""
        ...


def _validate_native_types(values: tuple[str, ...], *, maximum: int) -> None:
    """Require a bounded immutable set of exact engine-native type labels."""
    if not isinstance(values, tuple) or len(values) > maximum:
        raise ValueError("hierarchy native-type collection is invalid")
    if len(set(values)) != len(values):
        raise ValueError("hierarchy native types must be unique")
    for value in values:
        validate_observation_label(
            value,
            maximum_bytes=MAX_HIERARCHY_NATIVE_TYPE_BYTES,
        )
