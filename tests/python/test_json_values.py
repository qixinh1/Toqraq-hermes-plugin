"""Owned immutable JSON values retained by safe error contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest
from pydantic import TypeAdapter, ValidationError
from toqraq.contracts.json_values import FrozenJson, FrozenJsonValue

FROZEN_JSON_ADAPTER: TypeAdapter[FrozenJson] = TypeAdapter(FrozenJsonValue)


def test_dynamic_json_is_copied_frozen_and_serialized_exactly() -> None:
    source = {"inventory": [{"name": "key", "count": 1}]}
    value = FROZEN_JSON_ADAPTER.validate_python(source)
    source["inventory"][0]["count"] = 99

    frozen_root = cast(Mapping[str, object], value.data)
    frozen_inventory = cast(tuple[object, ...], frozen_root["inventory"])
    frozen_item = cast(Mapping[str, object], frozen_inventory[0])
    with pytest.raises(TypeError):
        frozen_item["count"] = 2  # type: ignore[index]

    assert FROZEN_JSON_ADAPTER.dump_python(value, mode="json") == {
        "inventory": [{"name": "key", "count": 1}]
    }


@pytest.mark.parametrize("key", ["__proto__", "prototype", "constructor", "bad\x00key"])
def test_dynamic_json_rejects_desktop_unsafe_mapping_keys(key: str) -> None:
    with pytest.raises(ValidationError, match="engine value key"):
        FROZEN_JSON_ADAPTER.validate_python({key: True})
