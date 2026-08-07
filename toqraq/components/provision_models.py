"""Immutable states and stable failures for component preparation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ComponentProvisionPhase(StrEnum):
    """Ordered user-visible phases of one component preparation."""

    CHECKING = "checking"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    VERIFYING = "verifying"
    READY = "ready"


class ComponentProvisionRejection(StrEnum):
    """Stable categories for a failed component preparation."""

    STRATEGY_UNAVAILABLE = "strategy_unavailable"
    STORAGE_UNAVAILABLE = "storage_unavailable"
    DOWNLOAD_FAILED = "download_failed"
    INSTALL_FAILED = "install_failed"
    PUBLICATION_FAILED = "publication_failed"
    OWNERSHIP_TIMEOUT = "ownership_timeout"
    OWNERSHIP_FAILED = "ownership_failed"


class ComponentProvisionRejectedError(RuntimeError):
    """A component preparation reached a typed non-cancellation failure."""

    def __init__(
        self,
        reason: ComponentProvisionRejection,
        *,
        cause: BaseException | None = None,
    ) -> None:
        """Retain one stable reason and private diagnostic cause."""
        self.reason = reason
        self.cause = cause
        super().__init__(f"component provision rejected: {reason.value}")


class ComponentProvisionCancelledError(Exception):
    """The owning component preparation was cancelled before publication."""


@dataclass(frozen=True, slots=True)
class ComponentProvisionProgress:
    """One authoritative phase and bounded byte position."""

    phase: ComponentProvisionPhase
    completed_bytes: int
    total_bytes: int

    def __post_init__(self) -> None:
        """Reject impossible progress snapshots at their source."""
        values = (self.completed_bytes, self.total_bytes)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValueError("component progress bytes must be integers")
        if not 0 <= self.completed_bytes <= self.total_bytes:
            raise ValueError("component progress bytes are outside their total")
