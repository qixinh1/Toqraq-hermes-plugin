"""Bounded immutable JSON values safe to retain on application failures."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import TypeAlias

MAX_ERROR_FIELDS = 32
MAX_ERROR_KEY_LENGTH = 64
MAX_ERROR_STRING_LENGTH = 512
MAX_ERROR_SEQUENCE_ITEMS = 32
MAX_ERROR_DEPTH = 4
MAX_ERROR_VALUE_NODES = 128
MAX_ERROR_SAFE_INTEGER = (1 << 53) - 1

ErrorScalar: TypeAlias = str | int | float | bool | None
ErrorValue: TypeAlias = ErrorScalar | tuple["ErrorValue", ...] | Mapping[str, "ErrorValue"]
ErrorFields: TypeAlias = Mapping[str, ErrorValue]


def freeze_error_fields(fields: ErrorFields | None) -> ErrorFields:
    """Validate and recursively freeze safe public error fields.

    Args:
        fields: Candidate localization parameters or structured details.

    Returns:
        An immutable mapping containing only bounded JSON values.
    """
    source = fields or {}
    if len(source) > MAX_ERROR_FIELDS:
        raise ValueError("error field mapping is too large")
    budget = [MAX_ERROR_VALUE_NODES]
    frozen = _freeze_mapping(source, depth=0, budget=budget)
    return MappingProxyType(frozen)


def _freeze_mapping(
    value: Mapping[str, ErrorValue],
    *,
    depth: int,
    budget: list[int],
) -> dict[str, ErrorValue]:
    """Validate one mapping inside the shared node budget."""
    if depth > MAX_ERROR_DEPTH:
        raise ValueError("error value nesting is too deep")
    if len(value) > MAX_ERROR_FIELDS:
        raise ValueError("error field mapping is too large")
    result: dict[str, ErrorValue] = {}
    for key, item in value.items():
        _consume_node(budget)
        if not isinstance(key, str) or not key or len(key) > MAX_ERROR_KEY_LENGTH:
            raise ValueError("error field key is invalid")
        result[key] = _freeze_value(item, depth=depth + 1, budget=budget)
    return result


def _freeze_value(value: ErrorValue, *, depth: int, budget: list[int]) -> ErrorValue:
    """Validate and freeze one recursive JSON value."""
    if depth > MAX_ERROR_DEPTH:
        raise ValueError("error value nesting is too deep")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        if abs(value) > MAX_ERROR_SAFE_INTEGER:
            raise ValueError("error integer is outside the cross-language safe range")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("error number must be finite")
        if value.is_integer() and abs(value) > MAX_ERROR_SAFE_INTEGER:
            raise ValueError("error integer is outside the cross-language safe range")
        return value
    if isinstance(value, str):
        if len(value) > MAX_ERROR_STRING_LENGTH:
            raise ValueError("error string is too long")
        return value
    if isinstance(value, Mapping):
        return MappingProxyType(_freeze_mapping(value, depth=depth, budget=budget))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if len(value) > MAX_ERROR_SEQUENCE_ITEMS:
            raise ValueError("error sequence is too large")
        result: list[ErrorValue] = []
        for item in value:
            _consume_node(budget)
            result.append(_freeze_value(item, depth=depth + 1, budget=budget))
        return tuple(result)
    raise TypeError("error values must be bounded JSON data")


def _consume_node(budget: list[int]) -> None:
    """Consume one node from the total public-value budget."""
    budget[0] -= 1
    if budget[0] < 0:
        raise ValueError("error value contains too many nodes")
