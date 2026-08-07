"""Strict selected-group values used by engine-bridge object reads."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, BeforeValidator, Field, model_validator

from ..core.object_inspection import (
    MAX_OBJECT_COMPONENTS,
    MAX_OBJECT_FIELD_GROUPS,
    MAX_OBJECT_PROPERTIES,
    MAX_OBJECT_RESOURCES,
    ObjectComponentGroup,
    ObjectExtensionGroup,
    ObjectPropertyGroup,
    ObjectResourceGroup,
    RuntimeObject,
)
from ..core.observation import RunObjectReference
from .base import ContractModel, freeze_sequence
from .bridge_object_scalars import (
    ObjectComponentValue,
    ObjectName,
    ObjectNativeType,
    ObjectPropertyValue,
    ObjectResourceValue,
)
from .bridge_observation import (
    EngineFactValues,
    ObservationObjectReference,
    engine_facts_from_core,
    engine_facts_to_core,
)
from .identifiers import MAX_JSON_INTEGER


class ObjectPropertyGroupValue(ContractModel):
    """One selected property group with explicit source count."""

    kind: Literal["properties"]
    total_count: int = Field(ge=0, le=MAX_JSON_INTEGER)
    items: Annotated[
        tuple[ObjectPropertyValue, ...],
        BeforeValidator(freeze_sequence),
        Field(max_length=MAX_OBJECT_PROPERTIES),
    ]
    truncated: bool

    @model_validator(mode="after")
    def validate_count(self) -> ObjectPropertyGroupValue:
        """Require truncation to agree with the exact source count."""
        _validate_count(self.total_count, len(self.items), self.truncated, "properties")
        return self

    def to_core(self) -> ObjectPropertyGroup:
        """Convert one selected property group to core."""
        return ObjectPropertyGroup(
            total_count=self.total_count,
            items=tuple(value.to_core() for value in self.items),
            truncated=self.truncated,
        )

    @classmethod
    def from_core(cls, value: ObjectPropertyGroup) -> ObjectPropertyGroupValue:
        """Create one exact selected property group from core."""
        return cls(
            kind="properties",
            total_count=value.total_count,
            items=tuple(ObjectPropertyValue.from_core(item) for item in value.items),
            truncated=value.truncated,
        )


class ObjectComponentGroupValue(ContractModel):
    """One selected component group with explicit source count."""

    kind: Literal["components"]
    total_count: int = Field(ge=0, le=MAX_JSON_INTEGER)
    items: Annotated[
        tuple[ObjectComponentValue, ...],
        BeforeValidator(freeze_sequence),
        Field(max_length=MAX_OBJECT_COMPONENTS),
    ]
    truncated: bool

    @model_validator(mode="after")
    def validate_count(self) -> ObjectComponentGroupValue:
        """Require truncation to agree with the exact source count."""
        _validate_count(self.total_count, len(self.items), self.truncated, "components")
        return self

    def to_core(self) -> ObjectComponentGroup:
        """Convert one selected component group to core."""
        return ObjectComponentGroup(
            total_count=self.total_count,
            items=tuple(value.to_core() for value in self.items),
            truncated=self.truncated,
        )

    @classmethod
    def from_core(cls, value: ObjectComponentGroup) -> ObjectComponentGroupValue:
        """Create one exact selected component group from core."""
        return cls(
            kind="components",
            total_count=value.total_count,
            items=tuple(ObjectComponentValue.from_core(item) for item in value.items),
            truncated=value.truncated,
        )


class ObjectResourceGroupValue(ContractModel):
    """One selected resource group with explicit source count."""

    kind: Literal["resources"]
    total_count: int = Field(ge=0, le=MAX_JSON_INTEGER)
    items: Annotated[
        tuple[ObjectResourceValue, ...],
        BeforeValidator(freeze_sequence),
        Field(max_length=MAX_OBJECT_RESOURCES),
    ]
    truncated: bool

    @model_validator(mode="after")
    def validate_count(self) -> ObjectResourceGroupValue:
        """Require truncation to agree with the exact source count."""
        _validate_count(self.total_count, len(self.items), self.truncated, "resources")
        return self

    def to_core(self) -> ObjectResourceGroup:
        """Convert one selected resource group to core."""
        return ObjectResourceGroup(
            total_count=self.total_count,
            items=tuple(value.to_core() for value in self.items),
            truncated=self.truncated,
        )

    @classmethod
    def from_core(cls, value: ObjectResourceGroup) -> ObjectResourceGroupValue:
        """Create one exact selected resource group from core."""
        return cls(
            kind="resources",
            total_count=value.total_count,
            items=tuple(ObjectResourceValue.from_core(item) for item in value.items),
            truncated=value.truncated,
        )


class ObjectExtensionGroupValue(ContractModel):
    """One selected flat engine-extension group with source count."""

    kind: Literal["extensions"]
    total_count: int = Field(ge=0, le=MAX_JSON_INTEGER)
    items: EngineFactValues
    truncated: bool

    @model_validator(mode="after")
    def validate_count(self) -> ObjectExtensionGroupValue:
        """Require truncation to agree with the exact source count."""
        _validate_count(self.total_count, len(self.items), self.truncated, "extensions")
        return self

    def to_core(self) -> ObjectExtensionGroup:
        """Convert one selected flat extension group to core."""
        return ObjectExtensionGroup(
            total_count=self.total_count,
            items=engine_facts_to_core(self.items),
            truncated=self.truncated,
        )

    @classmethod
    def from_core(cls, value: ObjectExtensionGroup) -> ObjectExtensionGroupValue:
        """Create one exact selected extension group from core."""
        return cls(
            kind="extensions",
            total_count=value.total_count,
            items=engine_facts_from_core(value.items),
            truncated=value.truncated,
        )


ObjectSelectedGroupValue: TypeAlias = Annotated[
    ObjectPropertyGroupValue
    | ObjectComponentGroupValue
    | ObjectResourceGroupValue
    | ObjectExtensionGroupValue,
    Field(discriminator="kind"),
]
ObjectSelectedGroupName: TypeAlias = Literal[
    "properties",
    "components",
    "resources",
    "extensions",
]


def _unique_groups(
    values: tuple[ObjectSelectedGroupValue, ...],
) -> tuple[ObjectSelectedGroupValue, ...]:
    """Reject duplicate selected group kinds before core conversion."""
    kinds = tuple(value.kind for value in values)
    if len(set(kinds)) != len(kinds):
        raise ValueError("object selected groups must be unique")
    return values


ObjectSelectedGroups: TypeAlias = Annotated[
    tuple[ObjectSelectedGroupValue, ...],
    BeforeValidator(freeze_sequence),
    Field(min_length=1, max_length=MAX_OBJECT_FIELD_GROUPS),
    AfterValidator(_unique_groups),
]


class RuntimeObjectValue(ContractModel):
    """One runtime object containing only its explicitly selected groups."""

    reference: ObservationObjectReference
    display_name: ObjectName
    native_type: ObjectNativeType
    groups: ObjectSelectedGroups

    def to_core(self) -> RuntimeObject:
        """Convert typed group variants to the focused core object value."""
        properties: ObjectPropertyGroup | None = None
        components: ObjectComponentGroup | None = None
        resources: ObjectResourceGroup | None = None
        extensions: ObjectExtensionGroup | None = None
        for group in self.groups:
            if isinstance(group, ObjectPropertyGroupValue):
                properties = group.to_core()
            elif isinstance(group, ObjectComponentGroupValue):
                components = group.to_core()
            elif isinstance(group, ObjectResourceGroupValue):
                resources = group.to_core()
            else:
                extensions = group.to_core()
        return RuntimeObject(
            reference=RunObjectReference(value=self.reference),
            display_name=self.display_name,
            native_type=self.native_type,
            properties=properties,
            components=components,
            resources=resources,
            extensions=extensions,
        )

    @classmethod
    def from_core(cls, value: RuntimeObject) -> RuntimeObjectValue:
        """Create exact selected group variants from one core object."""
        groups: list[ObjectSelectedGroupValue] = []
        if value.properties is not None:
            groups.append(ObjectPropertyGroupValue.from_core(value.properties))
        if value.components is not None:
            groups.append(ObjectComponentGroupValue.from_core(value.components))
        if value.resources is not None:
            groups.append(ObjectResourceGroupValue.from_core(value.resources))
        if value.extensions is not None:
            groups.append(ObjectExtensionGroupValue.from_core(value.extensions))
        return cls(
            reference=value.reference.value,
            display_name=value.display_name,
            native_type=value.native_type,
            groups=tuple(groups),
        )


def selected_group(value: ObjectSelectedGroupValue) -> ObjectSelectedGroupName:
    """Return the closed wire field represented by one group variant."""
    return value.kind


def _validate_count(total: int, returned: int, truncated: bool, label: str) -> None:
    """Require every selected collection to expose exact truncation."""
    if total < returned:
        raise ValueError(f"object {label} total count is too small")
    if truncated != (total > returned):
        raise ValueError(f"object {label} truncation is inconsistent")
