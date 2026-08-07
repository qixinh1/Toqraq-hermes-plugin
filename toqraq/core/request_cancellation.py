"""Pure same-connection request cancellation values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .bridge import BridgeRequestReference


class CancellationDisposition(StrEnum):
    """Safe idempotent state of one cancellation attempt."""

    REQUESTED = "requested"
    ALREADY_TERMINAL = "already_terminal"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True, kw_only=True)
class CancelRequestCommand:
    """Reference to one request owned by the same authenticated connection."""

    target: BridgeRequestReference

    def __post_init__(self) -> None:
        """Reject raw or cross-boundary target identities."""
        if not isinstance(self.target, BridgeRequestReference):
            raise ValueError("cancellation target request is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class CancellationAcknowledgement:
    """Current idempotent disposition for the request-bound target."""

    disposition: CancellationDisposition

    def __post_init__(self) -> None:
        """Require one closed safe disposition."""
        if not isinstance(self.disposition, CancellationDisposition):
            raise ValueError("cancellation disposition is invalid")
