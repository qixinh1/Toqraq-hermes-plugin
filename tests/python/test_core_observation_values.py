"""Pure shared, hierarchy, and selected-object observation invariants."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest
from toqraq.core.hierarchy import (
    MAX_HIERARCHY_DEPTH,
    HierarchyEntry,
    HierarchyPage,
    HierarchyQuery,
    HierarchyReader,
    validate_hierarchy_page,
)
from toqraq.core.object_inspection import (
    MAX_OBJECT_TOTAL_VALUE_BYTES,
    ObjectExtensionGroup,
    ObjectFieldGroup,
    ObjectProperty,
    ObjectPropertyGroup,
    ObjectReader,
    ObjectReadQuery,
    ObjectSnapshot,
    ObjectValue,
    ObjectValueKind,
    ObjectValuePayload,
    RuntimeObject,
    validate_object_snapshot,
)
from toqraq.core.observation import (
    MAX_ENGINE_EXTENSION_TEXT_BYTES,
    EngineFact,
    EngineFactKind,
    EngineFactPayload,
    ObservationCursor,
    ObservationRevision,
    ObservationStamp,
    RunObjectReference,
    validate_engine_facts,
)


def _ref(value: str = "node:1") -> RunObjectReference:
    return RunObjectReference(value=value)


def _revision(value: str = "hierarchy:7") -> ObservationRevision:
    return ObservationRevision(value=value)


def _stamp() -> ObservationStamp:
    return ObservationStamp(revision=_revision(), observed_at_unix_ms=1_700_000_000_000)


def _fact(field_id: str = "godot.scene.owner") -> EngineFact:
    return EngineFact(
        field_id=field_id,
        kind=EngineFactKind.REFERENCE,
        value=_ref("node:owner"),
    )


def _entry() -> HierarchyEntry:
    return HierarchyEntry(
        reference=_ref(),
        display_name="Player",
        native_type="CharacterBody2D",
        parent=_ref("node:root"),
        child_count=2,
        component_type_count=2,
        component_types=("CollisionShape2D", "Sprite2D"),
        components_truncated=False,
        extensions=(_fact(),),
    )


def _property_group() -> ObjectPropertyGroup:
    return ObjectPropertyGroup(
        total_count=1,
        items=(
            ObjectProperty(
                name="health",
                native_type="int",
                value=ObjectValue(kind=ObjectValueKind.INTEGER, value=100),
            ),
        ),
        truncated=False,
    )


def _runtime_object(*, properties: ObjectPropertyGroup | None = None) -> RuntimeObject:
    return RuntimeObject(
        reference=_ref(),
        display_name="Player",
        native_type="CharacterBody2D",
        properties=properties,
        components=None,
        resources=None,
        extensions=None,
    )


@pytest.mark.parametrize(
    "value",
    ["", "-leading", "node/path", "node value", "x" * 129, "node+native"],
)
def test_run_scoped_tokens_reject_path_and_unbounded_encodings(value: str) -> None:
    with pytest.raises(ValueError, match="observation token"):
        RunObjectReference(value=value)


def test_run_scoped_reference_revision_and_cursor_are_distinct_opaque_values() -> None:
    assert _ref().value == "node:1"
    assert _revision().value == "hierarchy:7"
    assert ObservationCursor(value="page:2").value == "page:2"


def test_engine_extension_is_unique_namespaced_scalar_data_only() -> None:
    exact_text = "界" * (MAX_ENGINE_EXTENSION_TEXT_BYTES // 3)
    facts = (
        EngineFact(field_id="godot.name", kind=EngineFactKind.TEXT, value=exact_text),
        EngineFact(field_id="godot.layer", kind=EngineFactKind.INTEGER, value=4),
        EngineFact(field_id="godot.visible", kind=EngineFactKind.BOOLEAN, value=True),
        EngineFact(field_id="godot.weight", kind=EngineFactKind.NUMBER, value=0.5),
        _fact(),
    )
    validate_engine_facts(facts)

    with pytest.raises(ValueError, match="UTF-8 byte bound"):
        EngineFact(
            field_id="godot.name",
            kind=EngineFactKind.TEXT,
            value=exact_text + "界",
        )
    with pytest.raises(ValueError, match="integer fact"):
        EngineFact(field_id="godot.layer", kind=EngineFactKind.INTEGER, value=True)
    with pytest.raises(ValueError, match="number fact"):
        EngineFact(field_id="godot.weight", kind=EngineFactKind.NUMBER, value=float("nan"))
    with pytest.raises(ValueError, match="namespaced"):
        EngineFact(field_id="owner", kind=EngineFactKind.TEXT, value="root")
    with pytest.raises(ValueError, match="must be unique"):
        validate_engine_facts((facts[0], replace(facts[0], value="other")))
    with pytest.raises(ValueError, match="text fact"):
        EngineFact(
            field_id="godot.payload",
            kind=EngineFactKind.TEXT,
            value=cast(EngineFactPayload, {"recursive": True}),
        )


def test_hierarchy_query_ties_cursor_to_revision_and_bounds_selection() -> None:
    query = HierarchyQuery(
        root=_ref("node:root"),
        depth=2,
        name_contains="Player",
        native_types=("CharacterBody2D",),
        revision=_revision(),
        cursor=ObservationCursor(value="page:2"),
        limit=64,
    )
    assert query.limit == 64

    with pytest.raises(ValueError, match="requires its revision"):
        replace(query, revision=None)
    with pytest.raises(ValueError, match="depth"):
        replace(query, depth=MAX_HIERARCHY_DEPTH + 1)
    with pytest.raises(ValueError, match="must be unique"):
        replace(query, native_types=("Node", "Node"))


def test_hierarchy_entry_and_page_never_hide_truncation_or_duplicate_refs() -> None:
    entry = _entry()
    page = HierarchyPage(
        stamp=_stamp(),
        entries=(entry,),
        truncated=True,
        next_cursor=ObservationCursor(value="page:2"),
    )
    assert page.entries == (entry,)

    with pytest.raises(ValueError, match="component truncation"):
        replace(entry, component_type_count=3, components_truncated=False)
    with pytest.raises(ValueError, match="truncation"):
        replace(page, truncated=False)
    with pytest.raises(ValueError, match="must be unique"):
        replace(page, entries=(entry, entry))

    query = HierarchyQuery(
        root=None,
        depth=1,
        name_contains=None,
        native_types=(),
        revision=_revision(),
        cursor=None,
        limit=1,
    )
    validate_hierarchy_page(page, query)
    with pytest.raises(ValueError, match="requested limit"):
        validate_hierarchy_page(
            replace(page, entries=(entry, replace(entry, reference=_ref("node:2")))), query
        )
    with pytest.raises(ValueError, match="revision does not match"):
        validate_hierarchy_page(page, replace(query, revision=_revision("hierarchy:8")))


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        (ObjectValueKind.NULL, None),
        (ObjectValueKind.BOOLEAN, True),
        (ObjectValueKind.INTEGER, 7),
        (ObjectValueKind.NUMBER, 7.5),
        (ObjectValueKind.TEXT, "ready"),
        (ObjectValueKind.REFERENCE, _ref("node:target")),
        (ObjectValueKind.SUMMARY, "Array[4096] summarized"),
    ],
)
def test_object_value_accepts_only_closed_non_recursive_shapes(
    kind: ObjectValueKind,
    value: ObjectValuePayload,
) -> None:
    assert ObjectValue(kind=kind, value=value).kind is kind


def test_object_value_rejects_discriminator_mismatch_and_recursive_containers() -> None:
    with pytest.raises(ValueError, match="integer object"):
        ObjectValue(kind=ObjectValueKind.INTEGER, value=True)
    with pytest.raises(ValueError, match="number object"):
        ObjectValue(kind=ObjectValueKind.NUMBER, value=float("inf"))
    with pytest.raises(ValueError, match="text object"):
        ObjectValue(
            kind=ObjectValueKind.TEXT,
            value=cast(ObjectValuePayload, {"position": [1, 2]}),
        )


def test_object_query_requires_unique_refs_fields_and_coherent_byte_budgets() -> None:
    query = ObjectReadQuery(
        references=(_ref(),),
        fields=(ObjectFieldGroup.PROPERTIES,),
        revision=_revision(),
        per_value_max_bytes=1_024,
        total_value_max_bytes=4_096,
    )
    assert query.fields == (ObjectFieldGroup.PROPERTIES,)

    with pytest.raises(ValueError, match="references must be unique"):
        replace(query, references=(_ref(), _ref()))
    with pytest.raises(ValueError, match="field selection"):
        replace(query, fields=(ObjectFieldGroup.PROPERTIES, ObjectFieldGroup.PROPERTIES))
    with pytest.raises(ValueError, match="total-value"):
        replace(query, total_value_max_bytes=512)


def test_object_groups_and_snapshot_match_exact_selection_and_budgets() -> None:
    properties = _property_group()
    value = _runtime_object(properties=properties)
    snapshot = ObjectSnapshot(
        stamp=_stamp(),
        fields=(ObjectFieldGroup.PROPERTIES,),
        objects=(value,),
        value_bytes=32,
    )
    assert snapshot.value_bytes == 32

    with pytest.raises(ValueError, match="truncation"):
        replace(properties, total_count=2, truncated=False)
    with pytest.raises(ValueError, match="do not match"):
        replace(snapshot, fields=(ObjectFieldGroup.COMPONENTS,))
    with pytest.raises(ValueError, match="protocol maximum"):
        replace(snapshot, value_bytes=MAX_OBJECT_TOTAL_VALUE_BYTES + 1)

    query = ObjectReadQuery(
        references=(_ref(),),
        fields=(ObjectFieldGroup.PROPERTIES,),
        revision=_revision(),
        per_value_max_bytes=1_024,
        total_value_max_bytes=4_096,
    )
    validate_object_snapshot(snapshot, query)
    with pytest.raises(ValueError, match="references do not match"):
        validate_object_snapshot(snapshot, replace(query, references=(_ref("node:2"),)))
    with pytest.raises(ValueError, match="total byte limit"):
        validate_object_snapshot(
            snapshot,
            replace(query, per_value_max_bytes=8, total_value_max_bytes=16),
        )

    extensions = ObjectExtensionGroup(
        total_count=1,
        items=(_fact(),),
        truncated=False,
    )
    assert extensions.items[0].field_id == "godot.scene.owner"


class _HierarchyReader:
    async def read(self, query: HierarchyQuery) -> HierarchyPage:
        return HierarchyPage(
            stamp=_stamp(),
            entries=(_entry(),),
            truncated=False,
            next_cursor=None,
        )


class _ObjectReader:
    async def read(self, query: ObjectReadQuery) -> ObjectSnapshot:
        value = _runtime_object(properties=_property_group())
        return ObjectSnapshot(
            stamp=_stamp(),
            fields=query.fields,
            objects=(value,),
            value_bytes=32,
        )


def test_hierarchy_and_object_ports_are_independently_structural() -> None:
    assert isinstance(_HierarchyReader(), HierarchyReader)
    assert isinstance(_ObjectReader(), ObjectReader)
