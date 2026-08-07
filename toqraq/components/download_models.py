"""Immutable values and stable failures for component package acquisition."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

MAX_DOWNLOAD_CHUNK_BYTES = 8 << 20


class ComponentDownloadRejection(StrEnum):
    """Stable reasons an exact package acquisition cannot complete."""

    FILE_INVALID = "file_invalid"
    ORIGIN_REJECTED = "origin_rejected"
    REDIRECT_LIMIT = "redirect_limit"
    RESPONSE_INVALID = "response_invalid"
    SIZE_MISMATCH = "size_mismatch"
    DIGEST_MISMATCH = "digest_mismatch"
    TIMEOUT = "timeout"
    TRANSPORT_FAILED = "transport_failed"


class ComponentDownloadRejectedError(ValueError):
    """A package source, response, file, or digest violated its release."""

    def __init__(
        self,
        reason: ComponentDownloadRejection,
        *,
        cause: BaseException | None = None,
    ) -> None:
        """Retain one stable reason and private diagnostic cause."""
        self.reason = reason
        self.cause = cause
        super().__init__(f"component download rejected: {reason.value}")


class ComponentDownloadCancelledError(Exception):
    """The owning component task cancelled while retaining resumable bytes."""


@dataclass(frozen=True, slots=True)
class ComponentDownloadPolicy:
    """Network, redirect, buffering, and durability bounds for downloads."""

    io_timeout_seconds: float
    idle_timeout_seconds: float
    total_timeout_seconds: float
    chunk_bytes: int
    checkpoint_bytes: int
    max_redirects: int
    user_agent: str

    def __post_init__(self) -> None:
        """Reject unusable or unbounded download policy."""
        times = (
            self.io_timeout_seconds,
            self.idle_timeout_seconds,
            self.total_timeout_seconds,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            or value <= 0
            for value in times
        ):
            raise ValueError("component download timeouts must be finite and positive")
        if not self.io_timeout_seconds <= self.idle_timeout_seconds <= self.total_timeout_seconds:
            raise ValueError("component download timeouts are not ordered")
        if (
            isinstance(self.chunk_bytes, bool)
            or not isinstance(self.chunk_bytes, int)
            or not 1 <= self.chunk_bytes <= MAX_DOWNLOAD_CHUNK_BYTES
            or isinstance(self.checkpoint_bytes, bool)
            or not isinstance(self.checkpoint_bytes, int)
            or self.checkpoint_bytes < self.chunk_bytes
            or isinstance(self.max_redirects, bool)
            or not isinstance(self.max_redirects, int)
            or not 0 <= self.max_redirects <= 16
        ):
            raise ValueError("component download size or redirect policy is invalid")
        if (
            not self.user_agent
            or len(self.user_agent) > 128
            or any(ord(character) < 33 or ord(character) > 126 for character in self.user_agent)
        ):
            raise ValueError("component download user agent must be bounded visible ASCII")


@dataclass(frozen=True, slots=True)
class ComponentDownloadProgress:
    """Authoritative byte progress for one exact package."""

    completed_bytes: int
    total_bytes: int


@dataclass(frozen=True, slots=True)
class DownloadedComponentPackage:
    """Verified local package ready for its registered install strategy."""

    path: Path
    size: int
    sha256: str
