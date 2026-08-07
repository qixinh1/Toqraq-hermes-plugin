"""Pure run-scoped observation primitives shared by focused read ports."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from .bridge import MAX_BRIDGE_RUN_REVISION
from .runtime import validate_namespaced_id

MAX_OBSERVATION_TOKEN_CHARACTERS = 128
MAX_ENGINE_EXTENSION_FACTS = 32
MAX_ENGINE_EXTENSION_TEXT_BYTES = 1_024
MAX_OBSERVATION_TIMESTAMP = MAX_BRIDGE_RUN_REVISION

_OPAQUE_OBSERVATION_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


def validate_observation_token(value: str) -> str:
    """Return one bounded opaque run-scoped token or raise."""
    if (
        not isinstance(value, str)
        or len(value) > MAX_OBSERVATION_TOKEN_CHARACTERS
        or _OPAQUE_OBSERVATION_TOKEN.fullmatch(value) is None
    ):
        raise ValueError("observation token is invalid")
    return value


def validate_observation_label(value: str, *, maximum_bytes: int) -> str:
    """Return bounded non-control UTF-8 engine identity text or raise."""
    encoded = _encoded_text(value, maximum_bytes=maximum_bytes, allow_empty=False)
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise ValueError("observation label contains a control character")
    if not encoded:
        raise ValueError("observation label is empty")
    return value


def validate_observation_text(
    value: str,
    *,
    maximum_bytes: int,
    allow_empty: bool = True,
) -> str:
    """Return bounded UTF-8 observation prose without an embedded null."""
    _encoded_text(value, maximum_bytes=maximum_bytes, allow_empty=allow_empty)
    if "\0" in value:
        raise ValueError("observation text contains a null character")
    return value


def validate_observation_count(value: int, *, label: str) -> int:
    """Return one non-negative cross-language-exact count or raise."""
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= MAX_BRIDGE_RUN_REVISION
    ):
        raise ValueError(f"{label} is invalid")
    return value


def validate_observation_timestamp(value: int) -> int:
    """Return non-negative Unix milliseconds safe in every bridge language."""
    return validate_observation_count(value, label="observation timestamp")


@dataclass(frozen=True, slots=True, kw_only=True)
class RunObjectReference:
    """Opaque object identity valid only on its authenticated bridge run."""

    value: str

    def __post_init__(self) -> None:
        """Reject values that expose path syntax or exceed the wire bound."""
        validate_observation_token(self.value)


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservationRevision:
    """Opaque revision for one mutable observation family in one run."""

    value: str

    def __post_init__(self) -> None:
        """Keep revision semantics engine-owned and transport-safe."""
        validate_observation_token(self.value)


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservationCursor:
    """Opaque continuation position tied to one observation revision."""

    value: str

    def __post_init__(self) -> None:
        """Reject page numbers and unbounded engine cursor encodings."""
        validate_observation_token(self.value)


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservationStamp:
    """Revision and collection time shared by one authoritative result."""

    revision: ObservationRevision
    observed_at_unix_ms: int

    def __post_init__(self) -> None:
        """Require one valid revision and cross-language timestamp."""
        if not isinstance(self.revision, ObservationRevision):
            raise ValueError("observation stamp revision is invalid")
        validate_observation_timestamp(self.observed_at_unix_ms)


class EngineFactKind(StrEnum):
    """Closed scalar shapes allowed in a namespaced engine extension."""

    TEXT = "text"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    REFERENCE = "reference"


EngineFactPayload: TypeAlias = str | int | float | bool | RunObjectReference


@dataclass(frozen=True, slots=True, kw_only=True)
class EngineFact:
    """One flat typed engine-native fact with no recursive JSON escape."""

    field_id: str
    kind: EngineFactKind
    value: EngineFactPayload

    def __post_init__(self) -> None:
        """Validate the discriminator, exact payload type, and scalar bound."""
        validate_namespaced_id(self.field_id)
        if not isinstance(self.kind, EngineFactKind):
            raise ValueError("engine fact kind is invalid")
        if self.kind is EngineFactKind.TEXT:
            if not isinstance(self.value, str):
                raise ValueError("engine text fact value is invalid")
            validate_observation_text(
                self.value,
                maximum_bytes=MAX_ENGINE_EXTENSION_TEXT_BYTES,
            )
            return
        if self.kind is EngineFactKind.INTEGER:
            _require_exact_integer(self.value, label="engine integer fact")
            return
        if self.kind is EngineFactKind.NUMBER:
            if type(self.value) is not float or not math.isfinite(self.value):
                raise ValueError("engine number fact value is invalid")
            return
        if self.kind is EngineFactKind.BOOLEAN:
            if type(self.value) is not bool:
                raise ValueError("engine boolean fact value is invalid")
            return
        if not isinstance(self.value, RunObjectReference):
            raise ValueError("engine reference fact value is invalid")


def validate_engine_facts(value: tuple[EngineFact, ...]) -> None:
    """Require one bounded tuple of unique namespaced scalar facts."""
    if (
        not isinstance(value, tuple)
        or len(value) > MAX_ENGINE_EXTENSION_FACTS
        or any(not isinstance(fact, EngineFact) for fact in value)
    ):
        raise ValueError("engine extension facts are invalid")
    field_ids = tuple(fact.field_id for fact in value)
    if len(set(field_ids)) != len(field_ids):
        raise ValueError("engine extension fact IDs must be unique")


def require_exact_integer(value: int, *, label: str) -> int:
    """Expose the bridge-safe signed-integer rule to focused values."""
    return _require_exact_integer(value, label=label)


def _require_exact_integer(value: object, *, label: str) -> int:
    """Reject booleans and integers that lose precision in bridge languages."""
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not -MAX_BRIDGE_RUN_REVISION <= value <= MAX_BRIDGE_RUN_REVISION
    ):
        raise ValueError(f"{label} is invalid")
    return value


def _encoded_text(value: str, *, maximum_bytes: int, allow_empty: bool) -> bytes:
    """Encode once so character counts cannot understate the byte budget."""
    if not isinstance(value, str) or maximum_bytes < 1 or (not allow_empty and not value):
        raise ValueError("observation text is invalid")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("observation text is not valid UTF-8") from exc
    if len(encoded) > maximum_bytes:
        raise ValueError("observation text exceeds its UTF-8 byte bound")
    return encoded
