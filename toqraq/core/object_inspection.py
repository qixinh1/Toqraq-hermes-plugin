"""Pure selected-object values and the focused read-only inspection port."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, TypeAlias, runtime_checkable

from .observation import (
    MAX_ENGINE_EXTENSION_FACTS,
    EngineFact,
    ObservationRevision,
    ObservationStamp,
    RunObjectReference,
    require_exact_integer,
    validate_engine_facts,
    validate_observation_count,
    validate_observation_label,
    validate_observation_text,
)

MAX_OBJECT_REFERENCES = 64
MAX_OBJECT_FIELD_GROUPS = 4
MAX_OBJECT_PROPERTIES = 128
MAX_OBJECT_COMPONENTS = 64
MAX_OBJECT_RESOURCES = 64
MAX_OBJECT_VALUE_TEXT_BYTES = 16_384
MAX_OBJECT_VALUE_SUMMARY_BYTES = 1_024
MAX_OBJECT_TOTAL_VALUE_BYTES = 262_144
MAX_OBJECT_NAME_BYTES = 256
MAX_OBJECT_NATIVE_TYPE_BYTES = 256


class ObjectFieldGroup(StrEnum):
    """Closed independently selectable common object field groups."""

    PROPERTIES = "properties"
    COMPONENTS = "components"
    RESOURCES = "resources"
    EXTENSIONS = "extensions"


class ObjectValueKind(StrEnum):
    """Closed non-recursive shapes allowed for one inspected property."""

    NULL = "null"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    TEXT = "text"
    REFERENCE = "reference"
    SUMMARY = "summary"


ObjectValuePayload: TypeAlias = None | bool | int | float | str | RunObjectReference


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectValue:
    """One typed scalar, opaque relation, or explicit bounded summary."""

    kind: ObjectValueKind
    value: ObjectValuePayload

    def __post_init__(self) -> None:
        """Reject recursive containers, discriminator ambiguity, and overflow."""
        if not isinstance(self.kind, ObjectValueKind):
            raise ValueError("object value kind is invalid")
        if self.kind is ObjectValueKind.NULL:
            if self.value is not None:
                raise ValueError("null object value is invalid")
            return
        if self.kind is ObjectValueKind.BOOLEAN:
            if type(self.value) is not bool:
                raise ValueError("boolean object value is invalid")
            return
        if self.kind is ObjectValueKind.INTEGER:
            if not isinstance(self.value, int) or isinstance(self.value, bool):
                raise ValueError("integer object value is invalid")
            require_exact_integer(self.value, label="integer object value")
            return
        if self.kind is ObjectValueKind.NUMBER:
            if type(self.value) is not float or not math.isfinite(self.value):
                raise ValueError("number object value is invalid")
            return
        if self.kind is ObjectValueKind.TEXT:
            if not isinstance(self.value, str):
                raise ValueError("text object value is invalid")
            validate_observation_text(
                self.value,
                maximum_bytes=MAX_OBJECT_VALUE_TEXT_BYTES,
            )
            return
        if self.kind is ObjectValueKind.REFERENCE:
            if not isinstance(self.value, RunObjectReference):
                raise ValueError("reference object value is invalid")
            return
        if not isinstance(self.value, str):
            raise ValueError("summary object value is invalid")
        validate_observation_text(
            self.value,
            maximum_bytes=MAX_OBJECT_VALUE_SUMMARY_BYTES,
            allow_empty=False,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectProperty:
    """One named engine-native property and its safe observed value."""

    name: str
    native_type: str
    value: ObjectValue

    def __post_init__(self) -> None:
        """Require bounded native identity and a non-recursive value."""
        validate_observation_label(self.name, maximum_bytes=MAX_OBJECT_NAME_BYTES)
        validate_observation_label(
            self.native_type,
            maximum_bytes=MAX_OBJECT_NATIVE_TYPE_BYTES,
        )
        if not isinstance(self.value, ObjectValue):
            raise ValueError("object property value is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectComponent:
    """One engine-native component relation represented by an opaque ref."""

    reference: RunObjectReference
    display_name: str
    native_type: str

    def __post_init__(self) -> None:
        """Reject exposed native identities and unbounded component labels."""
        if not isinstance(self.reference, RunObjectReference):
            raise ValueError("object component reference is invalid")
        validate_observation_label(
            self.display_name,
            maximum_bytes=MAX_OBJECT_NAME_BYTES,
        )
        validate_observation_label(
            self.native_type,
            maximum_bytes=MAX_OBJECT_NATIVE_TYPE_BYTES,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectResource:
    """One named live resource relation represented by an opaque ref."""

    reference: RunObjectReference
    name: str
    native_type: str

    def __post_init__(self) -> None:
        """Keep resource identity run-scoped and its labels bounded."""
        if not isinstance(self.reference, RunObjectReference):
            raise ValueError("object resource reference is invalid")
        validate_observation_label(self.name, maximum_bytes=MAX_OBJECT_NAME_BYTES)
        validate_observation_label(
            self.native_type,
            maximum_bytes=MAX_OBJECT_NATIVE_TYPE_BYTES,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectPropertyGroup:
    """Selected bounded properties with explicit source count."""

    total_count: int
    items: tuple[ObjectProperty, ...]
    truncated: bool

    def __post_init__(self) -> None:
        """Require exact visible truncation rather than silent dropping."""
        _validate_group(
            total_count=self.total_count,
            items=self.items,
            truncated=self.truncated,
            maximum=MAX_OBJECT_PROPERTIES,
            expected_type=ObjectProperty,
            label="object properties",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectComponentGroup:
    """Selected bounded component relations with explicit source count."""

    total_count: int
    items: tuple[ObjectComponent, ...]
    truncated: bool

    def __post_init__(self) -> None:
        """Require exact visible truncation rather than silent dropping."""
        _validate_group(
            total_count=self.total_count,
            items=self.items,
            truncated=self.truncated,
            maximum=MAX_OBJECT_COMPONENTS,
            expected_type=ObjectComponent,
            label="object components",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectResourceGroup:
    """Selected bounded resource relations with explicit source count."""

    total_count: int
    items: tuple[ObjectResource, ...]
    truncated: bool

    def __post_init__(self) -> None:
        """Require exact visible truncation rather than silent dropping."""
        _validate_group(
            total_count=self.total_count,
            items=self.items,
            truncated=self.truncated,
            maximum=MAX_OBJECT_RESOURCES,
            expected_type=ObjectResource,
            label="object resources",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectExtensionGroup:
    """Selected bounded engine facts with explicit source count."""

    total_count: int
    items: tuple[EngineFact, ...]
    truncated: bool

    def __post_init__(self) -> None:
        """Require flat unique facts and exact visible truncation."""
        validate_engine_facts(self.items)
        _validate_group(
            total_count=self.total_count,
            items=self.items,
            truncated=self.truncated,
            maximum=MAX_ENGINE_EXTENSION_FACTS,
            expected_type=EngineFact,
            label="object extensions",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeObject:
    """One inspected runtime object containing only selected field groups."""

    reference: RunObjectReference
    display_name: str
    native_type: str
    properties: ObjectPropertyGroup | None
    components: ObjectComponentGroup | None
    resources: ObjectResourceGroup | None
    extensions: ObjectExtensionGroup | None

    def __post_init__(self) -> None:
        """Validate common identity and each independently selected group."""
        if not isinstance(self.reference, RunObjectReference):
            raise ValueError("runtime object reference is invalid")
        validate_observation_label(
            self.display_name,
            maximum_bytes=MAX_OBJECT_NAME_BYTES,
        )
        validate_observation_label(
            self.native_type,
            maximum_bytes=MAX_OBJECT_NATIVE_TYPE_BYTES,
        )
        groups: tuple[tuple[object | None, type[object]], ...] = (
            (self.properties, ObjectPropertyGroup),
            (self.components, ObjectComponentGroup),
            (self.resources, ObjectResourceGroup),
            (self.extensions, ObjectExtensionGroup),
        )
        if any(group is not None and not isinstance(group, expected) for group, expected in groups):
            raise ValueError("runtime object field group is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectReadQuery:
    """Explicit object references, field groups, revision, and byte budgets."""

    references: tuple[RunObjectReference, ...]
    fields: tuple[ObjectFieldGroup, ...]
    revision: ObservationRevision | None
    per_value_max_bytes: int
    total_value_max_bytes: int

    def __post_init__(self) -> None:
        """Reject duplicate refs, implicit selection, and inconsistent limits."""
        if (
            not isinstance(self.references, tuple)
            or not 1 <= len(self.references) <= MAX_OBJECT_REFERENCES
            or any(not isinstance(reference, RunObjectReference) for reference in self.references)
        ):
            raise ValueError("object read references are invalid")
        if len(set(self.references)) != len(self.references):
            raise ValueError("object read references must be unique")
        _validate_field_groups(self.fields)
        if self.revision is not None and not isinstance(self.revision, ObservationRevision):
            raise ValueError("object read revision is invalid")
        if (
            isinstance(self.per_value_max_bytes, bool)
            or not isinstance(self.per_value_max_bytes, int)
            or not 1 <= self.per_value_max_bytes <= MAX_OBJECT_VALUE_TEXT_BYTES
        ):
            raise ValueError("object per-value byte limit is invalid")
        if (
            isinstance(self.total_value_max_bytes, bool)
            or not isinstance(self.total_value_max_bytes, int)
            or not 1 <= self.total_value_max_bytes <= MAX_OBJECT_TOTAL_VALUE_BYTES
            or self.total_value_max_bytes < self.per_value_max_bytes
        ):
            raise ValueError("object total-value byte limit is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectSnapshot:
    """One revision-consistent result containing exactly selected groups."""

    stamp: ObservationStamp
    fields: tuple[ObjectFieldGroup, ...]
    objects: tuple[RuntimeObject, ...]
    value_bytes: int

    def __post_init__(self) -> None:
        """Echo selection and require exact counts and group presence."""
        if not isinstance(self.stamp, ObservationStamp):
            raise ValueError("object observation stamp is invalid")
        _validate_field_groups(self.fields)
        if (
            not isinstance(self.objects, tuple)
            or not 1 <= len(self.objects) <= MAX_OBJECT_REFERENCES
            or any(not isinstance(value, RuntimeObject) for value in self.objects)
        ):
            raise ValueError("object snapshot values are invalid")
        references = tuple(value.reference for value in self.objects)
        if len(set(references)) != len(references):
            raise ValueError("object snapshot references must be unique")
        selected = set(self.fields)
        for value in self.objects:
            present = {
                ObjectFieldGroup.PROPERTIES: value.properties is not None,
                ObjectFieldGroup.COMPONENTS: value.components is not None,
                ObjectFieldGroup.RESOURCES: value.resources is not None,
                ObjectFieldGroup.EXTENSIONS: value.extensions is not None,
            }
            if {field for field, is_present in present.items() if is_present} != selected:
                raise ValueError("object snapshot groups do not match its selection")
        validate_observation_count(self.value_bytes, label="object value bytes")
        if self.value_bytes > MAX_OBJECT_TOTAL_VALUE_BYTES:
            raise ValueError("object value byte count exceeds the protocol maximum")


def validate_object_snapshot(snapshot: ObjectSnapshot, query: ObjectReadQuery) -> None:
    """Correlate one object snapshot with its exact selection and budgets."""
    if not isinstance(snapshot, ObjectSnapshot):
        raise TypeError("object snapshot is invalid")
    if not isinstance(query, ObjectReadQuery):
        raise TypeError("object read query is invalid")
    if query.revision is not None and snapshot.stamp.revision != query.revision:
        raise ValueError("object snapshot revision does not match its query")
    if snapshot.fields != query.fields:
        raise ValueError("object snapshot fields do not match its query")
    if tuple(value.reference for value in snapshot.objects) != query.references:
        raise ValueError("object snapshot references do not match its query")
    if snapshot.value_bytes > query.total_value_max_bytes:
        raise ValueError("object snapshot exceeds its requested total byte limit")
    for value in snapshot.objects:
        for text in _object_value_texts(value):
            if len(text.encode("utf-8")) > query.per_value_max_bytes:
                raise ValueError("object snapshot value exceeds its requested byte limit")


@runtime_checkable
class ObjectReader(Protocol):
    """Read-only engine boundary for selected live object fields."""

    async def read(self, query: ObjectReadQuery) -> ObjectSnapshot:
        """Inspect explicit refs without invoking or mutating engine objects."""
        ...


def _validate_field_groups(fields: tuple[ObjectFieldGroup, ...]) -> None:
    """Require an explicit immutable unique field selection."""
    if (
        not isinstance(fields, tuple)
        or not 1 <= len(fields) <= MAX_OBJECT_FIELD_GROUPS
        or any(not isinstance(field, ObjectFieldGroup) for field in fields)
        or len(set(fields)) != len(fields)
    ):
        raise ValueError("object field selection is invalid")


def _validate_group(
    *,
    total_count: int,
    items: tuple[object, ...],
    truncated: bool,
    maximum: int,
    expected_type: type[object],
    label: str,
) -> None:
    """Validate one selected group without introducing a generic domain model."""
    validate_observation_count(total_count, label=f"{label} total count")
    if (
        not isinstance(items, tuple)
        or len(items) > maximum
        or any(not isinstance(item, expected_type) for item in items)
        or total_count < len(items)
    ):
        raise ValueError(f"{label} are invalid")
    if type(truncated) is not bool or truncated != (total_count > len(items)):
        raise ValueError(f"{label} truncation is inconsistent")


def _object_value_texts(value: RuntimeObject) -> tuple[str, ...]:
    """Return only selected scalar payload text governed by query budgets."""
    texts: list[str] = []
    if value.properties is not None:
        texts.extend(
            item.value.value for item in value.properties.items if isinstance(item.value.value, str)
        )
    if value.extensions is not None:
        texts.extend(item.value for item in value.extensions.items if isinstance(item.value, str))
    return tuple(texts)
