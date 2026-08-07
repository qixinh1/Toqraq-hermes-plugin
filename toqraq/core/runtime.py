"""Exact engine-runtime identity, preparation, and ownership values."""

from __future__ import annotations

import re
from dataclasses import dataclass
from inspect import iscoroutinefunction
from pathlib import Path

from .absolute_path import require_absolute_normalized_path
from .capability_ids import HOST_ONLY_ENGINE_CAPABILITY_IDS
from .resource import AsyncResource

_MAX_OPAQUE_ID_CHARACTERS = 128
_MAX_COMPONENT_RELEASES = 32
_MAX_ENTRY_POINTS = 32
_MAX_CAPABILITIES = 64
_MAX_OWNED_RESOURCES = 64
_SYMBOLIC_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_NAMESPACED_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class RuntimePreparationCancelledError(Exception):
    """The owner cancelled local runtime verification before lease transfer."""


def validate_engine_id(value: str) -> str:
    """Return one bounded stable engine identifier or raise."""
    return _require_symbolic_id(value, "engine identifier")


def validate_namespaced_id(value: str) -> str:
    """Return one bounded namespaced identifier or raise."""
    if (
        not isinstance(value, str)
        or len(value) > _MAX_OPAQUE_ID_CHARACTERS
        or _NAMESPACED_ID.fullmatch(value) is None
    ):
        raise ValueError("namespaced identifier is invalid")
    return value


def validate_opaque_runtime_id(value: str) -> str:
    """Return one bounded provider-owned runtime identifier or raise."""
    return _require_opaque_id(value, "opaque runtime identifier")


def validate_component_release_id(value: str) -> str:
    """Return one canonical opaque component release identifier or raise."""
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError("component release identifier is invalid")
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class HostRuntimeTarget:
    """Exact host platform and architecture used to filter runtime releases."""

    platform: str
    architecture: str

    def __post_init__(self) -> None:
        """Reject host identities that cannot match a certified release."""
        _require_symbolic_id(self.platform, "runtime platform")
        _require_symbolic_id(self.architecture, "runtime architecture")


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeIdentity:
    """Complete immutable identity of one certified engine build."""

    engine_id: str
    version: str
    build_id: str
    distribution_id: str
    platform: str
    architecture: str

    def __post_init__(self) -> None:
        """Reject incomplete or ambiguous runtime identity fields."""
        validate_engine_id(self.engine_id)
        _require_opaque_id(self.version, "runtime version")
        _require_opaque_id(self.build_id, "runtime build identifier")
        _require_symbolic_id(self.distribution_id, "runtime distribution identifier")
        _require_symbolic_id(self.platform, "runtime platform")
        _require_symbolic_id(self.architecture, "runtime architecture")


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeEntryPointBinding:
    """Exact component entry point exposed under one runtime-owned name."""

    name: str
    component_release_id: str
    component_entry_point_name: str

    def __post_init__(self) -> None:
        """Reject implicit component or entry-point selection conventions."""
        _require_symbolic_id(self.name, "runtime entry-point name")
        validate_component_release_id(self.component_release_id)
        _require_symbolic_id(
            self.component_entry_point_name,
            "component entry-point name",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeRelease:
    """Certified components and bridge facts for one exact runtime identity."""

    identity: RuntimeIdentity
    component_release_ids: tuple[str, ...]
    entry_point_bindings: tuple[RuntimeEntryPointBinding, ...]
    bridge_id: str
    bridge_protocol: str
    capability_ids: frozenset[str] = frozenset()
    bridge_capability_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        """Validate every immutable release collection and exact identifier."""
        if not isinstance(self.identity, RuntimeIdentity):
            raise ValueError("runtime release identity is invalid")
        _require_unique_tuple(
            self.component_release_ids,
            "component releases",
            _MAX_COMPONENT_RELEASES,
        )
        if not self.component_release_ids or any(
            _is_invalid_component_release_id(value) for value in self.component_release_ids
        ):
            raise ValueError("component release identifiers are invalid")
        if (
            not isinstance(self.entry_point_bindings, tuple)
            or not self.entry_point_bindings
            or len(self.entry_point_bindings) > _MAX_ENTRY_POINTS
            or any(
                not isinstance(binding, RuntimeEntryPointBinding)
                for binding in self.entry_point_bindings
            )
        ):
            raise ValueError("runtime release requires a named entry point")
        names = tuple(binding.name for binding in self.entry_point_bindings)
        if len(set(names)) != len(names):
            raise ValueError("runtime entry-point names must be unique")
        component_release_ids = set(self.component_release_ids)
        if any(
            binding.component_release_id not in component_release_ids
            for binding in self.entry_point_bindings
        ):
            raise ValueError("runtime entry point references an unowned component release")
        validate_namespaced_id(self.bridge_id)
        _require_opaque_id(self.bridge_protocol, "bridge protocol")
        if (
            not isinstance(self.capability_ids, frozenset)
            or len(self.capability_ids) > _MAX_CAPABILITIES
        ):
            raise ValueError("runtime capability collection is invalid")
        for capability_id in self.capability_ids:
            validate_namespaced_id(capability_id)
        if (
            not isinstance(self.bridge_capability_ids, frozenset)
            or len(self.bridge_capability_ids) > _MAX_CAPABILITIES
        ):
            raise ValueError("runtime bridge capability collection is invalid")
        for capability_id in self.bridge_capability_ids:
            validate_namespaced_id(capability_id)
        if not self.bridge_capability_ids.issubset(self.capability_ids):
            raise ValueError("runtime bridge capabilities must be contribution capabilities")
        if self.bridge_capability_ids & HOST_ONLY_ENGINE_CAPABILITY_IDS:
            raise ValueError("runtime bridge capabilities contain a host-owned capability")

    @property
    def entry_point_names(self) -> tuple[str, ...]:
        """Return runtime-owned entry names in their certified binding order."""
        return tuple(binding.name for binding in self.entry_point_bindings)


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeEntryPoint:
    """One exact named absolute path in a verified prepared runtime."""

    name: str
    path: Path

    def __post_init__(self) -> None:
        """Reject ambiguous names and relative or non-normalized paths."""
        _require_symbolic_id(self.name, "runtime entry-point name")
        require_absolute_normalized_path(self.path, "runtime entry-point path")


@dataclass(frozen=True, slots=True, kw_only=True)
class PreparedRuntime:
    """Exact verified runtime paths and resources transferred to a session owner."""

    release: RuntimeRelease
    entry_points: tuple[RuntimeEntryPoint, ...]
    owned_resources: tuple[AsyncResource, ...]

    def __post_init__(self) -> None:
        """Bind exact entry points and unique resources to one release."""
        if not isinstance(self.release, RuntimeRelease):
            raise ValueError("prepared runtime release is invalid")
        if not isinstance(self.entry_points, tuple) or any(
            not isinstance(entry, RuntimeEntryPoint) for entry in self.entry_points
        ):
            raise ValueError("prepared runtime entry points are invalid")
        names = tuple(entry.name for entry in self.entry_points)
        if names != self.release.entry_point_names:
            raise ValueError("prepared runtime entry points do not match its release")
        if (
            not isinstance(self.owned_resources, tuple)
            or not self.owned_resources
            or len(self.owned_resources) > _MAX_OWNED_RESOURCES
            or any(not isinstance(resource, AsyncResource) for resource in self.owned_resources)
            or any(not iscoroutinefunction(resource.close) for resource in self.owned_resources)
            or len({id(resource) for resource in self.owned_resources}) != len(self.owned_resources)
        ):
            raise ValueError("prepared runtime resources are invalid")

    def entry_point(self, name: str) -> Path:
        """Return one certified named path without guessing an executable."""
        _require_symbolic_id(name, "runtime entry-point name")
        for entry in self.entry_points:
            if entry.name == name:
                return entry.path
        raise KeyError(name)


def _require_symbolic_id(value: str, label: str) -> str:
    """Require one bounded lowercase identifier without path meaning."""
    if (
        not isinstance(value, str)
        or len(value) > _MAX_OPAQUE_ID_CHARACTERS
        or _SYMBOLIC_ID.fullmatch(value) is None
    ):
        raise ValueError(f"{label} is invalid")
    return value


def _require_opaque_id(value: str, label: str) -> str:
    """Require one bounded opaque provider-owned identifier."""
    if (
        not isinstance(value, str)
        or len(value) > _MAX_OPAQUE_ID_CHARACTERS
        or _OPAQUE_ID.fullmatch(value) is None
    ):
        raise ValueError(f"{label} is invalid")
    return value


def _require_unique_tuple(values: tuple[str, ...], label: str, maximum: int) -> None:
    """Require one bounded strict tuple with no ambiguous duplicate values."""
    if (
        not isinstance(values, tuple)
        or len(values) > maximum
        or any(not isinstance(value, str) for value in values)
        or len(set(values)) != len(values)
    ):
        raise ValueError(f"{label} collection is invalid")


def _is_invalid_component_release_id(value: object) -> bool:
    """Return whether a value cannot identify one certified component release."""
    return not isinstance(value, str) or _SHA256.fullmatch(value) is None
