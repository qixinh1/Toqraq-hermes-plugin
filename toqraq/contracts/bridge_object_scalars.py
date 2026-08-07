"""Strict scalar and relation values used by bridge object reads."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, Field, StringConstraints

from ..core.object_inspection import (
    MAX_OBJECT_NAME_BYTES,
    MAX_OBJECT_NATIVE_TYPE_BYTES,
    MAX_OBJECT_VALUE_SUMMARY_BYTES,
    MAX_OBJECT_VALUE_TEXT_BYTES,
    ObjectComponent,
    ObjectProperty,
    ObjectResource,
    ObjectValue,
    ObjectValueKind,
)
from ..core.observation import RunObjectReference, validate_observation_label
from ..core.observation import validate_observation_text as validate_core_text
from .base import ContractModel
from .bridge_observation import ExactBridgeInteger, ObservationObjectReference


def _validate_name(value: str) -> str:
    """Apply the exact UTF-8 byte bound for object-owned names."""
    return validate_observation_label(value, maximum_bytes=MAX_OBJECT_NAME_BYTES)


def _validate_native_type(value: str) -> str:
    """Apply the exact UTF-8 byte bound for engine-native types."""
    return validate_observation_label(value, maximum_bytes=MAX_OBJECT_NATIVE_TYPE_BYTES)


def _validate_text(value: str) -> str:
    """Apply the exact UTF-8 byte bound for a complete scalar string."""
    return validate_core_text(value, maximum_bytes=MAX_OBJECT_VALUE_TEXT_BYTES)


def _validate_summary(value: str) -> str:
    """Apply the exact non-empty UTF-8 byte bound for an explicit summary."""
    return validate_core_text(
        value,
        maximum_bytes=MAX_OBJECT_VALUE_SUMMARY_BYTES,
        allow_empty=False,
    )


ObjectName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_OBJECT_NAME_BYTES),
    AfterValidator(_validate_name),
]
ObjectNativeType = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_OBJECT_NATIVE_TYPE_BYTES),
    AfterValidator(_validate_native_type),
]
ObjectText = Annotated[
    str,
    StringConstraints(max_length=MAX_OBJECT_VALUE_TEXT_BYTES),
    AfterValidator(_validate_text),
]
ObjectSummary = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_OBJECT_VALUE_SUMMARY_BYTES),
    AfterValidator(_validate_summary),
]


class ObjectNullValue(ContractModel):
    """An explicitly selected property whose current value is null."""

    kind: Literal["null"]

    def to_core(self) -> ObjectValue:
        """Convert the exact null discriminator to core."""
        return ObjectValue(kind=ObjectValueKind.NULL, value=None)


class ObjectBooleanValue(ContractModel):
    """An explicitly typed boolean property value."""

    kind: Literal["boolean"]
    value: bool

    def to_core(self) -> ObjectValue:
        """Convert the exact boolean discriminator to core."""
        return ObjectValue(kind=ObjectValueKind.BOOLEAN, value=self.value)


class ObjectIntegerValue(ContractModel):
    """A cross-language-exact integer property value."""

    kind: Literal["integer"]
    value: ExactBridgeInteger

    def to_core(self) -> ObjectValue:
        """Convert the exact integer discriminator to core."""
        return ObjectValue(kind=ObjectValueKind.INTEGER, value=self.value)


class ObjectNumberValue(ContractModel):
    """A finite number property value."""

    kind: Literal["number"]
    value: float = Field(allow_inf_nan=False)

    def to_core(self) -> ObjectValue:
        """Convert the exact number discriminator to core."""
        return ObjectValue(kind=ObjectValueKind.NUMBER, value=self.value)


class ObjectTextValue(ContractModel):
    """A complete bounded UTF-8 property string."""

    kind: Literal["text"]
    value: ObjectText

    def to_core(self) -> ObjectValue:
        """Convert the exact text discriminator to core."""
        return ObjectValue(kind=ObjectValueKind.TEXT, value=self.value)


class ObjectReferenceValue(ContractModel):
    """A relation to another opaque object in the same run."""

    kind: Literal["reference"]
    value: ObservationObjectReference

    def to_core(self) -> ObjectValue:
        """Convert the exact reference discriminator to core."""
        return ObjectValue(
            kind=ObjectValueKind.REFERENCE,
            value=RunObjectReference(value=self.value),
        )


class ObjectSummaryValue(ContractModel):
    """An explicit bounded replacement for recursive or expensive data."""

    kind: Literal["summary"]
    value: ObjectSummary

    def to_core(self) -> ObjectValue:
        """Convert the explicit summary discriminator to core."""
        return ObjectValue(kind=ObjectValueKind.SUMMARY, value=self.value)


ObjectObservedValue: TypeAlias = Annotated[
    ObjectNullValue
    | ObjectBooleanValue
    | ObjectIntegerValue
    | ObjectNumberValue
    | ObjectTextValue
    | ObjectReferenceValue
    | ObjectSummaryValue,
    Field(discriminator="kind"),
]


class ObjectPropertyValue(ContractModel):
    """One bounded named property with a non-recursive value."""

    name: ObjectName
    native_type: ObjectNativeType
    value: ObjectObservedValue

    def to_core(self) -> ObjectProperty:
        """Convert one strict property value to core."""
        return ObjectProperty(
            name=self.name,
            native_type=self.native_type,
            value=self.value.to_core(),
        )

    @classmethod
    def from_core(cls, value: ObjectProperty) -> ObjectPropertyValue:
        """Create one exact property result from core."""
        return cls(
            name=value.name,
            native_type=value.native_type,
            value=object_value_from_core(value.value),
        )


class ObjectComponentValue(ContractModel):
    """One bounded component relation."""

    reference: ObservationObjectReference
    display_name: ObjectName
    native_type: ObjectNativeType

    def to_core(self) -> ObjectComponent:
        """Convert one strict component relation to core."""
        return ObjectComponent(
            reference=RunObjectReference(value=self.reference),
            display_name=self.display_name,
            native_type=self.native_type,
        )

    @classmethod
    def from_core(cls, value: ObjectComponent) -> ObjectComponentValue:
        """Create one exact component result from core."""
        return cls(
            reference=value.reference.value,
            display_name=value.display_name,
            native_type=value.native_type,
        )


class ObjectResourceValue(ContractModel):
    """One bounded named runtime resource relation."""

    reference: ObservationObjectReference
    name: ObjectName
    native_type: ObjectNativeType

    def to_core(self) -> ObjectResource:
        """Convert one strict resource relation to core."""
        return ObjectResource(
            reference=RunObjectReference(value=self.reference),
            name=self.name,
            native_type=self.native_type,
        )

    @classmethod
    def from_core(cls, value: ObjectResource) -> ObjectResourceValue:
        """Create one exact resource result from core."""
        return cls(
            reference=value.reference.value,
            name=value.name,
            native_type=value.native_type,
        )


def object_value_from_core(value: ObjectValue) -> ObjectObservedValue:
    """Map one validated core discriminator to its exact wire variant."""
    if value.kind is ObjectValueKind.NULL:
        return ObjectNullValue(kind="null")
    if value.kind is ObjectValueKind.BOOLEAN:
        assert isinstance(value.value, bool)
        return ObjectBooleanValue(kind="boolean", value=value.value)
    if value.kind is ObjectValueKind.INTEGER:
        assert isinstance(value.value, int) and not isinstance(value.value, bool)
        return ObjectIntegerValue(kind="integer", value=value.value)
    if value.kind is ObjectValueKind.NUMBER:
        assert isinstance(value.value, float)
        return ObjectNumberValue(kind="number", value=value.value)
    if value.kind is ObjectValueKind.TEXT:
        assert isinstance(value.value, str)
        return ObjectTextValue(kind="text", value=value.value)
    if value.kind is ObjectValueKind.REFERENCE:
        assert isinstance(value.value, RunObjectReference)
        return ObjectReferenceValue(kind="reference", value=value.value.value)
    assert isinstance(value.value, str)
    return ObjectSummaryValue(kind="summary", value=value.value)
