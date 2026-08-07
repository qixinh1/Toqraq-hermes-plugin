"""Strict immutable records for components certified with one plugin release."""

from __future__ import annotations

import re
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from ..core.capability_ids import HOST_ONLY_ENGINE_CAPABILITY_IDS
from ..core.component import ComponentKind
from ..core.runtime import validate_opaque_runtime_id
from .network import (
    canonical_allowed_origin,
    canonical_component_origin,
    validate_component_https_url,
)
from .paths import is_portable_component_part

MAX_COMPONENT_PACKAGE_BYTES = 64 << 30
MAX_COMPONENT_INSTALLED_BYTES = 256 << 30
MAX_COMPONENT_DEPENDENCIES = 16
MAX_COMPONENT_ENTRY_POINTS = 32
MAX_COMPONENT_CAPABILITIES = 64

_COMPONENT_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")
_SYMBOLIC_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _opaque_path_token(value: str) -> str:
    """Validate an opaque identifier before it participates in a store path."""
    if value != value.strip() or value in {".", ".."}:
        raise ValueError("path token has ambiguous whitespace or traversal meaning")
    if any(character in value for character in "/\\") or not is_portable_component_part(value):
        raise ValueError("path token is not a portable path segment")
    return value


def validate_component_id(value: str) -> str:
    """Require a namespaced component identifier."""
    if _COMPONENT_ID.fullmatch(value) is None:
        raise ValueError("component identifier is invalid")
    return value


def _symbolic_id(value: str) -> str:
    """Require a stable symbolic identifier."""
    if _SYMBOLIC_ID.fullmatch(value) is None:
        raise ValueError("symbolic identifier is invalid")
    return value


def _sha256(value: str) -> str:
    """Require a canonical SHA-256 digest."""
    if _SHA256.fullmatch(value) is None:
        raise ValueError("SHA-256 digest must be 64 lowercase hexadecimal characters")
    return value


def _relative_install_path(value: str) -> str:
    """Validate a portable relative path declared by a certified record."""
    if not value or len(value) > 512 or "\\" in value or value.startswith("/"):
        raise ValueError("entry-point path must be a bounded POSIX relative path")
    parts = value.split("/")
    for part in parts:
        if (
            not part
            or part in {".", ".."}
            or len(part) > 128
            or not is_portable_component_part(part)
        ):
            raise ValueError("entry-point path contains an unsafe segment")
    return value


OpaquePathToken = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128),
    AfterValidator(_opaque_path_token),
]
ComponentId = Annotated[
    str,
    StringConstraints(min_length=3, max_length=128),
    AfterValidator(validate_component_id),
]
SymbolicId = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128),
    AfterValidator(_symbolic_id),
]
Sha256 = Annotated[str, StringConstraints(min_length=64, max_length=64), AfterValidator(_sha256)]
HttpsUrl = Annotated[
    str,
    StringConstraints(min_length=9, max_length=2_048),
    AfterValidator(validate_component_https_url),
]
Origin = Annotated[
    str,
    StringConstraints(min_length=9, max_length=255),
    AfterValidator(canonical_allowed_origin),
]
RelativeInstallPath = Annotated[
    str,
    StringConstraints(min_length=1, max_length=512),
    AfterValidator(_relative_install_path),
]
BoundedLabel = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)
]
BridgeProtocol = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128),
    AfterValidator(validate_opaque_runtime_id),
]


class ComponentRecord(BaseModel):
    """Base policy shared by every bundled component record value."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ComponentIdentity(ComponentRecord):
    """Complete immutable identity of one installable component package."""

    component_id: ComponentId
    version: OpaquePathToken
    build_id: OpaquePathToken
    platform: SymbolicId
    architecture: SymbolicId
    package_sha256: Sha256

    @property
    def key(self) -> tuple[str, str, str, str, str, str]:
        """Return the complete identity as a deterministic comparison key."""
        return (
            self.component_id,
            self.version,
            self.build_id,
            self.platform,
            self.architecture,
            self.package_sha256,
        )


class ComponentSource(ComponentRecord):
    """Publisher, provenance, and network boundary of a package."""

    publisher: BoundedLabel
    package_url: HttpsUrl
    provenance_url: HttpsUrl
    allowed_origins: tuple[Origin, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_origins(self) -> Self:
        """Require unique canonical origins and authorize the initial URL."""
        if len(set(self.allowed_origins)) != len(self.allowed_origins):
            raise ValueError("allowed download origins must be unique")
        if canonical_component_origin(self.package_url) not in self.allowed_origins:
            raise ValueError("package URL origin is not allowed")
        return self


class ComponentLicense(ComponentRecord):
    """License facts displayed before component preparation."""

    identifier: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ]
    name: BoundedLabel
    url: HttpsUrl
    acceptance_required: bool


class ComponentEntryPoint(ComponentRecord):
    """One named path a consumer may resolve after verification."""

    name: SymbolicId
    relative_path: RelativeInstallPath
    executable: bool


class ComponentBridge(ComponentRecord):
    """Exact runtime-bridge facts supplied by one component."""

    bridge_id: ComponentId
    protocol: BridgeProtocol
    capabilities: tuple[ComponentId, ...] = Field(
        max_length=MAX_COMPONENT_CAPABILITIES,
    )

    @model_validator(mode="after")
    def validate_capabilities(self) -> Self:
        """Reject an ambiguous native capability declaration."""
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("bridge capabilities must be unique")
        if set(self.capabilities) & HOST_ONLY_ENGINE_CAPABILITY_IDS:
            raise ValueError("bridge capabilities contain a host-owned capability")
        return self


class ComponentRelease(ComponentRecord):
    """One exact component release certified for one Toqraq plugin build."""

    record_version: Annotated[int, Field(ge=1, le=1)]
    kind: ComponentKind
    plugin_version: OpaquePathToken
    identity: ComponentIdentity
    label: BoundedLabel
    source: ComponentSource
    package_bytes: Annotated[int, Field(gt=0, le=MAX_COMPONENT_PACKAGE_BYTES)]
    installed_bytes: Annotated[int, Field(gt=0, le=MAX_COMPONENT_INSTALLED_BYTES)]
    install_strategy: ComponentId
    expected_tree_sha256: Sha256
    entry_points: tuple[ComponentEntryPoint, ...] = Field(
        min_length=1,
        max_length=MAX_COMPONENT_ENTRY_POINTS,
    )
    dependencies: tuple[ComponentIdentity, ...] = Field(
        default=(),
        max_length=MAX_COMPONENT_DEPENDENCIES,
    )
    capabilities: tuple[ComponentId, ...] = Field(
        default=(),
        max_length=MAX_COMPONENT_CAPABILITIES,
    )
    bridge: ComponentBridge | None
    license: ComponentLicense
    authentication_required: bool

    @model_validator(mode="after")
    def validate_collections(self) -> Self:
        """Reject ambiguous names, paths, dependencies, and capabilities."""
        entry_names = [entry.name for entry in self.entry_points]
        entry_paths = [entry.relative_path.casefold() for entry in self.entry_points]
        dependency_keys = [dependency.key for dependency in self.dependencies]
        if len(set(entry_names)) != len(entry_names):
            raise ValueError("entry-point names must be unique")
        if len(set(entry_paths)) != len(entry_paths):
            raise ValueError("entry-point paths must not collide")
        if len(set(dependency_keys)) != len(dependency_keys):
            raise ValueError("component dependencies must be unique")
        if self.identity.key in dependency_keys:
            raise ValueError("component release must not depend on itself")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("component capabilities must be unique")
        if self.bridge is not None and not set(self.bridge.capabilities).issubset(
            self.capabilities
        ):
            raise ValueError("bridge capabilities must be component capabilities")
        return self
