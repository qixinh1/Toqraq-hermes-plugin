"""Owned immutable representation for dynamic engine JSON values."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, TypeAlias

from pydantic import (
    InstanceOf,
    JsonValue,
    PlainSerializer,
    ValidateAs,
    WithJsonSchema,
)

_MAX_KEY_LENGTH = 512
_UNSAFE_OBJECT_KEYS = frozenset({"__proto__", "prototype", "constructor"})

JsonScalar: TypeAlias = str | int | float | bool | None
FrozenJsonData: TypeAlias = (
    JsonScalar | tuple["FrozenJsonData", ...] | Mapping[str, "FrozenJsonData"]
)


class FrozenJson:
    """A recursively copied JSON value with no mutable containers."""

    __slots__ = ("_data",)
    _data: FrozenJsonData

    def __init__(self, data: FrozenJsonData) -> None:
        """Store already-owned immutable data."""
        object.__setattr__(self, "_data", data)

    @property
    def data(self) -> FrozenJsonData:
        """Expose only immutable containers to contract consumers."""
        return self._data

    def __setattr__(self, _name: str, _value: object) -> None:
        """Prevent replacement of the owned immutable root."""
        raise AttributeError("FrozenJson is immutable")

    def __eq__(self, other: object) -> bool:
        """Compare semantic JSON content rather than wrapper identity."""
        return isinstance(other, FrozenJson) and self._data == other._data

    def __repr__(self) -> str:
        """Show the immutable representation in diagnostics."""
        return f"FrozenJson({self._data!r})"

    @classmethod
    def from_json(cls, value: JsonValue) -> FrozenJson:
        """Copy and freeze one already validated JSON value."""
        return cls(_freeze(value))

    def to_json(self) -> JsonValue:
        """Return a fresh JSON value for public serialization."""
        return _thaw(self.data)


def _freeze_validated(value: FrozenJson | JsonValue) -> FrozenJson:
    """Preserve owned values or freeze a newly validated boundary value."""
    if isinstance(value, FrozenJson):
        return value
    return FrozenJson.from_json(value)


def _serialize(value: FrozenJson) -> JsonValue:
    """Serialize without exposing the internal read-only containers."""
    return value.to_json()


FrozenJsonValue: TypeAlias = Annotated[
    FrozenJson,
    ValidateAs(InstanceOf[FrozenJson] | JsonValue, _freeze_validated),
    PlainSerializer(_serialize, return_type=JsonValue),
    WithJsonSchema({}),
]


def _freeze(value: JsonValue) -> FrozenJsonData:
    """Recursively copy lists and mappings into immutable containers."""
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        frozen: dict[str, FrozenJsonData] = {}
        for key, item in value.items():
            _validate_key(key)
            frozen[key] = _freeze(item)
        return MappingProxyType(frozen)
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError("validated JSON contains an unsupported value")


def _thaw(value: FrozenJsonData) -> JsonValue:
    """Recursively build fresh dicts and lists for a JSON serializer."""
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _validate_key(key: str) -> None:
    """Reject unbounded, control-bearing, and prototype-sensitive keys."""
    if not key or len(key) > _MAX_KEY_LENGTH:
        raise ValueError("engine value key length is invalid")
    if key in _UNSAFE_OBJECT_KEYS:
        raise ValueError("engine value key is unsafe")
    if any(unicodedata.category(character).startswith("C") for character in key):
        raise ValueError("engine value key contains a control character")
