"""Pure bounded performance values and the focused metrics read port."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, TypeAlias, runtime_checkable

from .observation import (
    ObservationRevision,
    ObservationStamp,
    require_exact_integer,
    validate_observation_count,
    validate_observation_timestamp,
)
from .runtime import validate_namespaced_id

MAX_METRIC_GROUPS = 16
MAX_METRIC_NAMES = 64
MAX_METRIC_SAMPLES = 128
MAX_UNAVAILABLE_METRICS = 64


class MetricValueKind(StrEnum):
    """Closed scalar value shapes supported by the common metrics port."""

    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"


MetricPayload: TypeAlias = bool | int | float


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricSample:
    """One namespaced typed sample with its own collection time."""

    name: str
    kind: MetricValueKind
    value: MetricPayload
    unit: str | None
    observed_at_unix_ms: int

    def __post_init__(self) -> None:
        """Reject ambiguous numeric shapes and non-namespaced metadata."""
        validate_namespaced_id(self.name)
        if not isinstance(self.kind, MetricValueKind):
            raise ValueError("metric value kind is invalid")
        if self.kind is MetricValueKind.BOOLEAN:
            if type(self.value) is not bool:
                raise ValueError("boolean metric value is invalid")
        elif self.kind is MetricValueKind.INTEGER:
            if not isinstance(self.value, int) or isinstance(self.value, bool):
                raise ValueError("integer metric value is invalid")
            require_exact_integer(self.value, label="integer metric value")
        elif type(self.value) is not float or not math.isfinite(self.value):
            raise ValueError("number metric value is invalid")
        if self.unit is not None:
            validate_namespaced_id(self.unit)
        validate_observation_timestamp(self.observed_at_unix_ms)


class MetricUnavailableReason(StrEnum):
    """Closed safe reasons why an explicitly selected metric is absent."""

    UNSUPPORTED = "unsupported"
    NOT_READY = "not_ready"
    UNAVAILABLE = "unavailable"
    COST_LIMIT = "cost_limit"


@dataclass(frozen=True, slots=True, kw_only=True)
class UnavailableMetric:
    """One namespaced selection the engine could not provide now."""

    selection_id: str
    reason: MetricUnavailableReason

    def __post_init__(self) -> None:
        """Keep absence typed without embedding native diagnostic prose."""
        validate_namespaced_id(self.selection_id)
        if not isinstance(self.reason, MetricUnavailableReason):
            raise ValueError("unavailable metric reason is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricsQuery:
    """Explicit namespaced metric selection and bounded sample limit."""

    groups: tuple[str, ...]
    names: tuple[str, ...]
    revision: ObservationRevision | None
    limit: int

    def __post_init__(self) -> None:
        """Require at least one bounded unique group or metric name."""
        _validate_namespaced_selection(self.groups, maximum=MAX_METRIC_GROUPS, label="groups")
        _validate_namespaced_selection(self.names, maximum=MAX_METRIC_NAMES, label="names")
        if not self.groups and not self.names:
            raise ValueError("metrics query requires a group or name")
        if self.revision is not None and not isinstance(self.revision, ObservationRevision):
            raise ValueError("metrics revision is invalid")
        if (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or not 1 <= self.limit <= MAX_METRIC_SAMPLES
        ):
            raise ValueError("metric sample limit is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricsSnapshot:
    """One non-pageable revision-consistent bounded metric snapshot."""

    stamp: ObservationStamp
    samples: tuple[MetricSample, ...]
    total_count: int
    truncated: bool
    unavailable: tuple[UnavailableMetric, ...]
    collection_duration_microseconds: int

    def __post_init__(self) -> None:
        """Require unique names, exact truncation, absence, and cost bounds."""
        if not isinstance(self.stamp, ObservationStamp):
            raise ValueError("metrics observation stamp is invalid")
        if (
            not isinstance(self.samples, tuple)
            or len(self.samples) > MAX_METRIC_SAMPLES
            or any(not isinstance(sample, MetricSample) for sample in self.samples)
        ):
            raise ValueError("metric samples are invalid")
        sample_names = tuple(sample.name for sample in self.samples)
        if len(set(sample_names)) != len(sample_names):
            raise ValueError("metric sample names must be unique")
        validate_observation_count(self.total_count, label="metric total count")
        if self.total_count < len(self.samples):
            raise ValueError("metric total count is too small")
        if type(self.truncated) is not bool or self.truncated != (
            self.total_count > len(self.samples)
        ):
            raise ValueError("metric truncation is inconsistent")
        if (
            not isinstance(self.unavailable, tuple)
            or len(self.unavailable) > MAX_UNAVAILABLE_METRICS
            or any(not isinstance(value, UnavailableMetric) for value in self.unavailable)
        ):
            raise ValueError("unavailable metric collection is invalid")
        selection_ids = tuple(value.selection_id for value in self.unavailable)
        if len(set(selection_ids)) != len(selection_ids):
            raise ValueError("unavailable metric selections must be unique")
        validate_observation_count(
            self.collection_duration_microseconds,
            label="metric collection duration",
        )


def validate_metrics_snapshot(snapshot: MetricsSnapshot, query: MetricsQuery) -> None:
    """Correlate one metrics snapshot with its exact selection and limit."""
    if not isinstance(snapshot, MetricsSnapshot):
        raise TypeError("metrics snapshot is invalid")
    if not isinstance(query, MetricsQuery):
        raise TypeError("metrics query is invalid")
    if len(snapshot.samples) > query.limit:
        raise ValueError("metrics snapshot exceeds its requested limit")
    if query.revision is not None and snapshot.stamp.revision != query.revision:
        raise ValueError("metrics snapshot revision does not match its query")
    if any(not _metric_is_selected(sample.name, query) for sample in snapshot.samples):
        raise ValueError("metric sample does not match its query")
    requested = set(query.groups) | set(query.names)
    if any(value.selection_id not in requested for value in snapshot.unavailable):
        raise ValueError("unavailable metric does not match its query")


@runtime_checkable
class MetricsReader(Protocol):
    """Read-only engine boundary for a bounded performance snapshot."""

    async def read(self, query: MetricsQuery) -> MetricsSnapshot:
        """Collect selected metrics without changing engine state."""
        ...


def _validate_namespaced_selection(
    values: tuple[str, ...],
    *,
    maximum: int,
    label: str,
) -> None:
    """Require a bounded immutable unique namespaced selection."""
    if not isinstance(values, tuple) or len(values) > maximum or len(set(values)) != len(values):
        raise ValueError(f"metric {label} are invalid")
    for value in values:
        validate_namespaced_id(value)


def _metric_is_selected(name: str, query: MetricsQuery) -> bool:
    """Match one exact name or one namespaced descendant of a selected group."""
    return name in query.names or any(
        name == group or name.startswith(f"{group}.") for group in query.groups
    )
