"""Pure semantic values shared by managed component boundaries."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from threading import Event
from typing import Protocol


class ComponentKind(StrEnum):
    """Closed product roles whose acquisition behavior remains adapter-owned."""

    ENGINE = "engine"
    BRIDGE = "bridge"
    TOOL = "tool"
    MODEL = "model"


class ComponentReadiness(StrEnum):
    """Authoritative state of one certified release in the managed store."""

    MISSING = "missing"
    INVALID = "invalid"
    READY = "ready"


class ComponentJobAction(StrEnum):
    """Mutations available through the asynchronous component surface."""

    PREPARE = "prepare"
    REMOVE = "remove"


class ComponentWorkPhase(StrEnum):
    """Engine-independent work phases emitted by a component adapter."""

    CHECKING = "checking"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    VERIFYING = "verifying"
    REMOVING = "removing"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class ComponentSource:
    """Pure public provenance facts from a certified release."""

    publisher: str
    package_url: str
    provenance_url: str


@dataclass(frozen=True, slots=True)
class ComponentLicense:
    """Pure public license facts from a certified release."""

    identifier: str
    name: str
    url: str
    acceptance_required: bool


@dataclass(frozen=True, slots=True)
class ManagedComponent:
    """Public-safe component inventory value without local paths."""

    release_id: str
    component_id: str
    kind: ComponentKind
    label: str
    version: str
    build_id: str
    platform: str
    architecture: str
    package_bytes: int
    installed_bytes: int
    package_sha256: str
    source: ComponentSource
    license: ComponentLicense
    authentication_required: bool
    capabilities: tuple[str, ...]
    readiness: ComponentReadiness
    in_use: bool


@dataclass(frozen=True, slots=True)
class ComponentWorkProgress:
    """Bounded progress emitted by one adapter-owned operation."""

    phase: ComponentWorkPhase
    completed_bytes: int
    total_bytes: int

    def __post_init__(self) -> None:
        """Reject impossible progress at its internal source."""
        values = (self.completed_bytes, self.total_bytes)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValueError("component work progress must use integer bytes")
        if not 0 <= self.completed_bytes <= self.total_bytes:
            raise ValueError("component work progress exceeds its total")


class ComponentWorkCancelledError(Exception):
    """A component adapter observed cancellation before its commit point."""


ComponentProgressObserver = Callable[[ComponentWorkProgress], None]


class ComponentInventory(Protocol):
    """Read-only process-wide certified component inventory."""

    def list_components(self) -> tuple[ManagedComponent, ...]:
        """Return every selectable release in deterministic order."""
        ...

    def require_component(self, release_id: str) -> ManagedComponent:
        """Return one known release or raise a typed application failure."""
        ...


class ComponentPreparation(Protocol):
    """Prepare one exact release behind an opaque release identifier."""

    def prepare_component(
        self,
        release_id: str,
        cancellation: Event,
        progress: ComponentProgressObserver,
    ) -> None:
        """Prepare or repair the release, returning only after atomic readiness."""
        ...


class ComponentRemoval(Protocol):
    """Remove one exact unleased release from managed storage."""

    def remove_component(
        self,
        release_id: str,
        cancellation: Event,
        progress: ComponentProgressObserver,
    ) -> None:
        """Remove the release or raise a typed application failure."""
        ...
