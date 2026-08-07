"""Pure runtime-diagnostic stream values and the focused read port."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from .bridge import MAX_BRIDGE_RUN_REVISION
from .observation import (
    ObservationCursor,
    ObservationRevision,
    ObservationStamp,
    validate_observation_count,
    validate_observation_label,
    validate_observation_text,
    validate_observation_timestamp,
)
from .runtime import validate_namespaced_id

MAX_DIAGNOSTIC_SOURCE_FILTERS = 16
MAX_DIAGNOSTIC_RECORDS = 200
MAX_DIAGNOSTIC_DETAILS = 8
MAX_DIAGNOSTIC_CODE_BYTES = 128
MAX_DIAGNOSTIC_SUMMARY_BYTES = 512
MAX_DIAGNOSTIC_DETAIL_BYTES = 1_024
MAX_DIAGNOSTIC_RESOURCE_BYTES = 1_024


class DiagnosticSeverity(StrEnum):
    """Closed severity ordering shared by every supported engine."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


@dataclass(frozen=True, slots=True, kw_only=True)
class DiagnosticLocation:
    """Bounded engine or project resource position without source contents."""

    resource: str
    line: int | None
    column: int | None

    def __post_init__(self) -> None:
        """Reject unbounded resource labels and invalid one-based positions."""
        validate_observation_label(
            self.resource,
            maximum_bytes=MAX_DIAGNOSTIC_RESOURCE_BYTES,
        )
        _validate_optional_position(self.line, label="diagnostic line")
        _validate_optional_position(self.column, label="diagnostic column")


@dataclass(frozen=True, slots=True, kw_only=True)
class DiagnosticRecord:
    """One strictly sequenced bounded native runtime diagnostic."""

    sequence: int
    occurred_at_unix_ms: int
    source_id: str
    severity: DiagnosticSeverity
    code: str | None
    summary: str
    details: tuple[str, ...]
    location: DiagnosticLocation | None

    def __post_init__(self) -> None:
        """Validate sequence, source identity, prose budgets, and location."""
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or not 1 <= self.sequence <= MAX_BRIDGE_RUN_REVISION
        ):
            raise ValueError("diagnostic sequence is invalid")
        validate_observation_timestamp(self.occurred_at_unix_ms)
        validate_namespaced_id(self.source_id)
        if not isinstance(self.severity, DiagnosticSeverity):
            raise ValueError("diagnostic severity is invalid")
        if self.code is not None:
            validate_observation_label(
                self.code,
                maximum_bytes=MAX_DIAGNOSTIC_CODE_BYTES,
            )
        validate_observation_text(
            self.summary,
            maximum_bytes=MAX_DIAGNOSTIC_SUMMARY_BYTES,
            allow_empty=False,
        )
        if not isinstance(self.details, tuple) or len(self.details) > MAX_DIAGNOSTIC_DETAILS:
            raise ValueError("diagnostic detail collection is invalid")
        for detail in self.details:
            validate_observation_text(
                detail,
                maximum_bytes=MAX_DIAGNOSTIC_DETAIL_BYTES,
                allow_empty=False,
            )
        if self.location is not None and not isinstance(self.location, DiagnosticLocation):
            raise ValueError("diagnostic location is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class DiagnosticsQuery:
    """Explicit diagnostic filters and revision-bound continuation position."""

    source_ids: tuple[str, ...]
    severities: tuple[DiagnosticSeverity, ...]
    revision: ObservationRevision | None
    cursor: ObservationCursor | None
    limit: int

    def __post_init__(self) -> None:
        """Reject ambiguous filters, stale cursor shape, and unbounded reads."""
        if (
            not isinstance(self.source_ids, tuple)
            or len(self.source_ids) > MAX_DIAGNOSTIC_SOURCE_FILTERS
            or len(set(self.source_ids)) != len(self.source_ids)
        ):
            raise ValueError("diagnostic source selection is invalid")
        for source_id in self.source_ids:
            validate_namespaced_id(source_id)
        if (
            not isinstance(self.severities, tuple)
            or len(self.severities) > len(DiagnosticSeverity)
            or any(not isinstance(value, DiagnosticSeverity) for value in self.severities)
            or len(set(self.severities)) != len(self.severities)
        ):
            raise ValueError("diagnostic severity selection is invalid")
        if self.revision is not None and not isinstance(self.revision, ObservationRevision):
            raise ValueError("diagnostic revision is invalid")
        if self.cursor is not None and not isinstance(self.cursor, ObservationCursor):
            raise ValueError("diagnostic cursor is invalid")
        if self.cursor is not None and self.revision is None:
            raise ValueError("diagnostic cursor requires its revision")
        if (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or not 1 <= self.limit <= MAX_DIAGNOSTIC_RECORDS
        ):
            raise ValueError("diagnostic record limit is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class DiagnosticsPage:
    """One revision-consistent page from a monotonic diagnostic stream."""

    stamp: ObservationStamp
    records: tuple[DiagnosticRecord, ...]
    truncated: bool
    next_cursor: ObservationCursor | None

    def __post_init__(self) -> None:
        """Require exact ordering and cursor-backed truncation."""
        if not isinstance(self.stamp, ObservationStamp):
            raise ValueError("diagnostic observation stamp is invalid")
        if (
            not isinstance(self.records, tuple)
            or len(self.records) > MAX_DIAGNOSTIC_RECORDS
            or any(not isinstance(record, DiagnosticRecord) for record in self.records)
        ):
            raise ValueError("diagnostic page records are invalid")
        sequences = tuple(record.sequence for record in self.records)
        if sequences != tuple(sorted(set(sequences))):
            raise ValueError("diagnostic records are not strictly sequenced")
        if self.next_cursor is not None and not isinstance(
            self.next_cursor,
            ObservationCursor,
        ):
            raise ValueError("diagnostic continuation cursor is invalid")
        if type(self.truncated) is not bool or self.truncated != (self.next_cursor is not None):
            raise ValueError("diagnostic truncation is inconsistent")


def validate_diagnostics_page(page: DiagnosticsPage, query: DiagnosticsQuery) -> None:
    """Correlate one diagnostic page with its exact filters and limit."""
    if not isinstance(page, DiagnosticsPage):
        raise TypeError("diagnostic page is invalid")
    if not isinstance(query, DiagnosticsQuery):
        raise TypeError("diagnostic query is invalid")
    if len(page.records) > query.limit:
        raise ValueError("diagnostic page exceeds its requested limit")
    if query.revision is not None and page.stamp.revision != query.revision:
        raise ValueError("diagnostic page revision does not match its query")
    if query.source_ids and any(
        record.source_id not in query.source_ids for record in page.records
    ):
        raise ValueError("diagnostic page source does not match its query")
    if query.severities and any(record.severity not in query.severities for record in page.records):
        raise ValueError("diagnostic page severity does not match its query")


@runtime_checkable
class DiagnosticsReader(Protocol):
    """Read-only engine boundary for bounded runtime diagnostics."""

    async def read(self, query: DiagnosticsQuery) -> DiagnosticsPage:
        """Read one ordered page without mutating engine diagnostic state."""
        ...


def _validate_optional_position(value: int | None, *, label: str) -> None:
    """Require a one-based cross-language-exact source position when present."""
    if value is None:
        return
    validate_observation_count(value, label=label)
    if value == 0:
        raise ValueError(f"{label} is invalid")
