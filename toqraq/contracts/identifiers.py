"""Bounded public identifiers shared by HTTP and Hermes tools."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, Field, StringConstraints

from ..core.bridge import validate_bridge_session_id

MAX_JSON_INTEGER = (1 << 53) - 1
_SYMBOLIC_ID_PATTERN = r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
_CANONICAL_UUID4_PATTERN = (
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
CanonicalUuid4Text = Annotated[
    str,
    StringConstraints(
        min_length=36,
        max_length=36,
        pattern=_CANONICAL_UUID4_PATTERN,
    ),
]
Sha256Value = Annotated[
    str,
    StringConstraints(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"),
]

EngineId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=_SYMBOLIC_ID_PATTERN,
    ),
]
EngineVersion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
RuntimeOpaqueId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]*$",
    ),
]
RuntimeSymbolicId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=_SYMBOLIC_ID_PATTERN,
    ),
]
HermesSessionId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=512),
    AfterValidator(validate_bridge_session_id),
]
RunRevision = Annotated[int, Field(gt=0, le=MAX_JSON_INTEGER)]
AttachmentId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
ProjectPath = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=32_767),
]
ProcessId = Annotated[int, Field(gt=0, le=MAX_JSON_INTEGER)]
CapabilityId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=_SYMBOLIC_ID_PATTERN,
    ),
]
DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]
ComponentId = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=128,
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$",
    ),
]
ComponentVersion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
ComponentBuildId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
ComponentReleaseId = Sha256Value
ComponentOperationId = CanonicalUuid4Text
HttpsUrlValue = Annotated[
    str,
    StringConstraints(min_length=9, max_length=2_048, pattern=r"^https://[^\s]+$"),
]
PlatformId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=32,
        pattern=r"^[a-z][a-z0-9_-]*$",
    ),
]
