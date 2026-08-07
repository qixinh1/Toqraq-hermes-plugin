"""Godot-owned discovery of the player window created by a managed launch."""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from threading import Event

from ...core.engine_contribution import ProjectDescription
from ...core.errors import (
    GameWindowNotFoundError,
    PlatformOperationError,
    RequestCancelledError,
    ToqraqError,
)
from ...core.native_preview import NativeWindowCandidate, NativeWindowDiscovery
from ...core.preview import NativeWindowSurface
from ...core.process_tree import ProcessTree
from ...core.runtime import PreparedRuntime
from .identity import GODOT_ENGINE_ID

DEFAULT_GODOT_PREVIEW_TIMEOUT_SECONDS = 20.0
DEFAULT_GODOT_PREVIEW_POLL_SECONDS = 0.05
MAX_GODOT_PREVIEW_POLICY_SECONDS = 300.0

MonotonicClock = Callable[[], float]
Delay = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True, kw_only=True)
class GodotPreviewLocatorPolicy:
    """Bounds for observing the one player window created after launch."""

    timeout_seconds: float = DEFAULT_GODOT_PREVIEW_TIMEOUT_SECONDS
    poll_seconds: float = DEFAULT_GODOT_PREVIEW_POLL_SECONDS

    def __post_init__(self) -> None:
        """Reject disabled, non-finite, or unbounded discovery waits."""
        for value in (self.timeout_seconds, self.poll_seconds):
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(value)
                or not 0 < value <= MAX_GODOT_PREVIEW_POLICY_SECONDS
            ):
                raise ValueError("Godot preview policy is invalid")
        if self.poll_seconds > self.timeout_seconds:
            raise ValueError("Godot preview policy is inconsistent")


class GodotPreviewLocator:
    """Select the largest visible client owned by the direct Godot player."""

    def __init__(
        self,
        discovery: NativeWindowDiscovery,
        policy: GodotPreviewLocatorPolicy | None = None,
        *,
        clock: MonotonicClock = time.monotonic,
        delay: Delay = asyncio.sleep,
    ) -> None:
        """Bind one platform discovery primitive and deterministic wait policy."""
        if not isinstance(discovery, NativeWindowDiscovery):
            raise ValueError("Godot preview discovery port is invalid")
        selected = policy or GodotPreviewLocatorPolicy()
        if not isinstance(selected, GodotPreviewLocatorPolicy):
            raise ValueError("Godot preview locator policy is invalid")
        if not callable(clock) or not callable(delay):
            raise ValueError("Godot preview timing dependency is invalid")
        self._discovery = discovery
        self._policy = selected
        self._clock = clock
        self._delay = delay

    @property
    def engine_id(self) -> str:
        """Return the stable Godot contribution identifier."""
        return GODOT_ENGINE_ID

    async def locate(
        self,
        project: ProjectDescription,
        runtime: PreparedRuntime,
        process_tree: ProcessTree,
        cancellation: Event,
    ) -> NativeWindowSurface:
        """Wait boundedly for the direct player's largest live client area."""
        _validate_request(project, runtime, process_tree, cancellation)
        deadline = self._clock() + self._policy.timeout_seconds
        while True:
            _require_not_cancelled(cancellation)
            exit_code = await asyncio.to_thread(process_tree.poll)
            if exit_code is not None:
                raise GameWindowNotFoundError(
                    details={"reason": "process_exited", "exit_code": exit_code}
                )
            candidates = await self._candidates(process_tree.root_pid)
            if candidates:
                selected = max(candidates, key=_candidate_order)
                if await asyncio.to_thread(process_tree.poll) is None:
                    return NativeWindowSurface(
                        window=selected.window,
                        viewport_size=selected.client_size,
                    )
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise GameWindowNotFoundError(
                    details={"reason": "deadline_exceeded", "retryable": True},
                    parameters={"timeout_seconds": self._policy.timeout_seconds},
                )
            await self._delay(min(self._policy.poll_seconds, remaining))

    async def _candidates(self, process_id: int) -> tuple[NativeWindowCandidate, ...]:
        """Translate unexpected platform failures once at the engine boundary."""
        try:
            return await asyncio.to_thread(self._discovery.for_process, process_id)
        except ToqraqError:
            raise
        except Exception as exc:
            raise PlatformOperationError(
                parameters={"operation": "discover_game_window"},
                details={"reason": "native_call_failed"},
                cause=exc,
            ) from exc


def _validate_request(
    project: ProjectDescription,
    runtime: PreparedRuntime,
    process_tree: ProcessTree,
    cancellation: Event,
) -> None:
    """Reject cross-engine and non-owned values before polling native state."""
    if not isinstance(project, ProjectDescription) or project.engine_id != GODOT_ENGINE_ID:
        raise ValueError("Godot preview project is invalid")
    if (
        not isinstance(runtime, PreparedRuntime)
        or runtime.release.identity.engine_id != GODOT_ENGINE_ID
    ):
        raise ValueError("Godot preview runtime is invalid")
    if not isinstance(process_tree, ProcessTree):
        raise ValueError("Godot preview process tree is invalid")
    if not isinstance(cancellation, Event):
        raise ValueError("Godot preview cancellation owner is invalid")


def _require_not_cancelled(cancellation: Event) -> None:
    """Stop preview discovery at the pending start's cancellation boundary."""
    if cancellation.is_set():
        raise RequestCancelledError(details={"reason": "preview_cancelled"})


def _candidate_order(candidate: NativeWindowCandidate) -> tuple[int, int]:
    """Choose largest area and then the lowest stable native reference."""
    return candidate.area, -candidate.window.value
