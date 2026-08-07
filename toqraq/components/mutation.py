"""Single cross-process mutation ownership for an exact component identity."""

from __future__ import annotations

from enum import StrEnum
from threading import Event
from types import TracebackType

from .identity import component_identity_key
from .layout import ComponentStoreLayout
from .lock import ComponentFileLock, ComponentLockPolicy
from .release import ComponentIdentity


class ComponentMutationRejection(StrEnum):
    """Stable reasons a mutation token cannot authorize an operation."""

    CLOSED = "closed"
    IDENTITY_MISMATCH = "identity_mismatch"


class ComponentMutationRejectedError(RuntimeError):
    """A component operation received invalid mutation ownership."""

    def __init__(self, reason: ComponentMutationRejection) -> None:
        """Retain one stable ownership failure."""
        self.reason = reason
        super().__init__(f"component mutation rejected: {reason.value}")


class ComponentMutation:
    """Exclusive acquired mutation ownership for one complete identity."""

    def __init__(self, identity_key: str, lock: ComponentFileLock) -> None:
        """Bind an already-acquired lock to its opaque identity key."""
        self._identity_key = identity_key
        self._lock: ComponentFileLock | None = lock

    def require(self, identity: ComponentIdentity) -> None:
        """Prove this live owner covers the requested exact identity."""
        if self._lock is None:
            raise ComponentMutationRejectedError(ComponentMutationRejection.CLOSED)
        if component_identity_key(identity) != self._identity_key:
            raise ComponentMutationRejectedError(ComponentMutationRejection.IDENTITY_MISMATCH)

    def close(self) -> None:
        """Release ownership idempotently."""
        lock = self._lock
        if lock is None:
            return
        lock.release()
        self._lock = None

    def __enter__(self) -> ComponentMutation:
        """Return this already-acquired owner."""
        return self

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Release ownership after the complete mutation transaction."""
        self.close()


class ComponentMutationOwner:
    """Factory that acquires the one mutation lock for an exact identity."""

    def __init__(
        self,
        layout: ComponentStoreLayout,
        lock_policy: ComponentLockPolicy,
    ) -> None:
        """Bind the authoritative store layout and wait policy."""
        self._layout = layout
        self._lock_policy = lock_policy

    def acquire(
        self,
        identity: ComponentIdentity,
        *,
        cancellation: Event | None = None,
    ) -> ComponentMutation:
        """Acquire and return exclusive ownership or propagate bounded failure."""
        identity_key = component_identity_key(identity)
        lock = ComponentFileLock(
            self._layout.lock_path(identity),
            self._lock_policy,
            cancellation=cancellation,
        )
        lock.acquire()
        return ComponentMutation(identity_key, lock)
