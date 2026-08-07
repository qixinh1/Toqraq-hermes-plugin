"""Thread-safe state owner for one asynchronous component operation."""

from __future__ import annotations

import threading
from types import MappingProxyType

from ..contracts.components import ComponentJobResult, ComponentJobState
from ..contracts.errors import PublicError
from ..core.component import (
    ComponentJobAction,
    ComponentWorkPhase,
    ComponentWorkProgress,
    ManagedComponent,
)

_PREPARE_PHASE_ORDER = MappingProxyType(
    {
        ComponentWorkPhase.CHECKING: 0,
        ComponentWorkPhase.DOWNLOADING: 1,
        ComponentWorkPhase.INSTALLING: 2,
        ComponentWorkPhase.VERIFYING: 3,
        ComponentWorkPhase.READY: 4,
    }
)
_REMOVE_PHASE_ORDER = MappingProxyType(
    {
        ComponentWorkPhase.CHECKING: 0,
        ComponentWorkPhase.REMOVING: 1,
        ComponentWorkPhase.READY: 2,
    }
)
_TERMINAL_STATES = frozenset(
    {
        ComponentJobState.READY,
        ComponentJobState.FAILED,
        ComponentJobState.CANCELLED,
    }
)


class ComponentJob:
    """Own cancellation, revisions, transitions, and snapshots for one job."""

    def __init__(
        self,
        operation_id: str,
        component: ManagedComponent,
        action: ComponentJobAction,
    ) -> None:
        """Create one queued job with a fresh cancellation owner."""
        self.operation_id = operation_id
        self.component = component
        self.action = action
        self.cancellation = threading.Event()
        self._lock = threading.RLock()
        self._state = ComponentJobState.QUEUED
        self._phase = ComponentWorkPhase.CHECKING
        self._completed_bytes = 0
        self._total_bytes = 0
        self._revision = 1
        self._error: PublicError | None = None

    @property
    def terminal(self) -> bool:
        """Return whether the worker has reached an immutable outcome."""
        with self._lock:
            return self._state in _TERMINAL_STATES

    def mark_running(self) -> None:
        """Move a queued job to running unless cancellation is already requested."""
        with self._lock:
            if self._state is ComponentJobState.QUEUED:
                self._state = ComponentJobState.RUNNING
                self._revision += 1

    def update(self, value: ComponentWorkProgress) -> None:
        """Apply monotonic adapter progress while preserving cancelling state."""
        with self._lock:
            if self._state in _TERMINAL_STATES:
                return
            if value.phase is ComponentWorkPhase.READY:
                return
            order = (
                _PREPARE_PHASE_ORDER
                if self.action is ComponentJobAction.PREPARE
                else _REMOVE_PHASE_ORDER
            )
            if value.phase not in order or order[value.phase] < order[self._phase]:
                raise ValueError("component job phase moved outside its action order")
            if value.phase is self._phase and value.completed_bytes < self._completed_bytes:
                raise ValueError("component job byte progress moved backwards")
            self._phase = value.phase
            self._completed_bytes = value.completed_bytes
            self._total_bytes = value.total_bytes
            self._revision += 1

    def request_cancellation(self) -> bool:
        """Signal cancellation once and expose a cancelling snapshot."""
        with self._lock:
            if self._state in _TERMINAL_STATES:
                return False
            self.cancellation.set()
            if self._state is not ComponentJobState.CANCELLING:
                self._state = ComponentJobState.CANCELLING
                self._revision += 1
            return True

    def mark_ready(self) -> None:
        """Record successful completion, including a post-cancellation commit."""
        with self._lock:
            if self._state in _TERMINAL_STATES:
                return
            total = (
                self.component.installed_bytes if self.action is ComponentJobAction.PREPARE else 0
            )
            self._state = ComponentJobState.READY
            self._phase = ComponentWorkPhase.READY
            self._completed_bytes = total
            self._total_bytes = total
            self._revision += 1

    def mark_cancelled(self) -> None:
        """Record cooperative cancellation before the adapter commit point."""
        with self._lock:
            if self._state in _TERMINAL_STATES:
                return
            self._state = ComponentJobState.CANCELLED
            self._revision += 1

    def mark_failed(self, error: PublicError) -> None:
        """Record one safe application error as the terminal outcome."""
        with self._lock:
            if self._state in _TERMINAL_STATES:
                return
            self._state = ComponentJobState.FAILED
            self._error = error
            self._revision += 1

    def snapshot(self) -> ComponentJobResult:
        """Return an immutable consistent public snapshot."""
        with self._lock:
            return ComponentJobResult(
                operation_id=self.operation_id,
                release_id=self.component.release_id,
                component_id=self.component.component_id,
                action=self.action,
                state=self._state,
                phase=self._phase,
                completed_bytes=self._completed_bytes,
                total_bytes=self._total_bytes,
                revision=self._revision,
                error=self._error,
            )
