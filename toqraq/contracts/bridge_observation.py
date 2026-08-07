"""Strict shared scalar values for engine-bridge observation methods."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, BeforeValidator, Field, StringConstraints

from ..core.bridge import MAX_BRIDGE_RUN_REVISION
from ..core.observation import (
    MAX_ENGINE_EXTENSION_FACTS,
    MAX_ENGINE_EXTENSION_TEXT_BYTES,
    MAX_OBSERVATION_TIMESTAMP,
    MAX_OBSERVATION_TOKEN_CHARACTERS,
    EngineFact,
    EngineFactKind,
    RunObjectReference,
    validate_engine_facts,
    validate_observation_text,
    validate_observation_token,
)
from .base import ContractModel, freeze_sequence
from .identifiers import CapabilityId

ObservationObjectReference = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=MAX_OBSERVATION_TOKEN_CHARACTERS,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
    AfterValidator(validate_observation_token),
]
ObservationRevisionValue = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=MAX_OBSERVATION_TOKEN_CHARACTERS,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
    AfterValidator(validate_observation_token),
]
ObservationCursorValue = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=MAX_OBSERVATION_TOKEN_CHARACTERS,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
    AfterValidator(validate_observation_token),
]
ObservationUnixMilliseconds = Annotated[
    int,
    Field(ge=0, le=MAX_OBSERVATION_TIMESTAMP),
]
ExactBridgeInteger = Annotated[
    int,
    Field(ge=-MAX_BRIDGE_RUN_REVISION, le=MAX_BRIDGE_RUN_REVISION),
]


def _validate_engine_text(value: str) -> str:
    """Apply the exact UTF-8 byte bound hidden by JSON Schema maxLength."""
    return validate_observation_text(
        value,
        maximum_bytes=MAX_ENGINE_EXTENSION_TEXT_BYTES,
    )


EngineFactText = Annotated[
    str,
    StringConstraints(max_length=MAX_ENGINE_EXTENSION_TEXT_BYTES),
    AfterValidator(_validate_engine_text),
]


class EngineTextFactValue(ContractModel):
    """One bounded namespaced engine text fact."""

    kind: Literal["text"]
    field_id: CapabilityId
    value: EngineFactText

    def to_core(self) -> EngineFact:
        """Convert one validated text fact to its pure core value."""
        return EngineFact(field_id=self.field_id, kind=EngineFactKind.TEXT, value=self.value)


class EngineIntegerFactValue(ContractModel):
    """One cross-language-exact namespaced engine integer fact."""

    kind: Literal["integer"]
    field_id: CapabilityId
    value: ExactBridgeInteger

    def to_core(self) -> EngineFact:
        """Convert one validated integer fact to its pure core value."""
        return EngineFact(field_id=self.field_id, kind=EngineFactKind.INTEGER, value=self.value)


class EngineNumberFactValue(ContractModel):
    """One finite namespaced engine number fact."""

    kind: Literal["number"]
    field_id: CapabilityId
    value: float = Field(allow_inf_nan=False)

    def to_core(self) -> EngineFact:
        """Convert one validated number fact to its pure core value."""
        return EngineFact(field_id=self.field_id, kind=EngineFactKind.NUMBER, value=self.value)


class EngineBooleanFactValue(ContractModel):
    """One namespaced engine boolean fact."""

    kind: Literal["boolean"]
    field_id: CapabilityId
    value: bool

    def to_core(self) -> EngineFact:
        """Convert one validated boolean fact to its pure core value."""
        return EngineFact(field_id=self.field_id, kind=EngineFactKind.BOOLEAN, value=self.value)


class EngineReferenceFactValue(ContractModel):
    """One namespaced engine relation to an opaque object reference."""

    kind: Literal["reference"]
    field_id: CapabilityId
    value: ObservationObjectReference

    def to_core(self) -> EngineFact:
        """Convert one validated reference fact to its pure core value."""
        return EngineFact(
            field_id=self.field_id,
            kind=EngineFactKind.REFERENCE,
            value=RunObjectReference(value=self.value),
        )


EngineFactValue: TypeAlias = Annotated[
    EngineTextFactValue
    | EngineIntegerFactValue
    | EngineNumberFactValue
    | EngineBooleanFactValue
    | EngineReferenceFactValue,
    Field(discriminator="kind"),
]


def _validate_fact_tuple(values: tuple[EngineFactValue, ...]) -> tuple[EngineFactValue, ...]:
    """Reject duplicate field IDs before a result reaches core conversion."""
    field_ids = tuple(value.field_id for value in values)
    if len(set(field_ids)) != len(field_ids):
        raise ValueError("engine extension fact IDs must be unique")
    return values


EngineFactValues: TypeAlias = Annotated[
    tuple[EngineFactValue, ...],
    BeforeValidator(freeze_sequence),
    Field(max_length=MAX_ENGINE_EXTENSION_FACTS),
    AfterValidator(_validate_fact_tuple),
]


def engine_facts_to_core(values: tuple[EngineFactValue, ...]) -> tuple[EngineFact, ...]:
    """Convert one validated immutable extension without untyped intermediates."""
    result = tuple(value.to_core() for value in values)
    validate_engine_facts(result)
    return result


def engine_facts_from_core(values: tuple[EngineFact, ...]) -> tuple[EngineFactValue, ...]:
    """Create exact discriminated boundary values from core scalar facts."""
    validate_engine_facts(values)
    return tuple(_engine_fact_from_core(value) for value in values)


def _engine_fact_from_core(value: EngineFact) -> EngineFactValue:
    """Map one core discriminator without reflection or arbitrary payloads."""
    if value.kind is EngineFactKind.TEXT:
        assert isinstance(value.value, str)
        return EngineTextFactValue(kind="text", field_id=value.field_id, value=value.value)
    if value.kind is EngineFactKind.INTEGER:
        assert isinstance(value.value, int) and not isinstance(value.value, bool)
        return EngineIntegerFactValue(
            kind="integer",
            field_id=value.field_id,
            value=value.value,
        )
    if value.kind is EngineFactKind.NUMBER:
        assert isinstance(value.value, float)
        return EngineNumberFactValue(kind="number", field_id=value.field_id, value=value.value)
    if value.kind is EngineFactKind.BOOLEAN:
        assert isinstance(value.value, bool)
        return EngineBooleanFactValue(
            kind="boolean",
            field_id=value.field_id,
            value=value.value,
        )
    assert isinstance(value.value, RunObjectReference)
    return EngineReferenceFactValue(
        kind="reference",
        field_id=value.field_id,
        value=value.value.value,
    )
