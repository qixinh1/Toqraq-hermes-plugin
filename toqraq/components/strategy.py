"""Open registry boundary for exact component package installation."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Event
from typing import Protocol

from .content_policy import ComponentContentPolicy
from .release import ComponentRelease, validate_component_id


class ComponentStrategyRejection(StrEnum):
    """Stable reasons a package install strategy cannot be selected."""

    DUPLICATE = "duplicate"
    NOT_REGISTERED = "not_registered"


class ComponentStrategyRejectedError(ValueError):
    """Composition or release data references an unusable install strategy."""

    def __init__(self, reason: ComponentStrategyRejection) -> None:
        """Retain the stable rejection without exposing record content."""
        self.reason = reason
        super().__init__(f"component install strategy rejected: {reason.value}")


class ComponentInstallCancelledError(Exception):
    """The owning component operation cancelled package installation."""


class ComponentInstallRejection(StrEnum):
    """Stable reasons a selected strategy cannot prepare its package."""

    PACKAGE_INVALID = "package_invalid"
    CONTENT_INVALID = "content_invalid"
    ENTRY_POINT_INVALID = "entry_point_invalid"


class ComponentInstallRejectedError(ValueError):
    """A verified package cannot produce its certified component tree."""

    def __init__(
        self,
        reason: ComponentInstallRejection,
        *,
        cause: BaseException | None = None,
    ) -> None:
        """Retain one stable reason and private diagnostic cause."""
        self.reason = reason
        self.cause = cause
        super().__init__(f"component package install rejected: {reason.value}")


@dataclass(frozen=True, slots=True)
class ComponentInstallProgress:
    """Authoritative installed-byte progress for one prepared package."""

    completed_bytes: int
    total_bytes: int


class ComponentPackageInstallStrategy(Protocol):
    """Prepare one verified package in a caller-owned staging directory."""

    @property
    def strategy_id(self) -> str:
        """Return the stable release-facing strategy identifier."""
        ...

    @property
    def content_policy(self) -> ComponentContentPolicy:
        """Return bounds used to verify the resulting component tree."""
        ...

    def install(
        self,
        package: Path,
        staging: Path,
        release: ComponentRelease,
        *,
        cancellation: Event | None = None,
        progress: Callable[[ComponentInstallProgress], None] | None = None,
    ) -> None:
        """Populate staging or raise without publishing it."""
        ...


class ComponentStrategyCatalog:
    """Immutable explicit composition of available package strategies."""

    def __init__(self, strategies: Iterable[ComponentPackageInstallStrategy]) -> None:
        """Index strategies once and reject ambiguous composition."""
        indexed: dict[str, ComponentPackageInstallStrategy] = {}
        for strategy in strategies:
            try:
                validate_component_id(strategy.strategy_id)
            except (TypeError, ValueError) as exc:
                raise ComponentStrategyRejectedError(
                    ComponentStrategyRejection.NOT_REGISTERED
                ) from exc
            if strategy.strategy_id in indexed:
                raise ComponentStrategyRejectedError(ComponentStrategyRejection.DUPLICATE)
            indexed[strategy.strategy_id] = strategy
        self._strategies = indexed

    def resolve(self, strategy_id: str) -> ComponentPackageInstallStrategy:
        """Return the exact registered strategy required by a release."""
        try:
            return self._strategies[strategy_id]
        except KeyError as exc:
            raise ComponentStrategyRejectedError(ComponentStrategyRejection.NOT_REGISTERED) from exc
