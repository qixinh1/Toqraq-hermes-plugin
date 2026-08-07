"""Cross-process leases for exact verified component installations."""

from __future__ import annotations

import logging
import os
import re
import uuid
from pathlib import Path
from threading import Event
from types import TracebackType
from typing import Generic, TypeVar

from .lock import ComponentFileLock, ComponentLockFileMode, ComponentLockPolicy

logger = logging.getLogger(__name__)
_LEASE_ID = re.compile(r"^[0-9a-f]{32}$")
_LEASE_ID_ATTEMPTS = 8
_InstallationT = TypeVar("_InstallationT")


class ComponentLeaseAllocationError(Exception):
    """A unique lease receipt could not be allocated within its bound."""


class ComponentLease(Generic[_InstallationT]):
    """Strong cross-process ownership of one verified installation."""

    def __init__(
        self,
        installation: _InstallationT,
        lock: ComponentFileLock,
        path: Path,
    ) -> None:
        """Own an already-acquired lease lock and its private receipt."""
        self.installation = installation
        self._lock: ComponentFileLock | None = lock
        self._path = path
        self._receipt_released = False

    def close(self) -> None:
        """Release this lease idempotently and expose retryable cleanup failure."""
        lock = self._lock
        if lock is None and self._receipt_released:
            return
        failure: OSError | None = None
        if lock is not None:
            try:
                lock.release()
            except OSError as exc:
                failure = exc
            else:
                self._lock = None
        if failure is None and not self._receipt_released:
            try:
                self._path.unlink(missing_ok=True)
            except OSError as exc:
                failure = failure or exc
            else:
                self._receipt_released = True
        if failure is not None:
            raise failure

    def __enter__(self) -> ComponentLease[_InstallationT]:
        """Return this already-acquired lease."""
        return self

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Release this lease after its runtime owner exits."""
        self.close()


def acquire_component_lease(
    installation: _InstallationT,
    locks_root: Path,
    identity_key: str,
    policy: ComponentLockPolicy,
    *,
    cancellation: Event | None = None,
) -> ComponentLease[_InstallationT]:
    """Allocate and acquire one bounded unique lease receipt."""
    for _ in range(_LEASE_ID_ATTEMPTS):
        lease_id = uuid.uuid4().hex
        path = locks_root / f"{identity_key}.lease.{lease_id}"
        if os.path.lexists(path):
            continue
        lock = ComponentFileLock(path, policy, cancellation=cancellation)
        if lock.try_acquire():
            return ComponentLease(installation, lock, path)
    raise ComponentLeaseAllocationError


def active_component_lease_count(
    locks_root: Path,
    identity_key: str,
    policy: ComponentLockPolicy,
) -> int:
    """Count live leases and reclaim receipts left by terminated owners."""
    prefix = f"{identity_key}.lease."
    active = 0
    with os.scandir(locks_root) as entries:
        names = sorted(entry.name for entry in entries if entry.name.startswith(prefix))
    for name in names:
        lease_id = name.removeprefix(prefix)
        if _LEASE_ID.fullmatch(lease_id) is None:
            continue
        path = locks_root / name
        probe = ComponentFileLock(
            path,
            policy,
            file_mode=ComponentLockFileMode.EXISTING,
        )
        try:
            acquired = probe.try_acquire()
        except FileNotFoundError:
            continue
        if not acquired:
            active += 1
            continue
        probe.release()
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(
                "stale component lease cleanup deferred identity_key=%s exception_type=%s",
                identity_key,
                type(exc).__name__,
            )
    return active
