"""Strict JSON-RPC contracts for bounded runtime diagnostic reads."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal, TypeAlias

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    StringConstraints,
    model_validator,
)

from ..core.diagnostics import (
    MAX_DIAGNOSTIC_CODE_BYTES,
    MAX_DIAGNOSTIC_DETAIL_BYTES,
    MAX_DIAGNOSTIC_DETAILS,
    MAX_DIAGNOSTIC_RECORDS,
    MAX_DIAGNOSTIC_RESOURCE_BYTES,
    MAX_DIAGNOSTIC_SOURCE_FILTERS,
    MAX_DIAGNOSTIC_SUMMARY_BYTES,
    DiagnosticLocation,
    DiagnosticRecord,
    DiagnosticSeverity,
    DiagnosticsPage,
    DiagnosticsQuery,
    validate_diagnostics_page,
)
from ..core.observation import ObservationCursor, ObservationRevision, ObservationStamp
from ..core.observation import validate_observation_label as validate_core_label
from ..core.observation import validate_observation_text as validate_core_text
from .base import ContractModel, freeze_sequence
from .bridge import JSON_RPC_VERSION
from .bridge_observation import (
    ObservationCursorValue,
    ObservationRevisionValue,
    ObservationUnixMilliseconds,
)
from .bridge_rpc import BridgeHostRequestId
from .identifiers import MAX_JSON_INTEGER, CapabilityId

DIAGNOSTICS_READ_METHOD: Literal["toqraq.diagnostics.read"] = "toqraq.diagnostics.read"
DiagnosticSeverityValue: TypeAlias = Literal[
    "debug",
    "info",
    "warning",
    "error",
    "fatal",
]


def _bounded_label(maximum_bytes: int) -> Callable[[str], str]:
    """Create one exact UTF-8 label validator for a stable field bound."""

    def validate(value: str) -> str:
        return validate_core_label(value, maximum_bytes=maximum_bytes)

    return validate


def _bounded_text(maximum_bytes: int, *, allow_empty: bool) -> Callable[[str], str]:
    """Create one exact UTF-8 prose validator for a stable field bound."""

    def validate(value: str) -> str:
        return validate_core_text(
            value,
            maximum_bytes=maximum_bytes,
            allow_empty=allow_empty,
        )

    return validate


DiagnosticCode = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_DIAGNOSTIC_CODE_BYTES),
    AfterValidator(_bounded_label(MAX_DIAGNOSTIC_CODE_BYTES)),
]
DiagnosticSummary = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_DIAGNOSTIC_SUMMARY_BYTES),
    AfterValidator(_bounded_text(MAX_DIAGNOSTIC_SUMMARY_BYTES, allow_empty=False)),
]
DiagnosticDetail = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_DIAGNOSTIC_DETAIL_BYTES),
    AfterValidator(_bounded_text(MAX_DIAGNOSTIC_DETAIL_BYTES, allow_empty=False)),
]
DiagnosticResource = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_DIAGNOSTIC_RESOURCE_BYTES),
    AfterValidator(_bounded_label(MAX_DIAGNOSTIC_RESOURCE_BYTES)),
]


class DiagnosticLocationValue(ContractModel):
    """One bounded engine or project resource position."""

    resource: DiagnosticResource
    line: int | None = Field(default=None, ge=1, le=MAX_JSON_INTEGER)
    column: int | None = Field(default=None, ge=1, le=MAX_JSON_INTEGER)

    def to_core(self) -> DiagnosticLocation:
        """Convert one strict source position to core."""
        return DiagnosticLocation(resource=self.resource, line=self.line, column=self.column)

    @classmethod
    def from_core(cls, value: DiagnosticLocation) -> DiagnosticLocationValue:
        """Create one exact source position from core."""
        return cls(resource=value.resource, line=value.line, column=value.column)


class DiagnosticRecordValue(ContractModel):
    """One strictly sequenced bounded native runtime diagnostic."""

    sequence: int = Field(ge=1, le=MAX_JSON_INTEGER)
    occurred_at_unix_ms: ObservationUnixMilliseconds
    source_id: CapabilityId
    severity: DiagnosticSeverityValue
    code: DiagnosticCode | None = None
    summary: DiagnosticSummary
    details: Annotated[
        tuple[DiagnosticDetail, ...],
        BeforeValidator(freeze_sequence),
        Field(max_length=MAX_DIAGNOSTIC_DETAILS),
    ]
    location: DiagnosticLocationValue | None = None

    def to_core(self) -> DiagnosticRecord:
        """Convert one strict diagnostic record to its pure value."""
        return DiagnosticRecord(
            sequence=self.sequence,
            occurred_at_unix_ms=self.occurred_at_unix_ms,
            source_id=self.source_id,
            severity=DiagnosticSeverity(self.severity),
            code=self.code,
            summary=self.summary,
            details=self.details,
            location=self.location.to_core() if self.location is not None else None,
        )

    @classmethod
    def from_core(cls, value: DiagnosticRecord) -> DiagnosticRecordValue:
        """Create one exact diagnostic record from core."""
        return cls(
            sequence=value.sequence,
            occurred_at_unix_ms=value.occurred_at_unix_ms,
            source_id=value.source_id,
            severity=value.severity.value,
            code=value.code,
            summary=value.summary,
            details=value.details,
            location=(
                DiagnosticLocationValue.from_core(value.location)
                if value.location is not None
                else None
            ),
        )


def _unique_source_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    """Reject duplicate source filters."""
    if len(set(values)) != len(values):
        raise ValueError("diagnostic source selection must be unique")
    return values


def _unique_severities(
    values: tuple[DiagnosticSeverityValue, ...],
) -> tuple[DiagnosticSeverityValue, ...]:
    """Reject duplicate severity filters."""
    if len(set(values)) != len(values):
        raise ValueError("diagnostic severity selection must be unique")
    return values


DiagnosticSourceSelection: TypeAlias = Annotated[
    tuple[CapabilityId, ...],
    BeforeValidator(freeze_sequence),
    Field(max_length=MAX_DIAGNOSTIC_SOURCE_FILTERS),
    AfterValidator(_unique_source_ids),
]
DiagnosticSeveritySelection: TypeAlias = Annotated[
    tuple[DiagnosticSeverityValue, ...],
    BeforeValidator(freeze_sequence),
    Field(max_length=len(DiagnosticSeverity)),
    AfterValidator(_unique_severities),
]


class DiagnosticsReadParams(ContractModel):
    """Explicit diagnostic filters and revision-bound continuation."""

    source_ids: DiagnosticSourceSelection
    severities: DiagnosticSeveritySelection
    revision: ObservationRevisionValue | None = None
    cursor: ObservationCursorValue | None = None
    limit: int = Field(ge=1, le=MAX_DIAGNOSTIC_RECORDS)

    @model_validator(mode="after")
    def validate_cursor_revision(self) -> DiagnosticsReadParams:
        """Tie a continuation cursor to the revision that created it."""
        if self.cursor is not None and self.revision is None:
            raise ValueError("diagnostic cursor requires its revision")
        return self

    def to_core(self) -> DiagnosticsQuery:
        """Convert strict params to the focused pure diagnostic query."""
        return DiagnosticsQuery(
            source_ids=self.source_ids,
            severities=tuple(DiagnosticSeverity(value) for value in self.severities),
            revision=(
                ObservationRevision(value=self.revision) if self.revision is not None else None
            ),
            cursor=ObservationCursor(value=self.cursor) if self.cursor is not None else None,
            limit=self.limit,
        )

    @classmethod
    def from_core(cls, value: DiagnosticsQuery) -> DiagnosticsReadParams:
        """Create canonical wire params from one validated pure query."""
        return cls(
            source_ids=value.source_ids,
            severities=tuple(severity.value for severity in value.severities),
            revision=value.revision.value if value.revision is not None else None,
            cursor=value.cursor.value if value.cursor is not None else None,
            limit=value.limit,
        )


class DiagnosticsReadResult(ContractModel):
    """One exact revision-consistent page from a diagnostic stream."""

    revision: ObservationRevisionValue
    observed_at_unix_ms: ObservationUnixMilliseconds
    records: Annotated[
        tuple[DiagnosticRecordValue, ...],
        BeforeValidator(freeze_sequence),
        Field(max_length=MAX_DIAGNOSTIC_RECORDS),
    ]
    truncated: bool
    next_cursor: ObservationCursorValue | None

    @model_validator(mode="after")
    def validate_page(self) -> DiagnosticsReadResult:
        """Require strict sequence and cursor-backed truncation."""
        sequences = tuple(record.sequence for record in self.records)
        if sequences != tuple(sorted(set(sequences))):
            raise ValueError("diagnostic records are not strictly sequenced")
        if self.truncated != (self.next_cursor is not None):
            raise ValueError("diagnostic truncation is inconsistent")
        return self

    def to_core(self, *, query: DiagnosticsQuery) -> DiagnosticsPage:
        """Convert and correlate a strict response with its owning query."""
        page = DiagnosticsPage(
            stamp=ObservationStamp(
                revision=ObservationRevision(value=self.revision),
                observed_at_unix_ms=self.observed_at_unix_ms,
            ),
            records=tuple(record.to_core() for record in self.records),
            truncated=self.truncated,
            next_cursor=(
                ObservationCursor(value=self.next_cursor) if self.next_cursor is not None else None
            ),
        )
        validate_diagnostics_page(page, query)
        return page

    @classmethod
    def from_core(
        cls,
        value: DiagnosticsPage,
        *,
        query: DiagnosticsQuery,
    ) -> DiagnosticsReadResult:
        """Create one result after correlating it with its owning query."""
        validate_diagnostics_page(value, query)
        return cls(
            revision=value.stamp.revision.value,
            observed_at_unix_ms=value.stamp.observed_at_unix_ms,
            records=tuple(DiagnosticRecordValue.from_core(record) for record in value.records),
            truncated=value.truncated,
            next_cursor=value.next_cursor.value if value.next_cursor is not None else None,
        )


class DiagnosticsReadRequest(ContractModel):
    """Exact JSON-RPC diagnostic read request."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    method: Literal["toqraq.diagnostics.read"]
    params: DiagnosticsReadParams

    @classmethod
    def from_core(cls, *, request_id: str, query: DiagnosticsQuery) -> DiagnosticsReadRequest:
        """Bind one pure query to a validated request ID and method."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            method=DIAGNOSTICS_READ_METHOD,
            params=DiagnosticsReadParams.from_core(query),
        )


class DiagnosticsReadResponse(ContractModel):
    """Exact JSON-RPC diagnostic success response."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    result: DiagnosticsReadResult

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        value: DiagnosticsPage,
        query: DiagnosticsQuery,
    ) -> DiagnosticsReadResponse:
        """Bind one request-correlated page to its validated ID."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            result=DiagnosticsReadResult.from_core(value, query=query),
        )
