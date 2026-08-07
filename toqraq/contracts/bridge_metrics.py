"""Strict JSON-RPC contracts for bounded runtime metric reads."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, BeforeValidator, Field, model_validator

from ..core.metrics import (
    MAX_METRIC_GROUPS,
    MAX_METRIC_NAMES,
    MAX_METRIC_SAMPLES,
    MAX_UNAVAILABLE_METRICS,
    MetricSample,
    MetricsQuery,
    MetricsSnapshot,
    MetricUnavailableReason,
    MetricValueKind,
    UnavailableMetric,
    validate_metrics_snapshot,
)
from ..core.observation import ObservationRevision, ObservationStamp
from .base import ContractModel, freeze_sequence
from .bridge import JSON_RPC_VERSION
from .bridge_observation import (
    ExactBridgeInteger,
    ObservationRevisionValue,
    ObservationUnixMilliseconds,
)
from .bridge_rpc import BridgeHostRequestId
from .identifiers import MAX_JSON_INTEGER, CapabilityId

METRICS_READ_METHOD: Literal["toqraq.metrics.read"] = "toqraq.metrics.read"
MetricUnavailableReasonValue: TypeAlias = Literal[
    "unsupported",
    "not_ready",
    "unavailable",
    "cost_limit",
]


class MetricSampleBase(ContractModel):
    """Namespaced identity and time shared by every metric scalar shape."""

    name: CapabilityId
    unit: CapabilityId | None
    observed_at_unix_ms: ObservationUnixMilliseconds


class BooleanMetricSampleValue(MetricSampleBase):
    """One explicitly boolean metric sample."""

    kind: Literal["boolean"]
    value: bool

    def to_core(self) -> MetricSample:
        """Convert one boolean sample to core."""
        return MetricSample(
            name=self.name,
            kind=MetricValueKind.BOOLEAN,
            value=self.value,
            unit=self.unit,
            observed_at_unix_ms=self.observed_at_unix_ms,
        )


class IntegerMetricSampleValue(MetricSampleBase):
    """One cross-language-exact integer metric sample."""

    kind: Literal["integer"]
    value: ExactBridgeInteger

    def to_core(self) -> MetricSample:
        """Convert one integer sample to core."""
        return MetricSample(
            name=self.name,
            kind=MetricValueKind.INTEGER,
            value=self.value,
            unit=self.unit,
            observed_at_unix_ms=self.observed_at_unix_ms,
        )


class NumberMetricSampleValue(MetricSampleBase):
    """One finite number metric sample."""

    kind: Literal["number"]
    value: float = Field(allow_inf_nan=False)

    def to_core(self) -> MetricSample:
        """Convert one number sample to core."""
        return MetricSample(
            name=self.name,
            kind=MetricValueKind.NUMBER,
            value=self.value,
            unit=self.unit,
            observed_at_unix_ms=self.observed_at_unix_ms,
        )


MetricSampleValue: TypeAlias = Annotated[
    BooleanMetricSampleValue | IntegerMetricSampleValue | NumberMetricSampleValue,
    Field(discriminator="kind"),
]


class UnavailableMetricValue(ContractModel):
    """One selected metric or group unavailable in the current snapshot."""

    selection_id: CapabilityId
    reason: MetricUnavailableReasonValue

    def to_core(self) -> UnavailableMetric:
        """Convert one typed absence to core."""
        return UnavailableMetric(
            selection_id=self.selection_id,
            reason=MetricUnavailableReason(self.reason),
        )

    @classmethod
    def from_core(cls, value: UnavailableMetric) -> UnavailableMetricValue:
        """Create one exact typed absence from core."""
        return cls(
            selection_id=value.selection_id,
            reason=value.reason.value,
        )


def _unique_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    """Reject duplicate namespaced metric selections."""
    if len(set(values)) != len(values):
        raise ValueError("metric selection IDs must be unique")
    return values


MetricGroups: TypeAlias = Annotated[
    tuple[CapabilityId, ...],
    BeforeValidator(freeze_sequence),
    Field(max_length=MAX_METRIC_GROUPS),
    AfterValidator(_unique_ids),
]
MetricNames: TypeAlias = Annotated[
    tuple[CapabilityId, ...],
    BeforeValidator(freeze_sequence),
    Field(max_length=MAX_METRIC_NAMES),
    AfterValidator(_unique_ids),
]


class MetricsReadParams(ContractModel):
    """Explicit metric group/name selection and bounded sample limit."""

    groups: MetricGroups
    names: MetricNames
    revision: ObservationRevisionValue | None = None
    limit: int = Field(ge=1, le=MAX_METRIC_SAMPLES)

    @model_validator(mode="after")
    def validate_selection(self) -> MetricsReadParams:
        """Require one deliberate group or metric-name selection."""
        if not self.groups and not self.names:
            raise ValueError("metrics query requires a group or name")
        return self

    def to_core(self) -> MetricsQuery:
        """Convert strict params to the focused pure metrics query."""
        return MetricsQuery(
            groups=self.groups,
            names=self.names,
            revision=(
                ObservationRevision(value=self.revision) if self.revision is not None else None
            ),
            limit=self.limit,
        )

    @classmethod
    def from_core(cls, value: MetricsQuery) -> MetricsReadParams:
        """Create canonical wire params from one validated pure query."""
        return cls(
            groups=value.groups,
            names=value.names,
            revision=value.revision.value if value.revision is not None else None,
            limit=value.limit,
        )


class MetricsReadResult(ContractModel):
    """One exact non-pageable typed performance snapshot."""

    revision: ObservationRevisionValue
    observed_at_unix_ms: ObservationUnixMilliseconds
    samples: Annotated[
        tuple[MetricSampleValue, ...],
        BeforeValidator(freeze_sequence),
        Field(max_length=MAX_METRIC_SAMPLES),
    ]
    total_count: int = Field(ge=0, le=MAX_JSON_INTEGER)
    truncated: bool
    unavailable: Annotated[
        tuple[UnavailableMetricValue, ...],
        BeforeValidator(freeze_sequence),
        Field(max_length=MAX_UNAVAILABLE_METRICS),
    ]
    collection_duration_microseconds: int = Field(ge=0, le=MAX_JSON_INTEGER)

    @model_validator(mode="after")
    def validate_snapshot(self) -> MetricsReadResult:
        """Require unique sample/absence IDs and exact snapshot truncation."""
        sample_names = tuple(sample.name for sample in self.samples)
        if len(set(sample_names)) != len(sample_names):
            raise ValueError("metric sample names must be unique")
        if self.total_count < len(self.samples):
            raise ValueError("metric total count is too small")
        if self.truncated != (self.total_count > len(self.samples)):
            raise ValueError("metric truncation is inconsistent")
        unavailable_ids = tuple(value.selection_id for value in self.unavailable)
        if len(set(unavailable_ids)) != len(unavailable_ids):
            raise ValueError("unavailable metric selections must be unique")
        return self

    def to_core(self, *, query: MetricsQuery) -> MetricsSnapshot:
        """Convert and correlate a strict response with its owning query."""
        snapshot = MetricsSnapshot(
            stamp=ObservationStamp(
                revision=ObservationRevision(value=self.revision),
                observed_at_unix_ms=self.observed_at_unix_ms,
            ),
            samples=tuple(sample.to_core() for sample in self.samples),
            total_count=self.total_count,
            truncated=self.truncated,
            unavailable=tuple(value.to_core() for value in self.unavailable),
            collection_duration_microseconds=self.collection_duration_microseconds,
        )
        validate_metrics_snapshot(snapshot, query)
        return snapshot

    @classmethod
    def from_core(
        cls,
        value: MetricsSnapshot,
        *,
        query: MetricsQuery,
    ) -> MetricsReadResult:
        """Create one result after correlating it with its owning query."""
        validate_metrics_snapshot(value, query)
        return cls(
            revision=value.stamp.revision.value,
            observed_at_unix_ms=value.stamp.observed_at_unix_ms,
            samples=tuple(_metric_sample_from_core(sample) for sample in value.samples),
            total_count=value.total_count,
            truncated=value.truncated,
            unavailable=tuple(UnavailableMetricValue.from_core(item) for item in value.unavailable),
            collection_duration_microseconds=value.collection_duration_microseconds,
        )


class MetricsReadRequest(ContractModel):
    """Exact JSON-RPC metrics read request."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    method: Literal["toqraq.metrics.read"]
    params: MetricsReadParams

    @classmethod
    def from_core(cls, *, request_id: str, query: MetricsQuery) -> MetricsReadRequest:
        """Bind one pure query to a validated request ID and method."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            method=METRICS_READ_METHOD,
            params=MetricsReadParams.from_core(query),
        )


class MetricsReadResponse(ContractModel):
    """Exact JSON-RPC metrics success response."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    result: MetricsReadResult

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        value: MetricsSnapshot,
        query: MetricsQuery,
    ) -> MetricsReadResponse:
        """Bind one request-correlated snapshot to its validated ID."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            result=MetricsReadResult.from_core(value, query=query),
        )


def _metric_sample_from_core(value: MetricSample) -> MetricSampleValue:
    """Map one validated core metric discriminator to its exact wire variant."""
    if value.kind is MetricValueKind.BOOLEAN:
        assert isinstance(value.value, bool)
        return BooleanMetricSampleValue(
            kind="boolean",
            name=value.name,
            value=value.value,
            unit=value.unit,
            observed_at_unix_ms=value.observed_at_unix_ms,
        )
    if value.kind is MetricValueKind.INTEGER:
        assert isinstance(value.value, int) and not isinstance(value.value, bool)
        return IntegerMetricSampleValue(
            kind="integer",
            name=value.name,
            value=value.value,
            unit=value.unit,
            observed_at_unix_ms=value.observed_at_unix_ms,
        )
    assert isinstance(value.value, float)
    return NumberMetricSampleValue(
        kind="number",
        name=value.name,
        value=value.value,
        unit=value.unit,
        observed_at_unix_ms=value.observed_at_unix_ms,
    )
