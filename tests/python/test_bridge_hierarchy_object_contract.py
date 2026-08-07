"""Strict bridge hierarchy and selected-object DTO contract tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import cast

import pytest
from pydantic import ValidationError
from toqraq.contracts.bridge_hierarchy import (
    HIERARCHY_READ_METHOD,
    HierarchyReadRequest,
    HierarchyReadResponse,
)
from toqraq.contracts.bridge_objects import (
    OBJECT_READ_METHOD,
    ObjectReadRequest,
    ObjectReadResponse,
)
from toqraq.core.hierarchy import HierarchyEntry, HierarchyPage, HierarchyQuery
from toqraq.core.object_inspection import (
    ObjectExtensionGroup,
    ObjectFieldGroup,
    ObjectProperty,
    ObjectPropertyGroup,
    ObjectReadQuery,
    ObjectSnapshot,
    ObjectValue,
    ObjectValueKind,
    RuntimeObject,
)
from toqraq.core.observation import (
    MAX_ENGINE_EXTENSION_TEXT_BYTES,
    EngineFact,
    EngineFactKind,
    ObservationCursor,
    ObservationRevision,
    ObservationStamp,
    RunObjectReference,
)


def _ref(value: str) -> RunObjectReference:
    return RunObjectReference(value=value)


def _stamp(value: str) -> ObservationStamp:
    return ObservationStamp(
        revision=ObservationRevision(value=value),
        observed_at_unix_ms=1_700_000_000_000,
    )


def _hierarchy_query() -> HierarchyQuery:
    return HierarchyQuery(
        root=_ref("node:root"),
        depth=3,
        name_contains="Player",
        native_types=("CharacterBody2D",),
        revision=ObservationRevision(value="hierarchy:8"),
        cursor=ObservationCursor(value="hierarchy:page:2"),
        limit=64,
    )


def _hierarchy_page() -> HierarchyPage:
    return HierarchyPage(
        stamp=_stamp("hierarchy:8"),
        entries=(
            HierarchyEntry(
                reference=_ref("node:player"),
                display_name="Player",
                native_type="CharacterBody2D",
                parent=_ref("node:root"),
                child_count=2,
                component_type_count=3,
                component_types=("CollisionShape2D", "Sprite2D"),
                components_truncated=True,
                extensions=(
                    EngineFact(
                        field_id="godot.scene.owner",
                        kind=EngineFactKind.REFERENCE,
                        value=_ref("node:root"),
                    ),
                ),
            ),
        ),
        truncated=True,
        next_cursor=ObservationCursor(value="hierarchy:page:3"),
    )


def _object_query() -> ObjectReadQuery:
    return ObjectReadQuery(
        references=(_ref("node:player"),),
        fields=(ObjectFieldGroup.PROPERTIES, ObjectFieldGroup.EXTENSIONS),
        revision=ObservationRevision(value="objects:3"),
        per_value_max_bytes=1_024,
        total_value_max_bytes=8_192,
    )


def _object_snapshot() -> ObjectSnapshot:
    properties = ObjectPropertyGroup(
        total_count=2,
        items=(
            ObjectProperty(
                name="health",
                native_type="int",
                value=ObjectValue(kind=ObjectValueKind.INTEGER, value=100),
            ),
            ObjectProperty(
                name="inventory",
                native_type="Array[Item]",
                value=ObjectValue(
                    kind=ObjectValueKind.SUMMARY,
                    value="Array[4096] omitted by value budget",
                ),
            ),
        ),
        truncated=False,
    )
    extensions = ObjectExtensionGroup(
        total_count=1,
        items=(
            EngineFact(
                field_id="godot.process.enabled",
                kind=EngineFactKind.BOOLEAN,
                value=True,
            ),
        ),
        truncated=False,
    )
    return ObjectSnapshot(
        stamp=_stamp("objects:3"),
        fields=(ObjectFieldGroup.PROPERTIES, ObjectFieldGroup.EXTENSIONS),
        objects=(
            RuntimeObject(
                reference=_ref("node:player"),
                display_name="Player",
                native_type="CharacterBody2D",
                properties=properties,
                components=None,
                resources=None,
                extensions=extensions,
            ),
        ),
        value_bytes=184,
    )


def test_hierarchy_request_and_response_round_trip_without_session_selector() -> None:
    request = HierarchyReadRequest.from_core(request_id="host-1", query=_hierarchy_query())
    response = HierarchyReadResponse.from_core(
        request_id=request.id,
        value=_hierarchy_page(),
        query=_hierarchy_query(),
    )

    assert request.method == HIERARCHY_READ_METHOD
    assert request.params.to_core() == _hierarchy_query()
    assert (
        HierarchyReadRequest.model_validate(request.model_dump(mode="json")).params.to_core()
        == _hierarchy_query()
    )
    assert response.result.to_core(query=_hierarchy_query()) == _hierarchy_page()
    payload = response.model_dump(mode="json")
    assert "kind" not in payload["result"]
    assert "returned_count" not in payload["result"]
    assert payload["result"]["entries"][0]["extensions"] == [
        {
            "kind": "reference",
            "field_id": "godot.scene.owner",
            "value": "node:root",
        }
    ]
    assert "session_id" not in str(request.model_dump(mode="json"))
    assert (
        HierarchyReadResponse.model_validate(payload).result.to_core(query=_hierarchy_query())
        == _hierarchy_page()
    )
    with pytest.raises(ValueError, match="revision does not match"):
        response.result.to_core(
            query=replace(
                _hierarchy_query(),
                revision=ObservationRevision(value="hierarchy:other"),
            )
        )


def test_hierarchy_params_and_page_reject_alternate_or_inconsistent_shapes() -> None:
    request = HierarchyReadRequest.from_core(request_id="host-1", query=_hierarchy_query())
    payload = request.model_dump(mode="json")

    invalid = deepcopy(payload)
    invalid["params"]["revision"] = None
    with pytest.raises(ValidationError, match="requires its revision"):
        HierarchyReadRequest.model_validate(invalid)

    invalid = deepcopy(payload)
    invalid["params"]["native_types"] = ["Node", "Node"]
    with pytest.raises(ValidationError, match="must be unique"):
        HierarchyReadRequest.model_validate(invalid)

    invalid = deepcopy(payload)
    invalid["params"]["session_id"] = "another-run"
    with pytest.raises(ValidationError, match="Extra inputs"):
        HierarchyReadRequest.model_validate(invalid)

    response = HierarchyReadResponse.from_core(
        request_id=request.id,
        value=_hierarchy_page(),
        query=_hierarchy_query(),
    ).model_dump(mode="json")
    invalid = deepcopy(response)
    invalid["result"]["returned_count"] = 0
    with pytest.raises(ValidationError, match="Extra inputs"):
        HierarchyReadResponse.model_validate(invalid)

    invalid = deepcopy(response)
    invalid["result"]["entries"][0]["extensions"].append(
        {
            "kind": "text",
            "field_id": "godot.scene.owner",
            "value": "duplicate",
        }
    )
    with pytest.raises(ValidationError, match="must be unique"):
        HierarchyReadResponse.model_validate(invalid)

    invalid = deepcopy(response)
    invalid["result"]["entries"][0]["extensions"] = [
        {
            "kind": "text",
            "field_id": "godot.native_label",
            "value": "界" * (MAX_ENGINE_EXTENSION_TEXT_BYTES // 3 + 1),
        }
    ]
    with pytest.raises(ValidationError, match="UTF-8 byte bound"):
        HierarchyReadResponse.model_validate(invalid)


def test_object_request_and_response_round_trip_selected_typed_groups_only() -> None:
    request = ObjectReadRequest.from_core(request_id="host-2", query=_object_query())
    response = ObjectReadResponse.from_core(
        request_id=request.id,
        value=_object_snapshot(),
        query=_object_query(),
    )

    assert request.method == OBJECT_READ_METHOD
    assert request.params.to_core() == _object_query()
    assert (
        ObjectReadRequest.model_validate(request.model_dump(mode="json")).params.to_core()
        == _object_query()
    )
    assert response.result.to_core(query=_object_query()) == _object_snapshot()
    payload = response.model_dump(mode="json")
    assert "kind" not in payload["result"]
    assert "returned_count" not in payload["result"]
    groups = payload["result"]["objects"][0]["groups"]
    assert [group["kind"] for group in groups] == ["properties", "extensions"]
    assert groups[0]["items"][1]["value"] == {
        "kind": "summary",
        "value": "Array[4096] omitted by value budget",
    }
    serialized = response.model_dump_json()
    assert "png_base64" not in serialized
    assert "recursive" not in serialized
    assert (
        ObjectReadResponse.model_validate(payload).result.to_core(query=_object_query())
        == _object_snapshot()
    )
    with pytest.raises(ValueError, match="references do not match"):
        response.result.to_core(query=replace(_object_query(), references=(_ref("node:other"),)))
    with pytest.raises(ValueError, match="total byte limit"):
        response.result.to_core(
            query=replace(
                _object_query(),
                per_value_max_bytes=1,
                total_value_max_bytes=100,
            )
        )


def test_object_contract_rejects_wrong_groups_recursive_values_and_unknown_fields() -> None:
    response = ObjectReadResponse.from_core(
        request_id="host-2",
        value=_object_snapshot(),
        query=_object_query(),
    ).model_dump(mode="json")

    invalid = deepcopy(response)
    invalid["result"]["fields"] = ["components", "extensions"]
    with pytest.raises(ValidationError, match="do not match"):
        ObjectReadResponse.model_validate(invalid)

    invalid = deepcopy(response)
    invalid["result"]["objects"][0]["groups"][0]["items"][0]["value"] = {
        "kind": "text",
        "value": {"nested": [1, 2]},
    }
    with pytest.raises(ValidationError):
        ObjectReadResponse.model_validate(invalid)

    invalid = deepcopy(response)
    invalid["result"]["objects"][0]["groups"].append(
        deepcopy(invalid["result"]["objects"][0]["groups"][1])
    )
    with pytest.raises(ValidationError, match="must be unique"):
        ObjectReadResponse.model_validate(invalid)

    request = ObjectReadRequest.from_core(
        request_id="host-2",
        query=_object_query(),
    ).model_dump(mode="json")
    request["method"] = "toqraq.object.execute"
    with pytest.raises(ValidationError):
        ObjectReadRequest.model_validate(request)

    request = cast(dict[str, object], deepcopy(request))
    request["arbitrary"] = True
    with pytest.raises(ValidationError, match="Extra inputs"):
        ObjectReadRequest.model_validate(request)


def test_object_params_enforce_unique_selection_and_two_independent_byte_bounds() -> None:
    payload = ObjectReadRequest.from_core(
        request_id="host-2",
        query=_object_query(),
    ).model_dump(mode="json")

    invalid = deepcopy(payload)
    invalid["params"]["references"] = ["node:player", "node:player"]
    with pytest.raises(ValidationError, match="must be unique"):
        ObjectReadRequest.model_validate(invalid)

    invalid = deepcopy(payload)
    invalid["params"]["fields"] = ["properties", "properties"]
    with pytest.raises(ValidationError, match="must be unique"):
        ObjectReadRequest.model_validate(invalid)

    invalid = deepcopy(payload)
    invalid["params"]["per_value_max_bytes"] = 2_048
    invalid["params"]["total_value_max_bytes"] = 1_024
    with pytest.raises(ValidationError, match="total-value"):
        ObjectReadRequest.model_validate(invalid)
