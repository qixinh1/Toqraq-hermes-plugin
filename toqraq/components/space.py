"""Disk-capacity preflight for managed component transactions."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class ComponentSpacePhase(StrEnum):
    """Stable allocation phase whose exact bytes were checked."""

    DOWNLOAD = "download"
    INSTALL = "install"


class ComponentSpaceRejection(StrEnum):
    """Stable reasons storage capacity cannot authorize a write."""

    INSUFFICIENT = "insufficient"
    PROBE_FAILED = "probe_failed"


class ComponentSpaceRejectedError(OSError):
    """The managed store lacks proven capacity for one bounded phase."""

    def __init__(
        self,
        reason: ComponentSpaceRejection,
        phase: ComponentSpacePhase,
        required_bytes: int,
        available_bytes: int | None,
        *,
        cause: BaseException | None = None,
    ) -> None:
        """Retain safe numeric facts and a private diagnostic cause."""
        self.reason = reason
        self.phase = phase
        self.required_bytes = required_bytes
        self.available_bytes = available_bytes
        self.cause = cause
        super().__init__(f"component storage rejected: {reason.value}")


@dataclass(frozen=True, slots=True)
class ComponentSpacePolicy:
    """Capacity held back from component payload allocation."""

    reserve_bytes: int

    def __post_init__(self) -> None:
        """Require one finite non-negative integer reserve."""
        if (
            isinstance(self.reserve_bytes, bool)
            or not isinstance(self.reserve_bytes, int)
            or self.reserve_bytes < 0
        ):
            raise ValueError("component storage reserve must be a non-negative integer")


class ComponentSpaceProbe(Protocol):
    """Read free bytes from the filesystem containing a managed path."""

    def available_bytes(self, path: Path) -> int:
        """Return currently available bytes for the selected filesystem."""
        ...


class SystemComponentSpaceProbe:
    """Standard-library filesystem capacity adapter."""

    def available_bytes(self, path: Path) -> int:
        """Return the operating system's current free-byte report."""
        return shutil.disk_usage(path).free


def require_component_space(
    probe: ComponentSpaceProbe,
    policy: ComponentSpacePolicy,
    path: Path,
    payload_bytes: int,
    phase: ComponentSpacePhase,
) -> None:
    """Require payload plus reserve without exposing the managed path on failure."""
    if isinstance(payload_bytes, bool) or not isinstance(payload_bytes, int) or payload_bytes < 0:
        raise ValueError("component payload size must be a non-negative integer")
    required = payload_bytes + policy.reserve_bytes
    try:
        available = probe.available_bytes(path)
    except OSError as exc:
        raise ComponentSpaceRejectedError(
            ComponentSpaceRejection.PROBE_FAILED,
            phase,
            required,
            None,
            cause=exc,
        ) from exc
    if isinstance(available, bool) or not isinstance(available, int) or available < 0:
        raise ComponentSpaceRejectedError(
            ComponentSpaceRejection.PROBE_FAILED,
            phase,
            required,
            None,
        )
    if available < required:
        raise ComponentSpaceRejectedError(
            ComponentSpaceRejection.INSUFFICIENT,
            phase,
            required,
            available,
        )
