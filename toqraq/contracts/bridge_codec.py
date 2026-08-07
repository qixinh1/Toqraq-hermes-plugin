"""Strict bounded JSON decoding for the first engine-bridge message."""

from __future__ import annotations

import contextlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import NoReturn

from pydantic import ValidationError

from ..core.bridge import (
    MAX_BRIDGE_JSON_COLLECTION_ITEMS,
    MAX_BRIDGE_JSON_DEPTH,
    MAX_BRIDGE_JSON_NODES,
    MAX_BRIDGE_TEXT_MESSAGE_BYTES,
)
from ..core.bridge_errors import (
    BridgeJsonInvalidError,
    BridgeMessageTooLargeError,
    BridgeMethodNotFoundError,
    BridgeParamsInvalidError,
    BridgeRequestInvalidError,
)
from .bridge import (
    BRIDGE_HANDSHAKE_METHOD,
    BridgeHandshakeRequest,
    JsonRpcRequestEnvelope,
)

_MAX_ERROR_LOCATION_CHARACTERS = 128


class _DuplicateObjectKeyError(ValueError):
    """Internal marker that prevents ambiguous JSON object decoding."""


def decode_bridge_json(message: str, *, maximum_bytes: int) -> object:
    """Decode one bounded duplicate-free finite JSON value.

    The returned ``object`` is the external decode boundary. Callers must
    convert it immediately to one exact contract model.
    """
    if (
        isinstance(maximum_bytes, bool)
        or not isinstance(maximum_bytes, int)
        or not 1 <= maximum_bytes <= MAX_BRIDGE_TEXT_MESSAGE_BYTES
    ):
        raise ValueError("bridge JSON byte limit is invalid")
    if type(message) is not str:
        raise BridgeJsonInvalidError()
    message_bytes = _utf8_size(message)
    if message_bytes > maximum_bytes:
        raise BridgeMessageTooLargeError(
            actual_bytes=message_bytes,
            maximum_bytes=maximum_bytes,
        )

    decoded = _decode_json(message)
    _validate_json_bounds(decoded)
    return decoded


def decode_handshake_request(
    message: str,
    *,
    maximum_bytes: int = MAX_BRIDGE_TEXT_MESSAGE_BYTES,
) -> BridgeHandshakeRequest:
    """Decode one bounded first text frame or raise a stable bridge failure."""
    decoded = decode_bridge_json(
        message,
        maximum_bytes=maximum_bytes,
    )
    if not isinstance(decoded, dict):
        raise BridgeRequestInvalidError()

    envelope: JsonRpcRequestEnvelope | None = None
    with contextlib.suppress(ValidationError):
        envelope = JsonRpcRequestEnvelope.model_validate(decoded)
    if envelope is None:
        raise BridgeRequestInvalidError()
    if envelope.method != BRIDGE_HANDSHAKE_METHOD:
        raise BridgeMethodNotFoundError(request_id=envelope.id)

    location = "params"
    try:
        return BridgeHandshakeRequest.model_validate(decoded)
    except ValidationError as exc:
        location = _validation_location(exc)
    raise BridgeParamsInvalidError(location=location, request_id=envelope.id)


def _utf8_size(message: str) -> int:
    """Return encoded size without retaining an invalid source string in an error."""
    try:
        return len(message.encode("utf-8"))
    except UnicodeEncodeError:
        pass
    raise BridgeJsonInvalidError()


def _decode_json(message: str) -> object:
    """Parse one finite duplicate-free JSON value without retaining input on failure."""
    try:
        return json.loads(
            message,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_non_finite,
        )
    except (json.JSONDecodeError, _DuplicateObjectKeyError, RecursionError, ValueError):
        pass
    raise BridgeJsonInvalidError()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build one object while rejecting duplicate member names."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateObjectKeyError
        result[key] = value
    return result


def _reject_non_finite(_value: str) -> NoReturn:
    """Reject Python JSON decoder extensions for NaN and infinities."""
    raise ValueError("non-finite JSON number")


def _validate_json_bounds(value: object) -> None:
    """Apply aggregate shape bounds before method-specific Pydantic validation."""
    pending: list[tuple[object, int]] = [(value, 0)]
    nodes = 0
    while pending:
        current, depth = pending.pop()
        nodes += 1
        if nodes > MAX_BRIDGE_JSON_NODES or depth > MAX_BRIDGE_JSON_DEPTH:
            raise BridgeRequestInvalidError()
        if isinstance(current, Mapping):
            if len(current) > MAX_BRIDGE_JSON_COLLECTION_ITEMS:
                raise BridgeRequestInvalidError()
            for key in current:
                _require_unicode_scalar_text(key)
            pending.extend((item, depth + 1) for item in current.values())
            continue
        if isinstance(current, Sequence) and not isinstance(current, str | bytes | bytearray):
            if len(current) > MAX_BRIDGE_JSON_COLLECTION_ITEMS:
                raise BridgeRequestInvalidError()
            pending.extend((item, depth + 1) for item in current)
            continue
        if isinstance(current, str):
            _require_unicode_scalar_text(current)
            continue
        if isinstance(current, float) and not math.isfinite(current):
            raise BridgeJsonInvalidError()


def _require_unicode_scalar_text(value: object) -> None:
    """Reject strings containing lone surrogate code points."""
    if not isinstance(value, str):
        raise BridgeJsonInvalidError()
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        pass
    else:
        return
    raise BridgeJsonInvalidError()


def _validation_location(error: ValidationError) -> str:
    """Return only the first bounded schema path, never its message or input."""
    issues = error.errors(include_url=False, include_input=False)
    if not issues:
        return "params"
    location = issues[0].get("loc", ())
    if not isinstance(location, tuple | list):
        return "params"
    parts: list[str] = []
    for item in location:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, int) and not isinstance(item, bool):
            parts.append(str(item))
        else:
            parts.append("unknown")
    value = ".".join(parts) or "params"
    return value[:_MAX_ERROR_LOCATION_CHARACTERS]
