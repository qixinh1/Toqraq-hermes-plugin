"""Immutable feature-readiness states and safe failure facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from .error_values import ErrorFields, freeze_error_fields
from .errors import (
    APPLICATION_ERROR_TYPES,
    ErrorCategory,
    SessionStateError,
    ToqraqError,
)
from .trace import TraceId


class FeatureReadiness(StrEnum):
    """Independent readiness states for one active game run."""

    UNAVAILABLE = "unavailable"
    CONNECTING = "connecting"
    READY = "ready"
    FAILED = "failed"


class ReadinessFeature(StrEnum):
    """Feature groups that may own one readiness failure fact."""

    PREVIEW = "preview"
    PERCEPTION = "perception"
    CONTROL = "control"


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadinessFailure:
    """Immutable public-safe failure fact with no retained exception cause."""

    code: str
    category: ErrorCategory
    features: frozenset[ReadinessFeature]
    parameters: ErrorFields = field(default_factory=lambda: MappingProxyType({}))
    details: ErrorFields = field(default_factory=lambda: MappingProxyType({}))
    trace_id: TraceId

    def __post_init__(self) -> None:
        """Keep only registered, bounded, immutable application-error facts."""
        if not isinstance(self.category, ErrorCategory):
            raise ValueError("readiness failure category is invalid")
        if (
            not isinstance(self.features, frozenset)
            or not self.features
            or any(not isinstance(feature, ReadinessFeature) for feature in self.features)
        ):
            raise ValueError("readiness failure features are invalid")
        if not isinstance(self.code, str) or not any(
            error_type.code == self.code and error_type.category is self.category
            for error_type in APPLICATION_ERROR_TYPES
        ):
            raise ValueError("readiness failure code or category is invalid")
        if not isinstance(self.trace_id, TraceId):
            raise ValueError("readiness failure trace ID is invalid")
        object.__setattr__(self, "parameters", freeze_error_fields(self.parameters))
        object.__setattr__(self, "details", freeze_error_fields(self.details))

    @classmethod
    def from_error(
        cls,
        error: ToqraqError,
        *,
        features: frozenset[ReadinessFeature],
    ) -> ReadinessFailure:
        """Copy safe facts from an application error without retaining its cause."""
        if not isinstance(error, ToqraqError):
            raise ValueError("readiness failure source is invalid")
        return cls(
            code=error.code,
            category=error.category,
            features=features,
            parameters=error.parameters,
            details=error.details,
            trace_id=error.trace_id,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class FeatureReadinessSnapshot:
    """One immutable feature state and its terminal failure, when present."""

    state: FeatureReadiness
    failure: ReadinessFailure | None = None

    def __post_init__(self) -> None:
        """Require failures exactly when readiness has failed."""
        if not isinstance(self.state, FeatureReadiness):
            raise ValueError("feature readiness state is invalid")
        if self.state is FeatureReadiness.FAILED:
            if not isinstance(self.failure, ReadinessFailure):
                raise ValueError("failed readiness requires a safe failure")
        elif self.failure is not None:
            raise ValueError("non-failed readiness cannot retain a failure")


CONNECTING_READINESS = FeatureReadinessSnapshot(state=FeatureReadiness.CONNECTING)
UNAVAILABLE_READINESS = FeatureReadinessSnapshot(state=FeatureReadiness.UNAVAILABLE)


def ready_readiness(current: FeatureReadinessSnapshot) -> FeatureReadinessSnapshot:
    """Advance one connecting feature to ready."""
    if current.state is not FeatureReadiness.CONNECTING:
        raise SessionStateError(details={"reason": "readiness_transition_not_allowed"})
    return FeatureReadinessSnapshot(state=FeatureReadiness.READY)


def failed_readiness(
    current: FeatureReadinessSnapshot,
    failure: ReadinessFailure,
) -> FeatureReadinessSnapshot:
    """Advance a connecting or ready feature to failed."""
    if not isinstance(failure, ReadinessFailure):
        raise ValueError("readiness failure is invalid")
    if current.state not in {FeatureReadiness.CONNECTING, FeatureReadiness.READY}:
        raise SessionStateError(details={"reason": "readiness_transition_not_allowed"})
    return FeatureReadinessSnapshot(state=FeatureReadiness.FAILED, failure=failure)


def unavailable_readiness(
    current: FeatureReadinessSnapshot,
) -> FeatureReadinessSnapshot:
    """Withdraw a non-failed live feature while preserving its failure fact."""
    if current.state is FeatureReadiness.FAILED:
        return current
    return UNAVAILABLE_READINESS
