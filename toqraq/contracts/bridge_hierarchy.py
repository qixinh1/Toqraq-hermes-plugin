"""Strict JSON-RPC contracts for bounded runtime hierarchy reads."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    StringConstraints,
    model_validator,
)

from ..core.hierarchy import (
    MAX_HIERARCHY_COMPONENT_TYPES,
    MAX_HIERARCHY_DEPTH,
    MAX_HIERARCHY_FILTER_TYPES,
    MAX_HIERARCHY_NAME_BYTES,
    MAX_HIERARCHY_NATIVE_TYPE_BYTES,
    MAX_HIERARCHY_PAGE_ENTRIES,
    HierarchyEntry,
    HierarchyPage,
    HierarchyQuery,
    validate_hierarchy_page,
)
from ..core.observation import (
    ObservationCursor,
    ObservationRevision,
    ObservationStamp,
    RunObjectReference,
    validate_observation_label,
)
from .base import ContractModel, freeze_sequence
from .bridge import JSON_RPC_VERSION
from .bridge_observation import (
    EngineFactValues,
    ObservationCursorValue,
    ObservationObjectReference,
    ObservationRevisionValue,
    ObservationUnixMilliseconds,
    engine_facts_from_core,
    engine_facts_to_core,
)
from .bridge_rpc import BridgeHostRequestId
from .identifiers import MAX_JSON_INTEGER

HIERARCHY_READ_METHOD: Literal["toqraq.hierarchy.read"] = "toqraq.hierarchy.read"


def _validate_name(value: str) -> str:
    """Apply the hierarchy name UTF-8 byte bound."""
    return validate_observation_label(value, maximum_bytes=MAX_HIERARCHY_NAME_BYTES)


def _validate_native_type(value: str) -> str:
    """Apply the engine-native type UTF-8 byte bound."""
    return validate_observation_label(
        value,
        maximum_bytes=MAX_HIERARCHY_NATIVE_TYPE_BYTES,
    )


HierarchyName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_HIERARCHY_NAME_BYTES),
    AfterValidator(_validate_name),
]
HierarchyNativeType = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_HIERARCHY_NATIVE_TYPE_BYTES),
    AfterValidator(_validate_native_type),
]


def _unique_native_types(values: tuple[str, ...]) -> tuple[str, ...]:
    """Reject duplicates instead of changing exact engine filter semantics."""
    if len(set(values)) != len(values):
        raise ValueError("hierarchy native types must be unique")
    return values


HierarchyFilterTypes: TypeAlias = Annotated[
    tuple[HierarchyNativeType, ...],
    BeforeValidator(freeze_sequence),
    Field(max_length=MAX_HIERARCHY_FILTER_TYPES),
    AfterValidator(_unique_native_types),
]
HierarchyComponentTypes: TypeAlias = Annotated[
    tuple[HierarchyNativeType, ...],
    BeforeValidator(freeze_sequence),
    Field(max_length=MAX_HIERARCHY_COMPONENT_TYPES),
    AfterValidator(_unique_native_types),
]


class HierarchyReadParams(ContractModel):
    """Exact bounded hierarchy selection sent to one authenticated run."""

    root: ObservationObjectReference | None = None
    depth: int = Field(ge=0, le=MAX_HIERARCHY_DEPTH)
    name_contains: HierarchyName | None = None
    native_types: HierarchyFilterTypes
    revision: ObservationRevisionValue | None = None
    cursor: ObservationCursorValue | None = None
    limit: int = Field(ge=1, le=MAX_HIERARCHY_PAGE_ENTRIES)

    @model_validator(mode="after")
    def validate_cursor_revision(self) -> HierarchyReadParams:
        """Tie a continuation cursor to the revision that created it."""
        if self.cursor is not None and self.revision is None:
            raise ValueError("hierarchy cursor requires its revision")
        return self

    def to_core(self) -> HierarchyQuery:
        """Convert the strict wire params to the pure focused query."""
        return HierarchyQuery(
            root=RunObjectReference(value=self.root) if self.root is not None else None,
            depth=self.depth,
            name_contains=self.name_contains,
            native_types=self.native_types,
            revision=(
                ObservationRevision(value=self.revision) if self.revision is not None else None
            ),
            cursor=ObservationCursor(value=self.cursor) if self.cursor is not None else None,
            limit=self.limit,
        )

    @classmethod
    def from_core(cls, value: HierarchyQuery) -> HierarchyReadParams:
        """Create canonical wire params from one validated core query."""
        return cls(
            root=value.root.value if value.root is not None else None,
            depth=value.depth,
            name_contains=value.name_contains,
            native_types=value.native_types,
            revision=value.revision.value if value.revision is not None else None,
            cursor=value.cursor.value if value.cursor is not None else None,
            limit=value.limit,
        )


class HierarchyEntryValue(ContractModel):
    """One flat bounded engine-native hierarchy entry."""

    reference: ObservationObjectReference
    display_name: HierarchyName
    native_type: HierarchyNativeType
    parent: ObservationObjectReference | None
    child_count: int = Field(ge=0, le=MAX_JSON_INTEGER)
    component_type_count: int = Field(ge=0, le=MAX_JSON_INTEGER)
    component_types: HierarchyComponentTypes
    components_truncated: bool
    extensions: EngineFactValues

    @model_validator(mode="after")
    def validate_summary(self) -> HierarchyEntryValue:
        """Require a non-cyclic parent and exact component truncation."""
        if self.parent == self.reference:
            raise ValueError("hierarchy entry cannot parent itself")
        if self.component_type_count < len(self.component_types):
            raise ValueError("hierarchy component-type count is too small")
        if self.components_truncated != (self.component_type_count > len(self.component_types)):
            raise ValueError("hierarchy component truncation is inconsistent")
        return self

    def to_core(self) -> HierarchyEntry:
        """Convert one boundary entry without engine-specific reflection data."""
        return HierarchyEntry(
            reference=RunObjectReference(value=self.reference),
            display_name=self.display_name,
            native_type=self.native_type,
            parent=RunObjectReference(value=self.parent) if self.parent is not None else None,
            child_count=self.child_count,
            component_type_count=self.component_type_count,
            component_types=self.component_types,
            components_truncated=self.components_truncated,
            extensions=engine_facts_to_core(self.extensions),
        )

    @classmethod
    def from_core(cls, value: HierarchyEntry) -> HierarchyEntryValue:
        """Create an exact result value from one validated core entry."""
        return cls(
            reference=value.reference.value,
            display_name=value.display_name,
            native_type=value.native_type,
            parent=value.parent.value if value.parent is not None else None,
            child_count=value.child_count,
            component_type_count=value.component_type_count,
            component_types=value.component_types,
            components_truncated=value.components_truncated,
            extensions=engine_facts_from_core(value.extensions),
        )


class HierarchyReadResult(ContractModel):
    """One exact revision-consistent hierarchy page."""

    revision: ObservationRevisionValue
    observed_at_unix_ms: ObservationUnixMilliseconds
    entries: Annotated[
        tuple[HierarchyEntryValue, ...],
        BeforeValidator(freeze_sequence),
        Field(max_length=MAX_HIERARCHY_PAGE_ENTRIES),
    ]
    truncated: bool
    next_cursor: ObservationCursorValue | None

    @model_validator(mode="after")
    def validate_page(self) -> HierarchyReadResult:
        """Require unique refs and cursor-backed truncation."""
        references = tuple(entry.reference for entry in self.entries)
        if len(set(references)) != len(references):
            raise ValueError("hierarchy page references must be unique")
        if self.truncated != (self.next_cursor is not None):
            raise ValueError("hierarchy truncation is inconsistent")
        return self

    def to_core(self, *, query: HierarchyQuery) -> HierarchyPage:
        """Convert and correlate a strict response with its owning query."""
        page = HierarchyPage(
            stamp=ObservationStamp(
                revision=ObservationRevision(value=self.revision),
                observed_at_unix_ms=self.observed_at_unix_ms,
            ),
            entries=tuple(entry.to_core() for entry in self.entries),
            truncated=self.truncated,
            next_cursor=(
                ObservationCursor(value=self.next_cursor) if self.next_cursor is not None else None
            ),
        )
        validate_hierarchy_page(page, query)
        return page

    @classmethod
    def from_core(
        cls,
        value: HierarchyPage,
        *,
        query: HierarchyQuery,
    ) -> HierarchyReadResult:
        """Create one result after correlating it with its owning query."""
        validate_hierarchy_page(value, query)
        return cls(
            revision=value.stamp.revision.value,
            observed_at_unix_ms=value.stamp.observed_at_unix_ms,
            entries=tuple(HierarchyEntryValue.from_core(entry) for entry in value.entries),
            truncated=value.truncated,
            next_cursor=value.next_cursor.value if value.next_cursor is not None else None,
        )


class HierarchyReadRequest(ContractModel):
    """Exact JSON-RPC hierarchy request."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    method: Literal["toqraq.hierarchy.read"]
    params: HierarchyReadParams

    @classmethod
    def from_core(cls, *, request_id: str, query: HierarchyQuery) -> HierarchyReadRequest:
        """Bind one pure query to a validated request ID and method."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            method=HIERARCHY_READ_METHOD,
            params=HierarchyReadParams.from_core(query),
        )


class HierarchyReadResponse(ContractModel):
    """Exact JSON-RPC hierarchy success response."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    result: HierarchyReadResult

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        value: HierarchyPage,
        query: HierarchyQuery,
    ) -> HierarchyReadResponse:
        """Bind one request-correlated page to its validated ID."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            result=HierarchyReadResult.from_core(value, query=query),
        )
