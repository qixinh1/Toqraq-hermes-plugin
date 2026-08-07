"""Strict JSON-RPC contracts for selected runtime object reads."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, BeforeValidator, Field, model_validator

from ..core.object_inspection import (
    MAX_OBJECT_FIELD_GROUPS,
    MAX_OBJECT_REFERENCES,
    MAX_OBJECT_TOTAL_VALUE_BYTES,
    MAX_OBJECT_VALUE_TEXT_BYTES,
    ObjectFieldGroup,
    ObjectReadQuery,
    ObjectSnapshot,
    validate_object_snapshot,
)
from ..core.observation import ObservationRevision, ObservationStamp, RunObjectReference
from .base import ContractModel, freeze_sequence
from .bridge import JSON_RPC_VERSION
from .bridge_object_values import (
    ObjectSelectedGroupName,
    RuntimeObjectValue,
    selected_group,
)
from .bridge_observation import (
    ObservationObjectReference,
    ObservationRevisionValue,
    ObservationUnixMilliseconds,
)
from .bridge_rpc import BridgeHostRequestId

OBJECT_READ_METHOD: Literal["toqraq.object.read"] = "toqraq.object.read"


def _unique_references(values: tuple[str, ...]) -> tuple[str, ...]:
    """Reject duplicate work and ambiguous result correlation."""
    if len(set(values)) != len(values):
        raise ValueError("object read references must be unique")
    return values


def _unique_fields(
    values: tuple[ObjectSelectedGroupName, ...],
) -> tuple[ObjectSelectedGroupName, ...]:
    """Reject duplicate field-group selection."""
    if len(set(values)) != len(values):
        raise ValueError("object field selection must be unique")
    return values


ObjectReferences: TypeAlias = Annotated[
    tuple[ObservationObjectReference, ...],
    BeforeValidator(freeze_sequence),
    Field(min_length=1, max_length=MAX_OBJECT_REFERENCES),
    AfterValidator(_unique_references),
]
ObjectFieldSelection: TypeAlias = Annotated[
    tuple[ObjectSelectedGroupName, ...],
    BeforeValidator(freeze_sequence),
    Field(min_length=1, max_length=MAX_OBJECT_FIELD_GROUPS),
    AfterValidator(_unique_fields),
]


class ObjectReadParams(ContractModel):
    """Explicit object refs, field groups, revision, and byte budgets."""

    references: ObjectReferences
    fields: ObjectFieldSelection
    revision: ObservationRevisionValue | None = None
    per_value_max_bytes: int = Field(ge=1, le=MAX_OBJECT_VALUE_TEXT_BYTES)
    total_value_max_bytes: int = Field(ge=1, le=MAX_OBJECT_TOTAL_VALUE_BYTES)

    @model_validator(mode="after")
    def validate_byte_limits(self) -> ObjectReadParams:
        """Ensure the total budget can contain any permitted single value."""
        if self.total_value_max_bytes < self.per_value_max_bytes:
            raise ValueError("object total-value byte limit is invalid")
        return self

    def to_core(self) -> ObjectReadQuery:
        """Convert strict params to the focused pure object query."""
        return ObjectReadQuery(
            references=tuple(RunObjectReference(value=value) for value in self.references),
            fields=tuple(ObjectFieldGroup(value) for value in self.fields),
            revision=(
                ObservationRevision(value=self.revision) if self.revision is not None else None
            ),
            per_value_max_bytes=self.per_value_max_bytes,
            total_value_max_bytes=self.total_value_max_bytes,
        )

    @classmethod
    def from_core(cls, value: ObjectReadQuery) -> ObjectReadParams:
        """Create canonical wire params from one validated pure query."""
        return cls(
            references=tuple(reference.value for reference in value.references),
            fields=tuple(field.value for field in value.fields),
            revision=value.revision.value if value.revision is not None else None,
            per_value_max_bytes=value.per_value_max_bytes,
            total_value_max_bytes=value.total_value_max_bytes,
        )


class ObjectReadResult(ContractModel):
    """One revision-consistent snapshot containing exactly selected groups."""

    revision: ObservationRevisionValue
    observed_at_unix_ms: ObservationUnixMilliseconds
    fields: ObjectFieldSelection
    objects: Annotated[
        tuple[RuntimeObjectValue, ...],
        BeforeValidator(freeze_sequence),
        Field(min_length=1, max_length=MAX_OBJECT_REFERENCES),
    ]
    value_bytes: int = Field(ge=0, le=MAX_OBJECT_TOTAL_VALUE_BYTES)

    @model_validator(mode="after")
    def validate_snapshot(self) -> ObjectReadResult:
        """Require unique refs and exact selected group presence."""
        references = tuple(value.reference for value in self.objects)
        if len(set(references)) != len(references):
            raise ValueError("object snapshot references must be unique")
        fields = set(self.fields)
        for value in self.objects:
            if {selected_group(group) for group in value.groups} != fields:
                raise ValueError("object snapshot groups do not match its selection")
        return self

    def to_core(self, *, query: ObjectReadQuery) -> ObjectSnapshot:
        """Convert and correlate a strict response with its owning query."""
        snapshot = ObjectSnapshot(
            stamp=ObservationStamp(
                revision=ObservationRevision(value=self.revision),
                observed_at_unix_ms=self.observed_at_unix_ms,
            ),
            fields=tuple(ObjectFieldGroup(value) for value in self.fields),
            objects=tuple(value.to_core() for value in self.objects),
            value_bytes=self.value_bytes,
        )
        validate_object_snapshot(snapshot, query)
        return snapshot

    @classmethod
    def from_core(
        cls,
        value: ObjectSnapshot,
        *,
        query: ObjectReadQuery,
    ) -> ObjectReadResult:
        """Create one result after correlating it with its owning query."""
        validate_object_snapshot(value, query)
        return cls(
            revision=value.stamp.revision.value,
            observed_at_unix_ms=value.stamp.observed_at_unix_ms,
            fields=tuple(field.value for field in value.fields),
            objects=tuple(RuntimeObjectValue.from_core(item) for item in value.objects),
            value_bytes=value.value_bytes,
        )


class ObjectReadRequest(ContractModel):
    """Exact JSON-RPC selected-object request."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    method: Literal["toqraq.object.read"]
    params: ObjectReadParams

    @classmethod
    def from_core(cls, *, request_id: str, query: ObjectReadQuery) -> ObjectReadRequest:
        """Bind one pure query to a validated request ID and method."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            method=OBJECT_READ_METHOD,
            params=ObjectReadParams.from_core(query),
        )


class ObjectReadResponse(ContractModel):
    """Exact JSON-RPC selected-object success response."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    result: ObjectReadResult

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        value: ObjectSnapshot,
        query: ObjectReadQuery,
    ) -> ObjectReadResponse:
        """Bind one request-correlated snapshot to its validated ID."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            result=ObjectReadResult.from_core(value, query=query),
        )
