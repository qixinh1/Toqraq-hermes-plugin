"""Platform-neutral values and port for bounded native-window discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .geometry import Size
from .preview import NativeWindowReference

MAX_NATIVE_PREVIEW_CANDIDATES = 16


@dataclass(frozen=True, slots=True, kw_only=True)
class NativeWindowCandidate:
    """One visible client surface currently owned by an exact process."""

    window: NativeWindowReference
    process_id: int
    client_size: Size

    def __post_init__(self) -> None:
        """Reject invalid process identities or empty client geometry."""
        if not isinstance(self.window, NativeWindowReference):
            raise ValueError("native preview candidate window is invalid")
        if (
            isinstance(self.process_id, bool)
            or not isinstance(self.process_id, int)
            or self.process_id < 1
        ):
            raise ValueError("native preview candidate process is invalid")
        if not isinstance(self.client_size, Size):
            raise ValueError("native preview candidate size is invalid")

    @property
    def area(self) -> int:
        """Return exact client pixels for deterministic engine selection."""
        return self.client_size.width * self.client_size.height


@runtime_checkable
class NativeWindowDiscovery(Protocol):
    """Read-only platform primitive used by engine-owned preview locators."""

    def for_process(self, process_id: int) -> tuple[NativeWindowCandidate, ...]:
        """Return at most the largest bounded visible windows for one process."""
        ...
