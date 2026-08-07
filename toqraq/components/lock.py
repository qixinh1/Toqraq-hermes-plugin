"""Bounded cross-process mutation lock for one component identity."""

from __future__ import annotations

import errno
import importlib
import math
import os
import stat
import time
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Event
from types import TracebackType
from typing import Protocol, cast

from .file_mode import restrict_component_file
from .paths import is_link_or_reparse


class _FcntlModule(Protocol):
    """POSIX lock surface loaded only on hosts that provide it."""

    LOCK_EX: int
    LOCK_NB: int
    LOCK_UN: int

    def flock(self, descriptor: int, operation: int) -> None:
        """Apply one advisory descriptor lock operation."""
        ...


class ComponentLockTimeoutError(TimeoutError):
    """Another process retained a component mutation lock past its deadline."""


class ComponentLockCancelledError(Exception):
    """The owner cancelled while waiting for a component mutation lock."""


class ComponentLockFileError(ValueError):
    """The managed lock file is redirected, linked, or malformed."""


class ComponentLockFileMode(StrEnum):
    """Whether a lock may initialize its owned file or only inspect one."""

    CREATE_OR_OPEN = "create_or_open"
    EXISTING = "existing"


@dataclass(frozen=True, slots=True)
class ComponentLockPolicy:
    """Owned wait bounds for cross-process component mutation."""

    timeout_seconds: float
    poll_seconds: float

    def __post_init__(self) -> None:
        """Reject non-finite or unusable timing policy."""
        values = (self.timeout_seconds, self.poll_seconds)
        if any(
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            or value <= 0
            for value in values
        ):
            raise ValueError("component lock timing values must be finite and positive")
        if self.poll_seconds > self.timeout_seconds:
            raise ValueError("component lock polling must not exceed its timeout")


class ComponentFileLock:
    """One reusable idempotent owner of an advisory OS file lock."""

    def __init__(
        self,
        path: Path,
        policy: ComponentLockPolicy,
        *,
        cancellation: Event | None = None,
        file_mode: ComponentLockFileMode = ComponentLockFileMode.CREATE_OR_OPEN,
    ) -> None:
        """Bind an exact lock path, timing policy, and optional cancellation."""
        self._path = path
        self._policy = policy
        self._cancellation = cancellation
        self._file_mode = file_mode
        self._descriptor: int | None = None
        self._locked = False

    def acquire(self) -> ComponentFileLock:
        """Acquire the lock or fail on cancellation, timeout, or unsafe storage."""
        if self._descriptor is not None:
            raise RuntimeError("component lock is already acquired")
        descriptor = _open_lock_file(self._path, self._file_mode)
        deadline = time.monotonic() + self._policy.timeout_seconds
        try:
            while True:
                if self._cancellation is not None and self._cancellation.is_set():
                    raise ComponentLockCancelledError
                try:
                    _try_lock(descriptor)
                except OSError as exc:
                    if not _is_lock_contention(exc):
                        raise
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ComponentLockTimeoutError from exc
                    time.sleep(min(self._policy.poll_seconds, remaining))
                    continue
                self._descriptor = descriptor
                self._locked = True
                return self
        except BaseException:
            with suppress(OSError):
                os.close(descriptor)
            raise

    def try_acquire(self) -> bool:
        """Attempt acquisition once without waiting for another owner."""
        if self._descriptor is not None:
            raise RuntimeError("component lock is already acquired")
        if self._cancellation is not None and self._cancellation.is_set():
            raise ComponentLockCancelledError
        descriptor = _open_lock_file(self._path, self._file_mode)
        try:
            _try_lock(descriptor)
        except OSError as exc:
            with suppress(OSError):
                os.close(descriptor)
            if _is_lock_contention(exc):
                return False
            raise
        self._descriptor = descriptor
        self._locked = True
        return True

    def release(self) -> None:
        """Release ownership idempotently and always close its descriptor."""
        descriptor = self._descriptor
        if descriptor is None:
            return
        if self._locked:
            _unlock(descriptor)
            self._locked = False
        try:
            os.close(descriptor)
        except OSError:
            raise
        self._descriptor = None

    def __enter__(self) -> ComponentFileLock:
        """Acquire this lock for a synchronous ownership transaction."""
        return self.acquire()

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Release this lock after the transaction."""
        self.release()


def _open_lock_file(path: Path, mode: ComponentLockFileMode) -> int:
    """Open or initialize one private one-byte regular lock file."""
    flags = os.O_RDWR
    if mode is ComponentLockFileMode.CREATE_OR_OPEN:
        flags |= os.O_CREAT
    flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        descriptor_info = os.fstat(descriptor)
        path_info = os.lstat(path)
        if (
            not stat.S_ISREG(descriptor_info.st_mode)
            or descriptor_info.st_nlink != 1
            or is_link_or_reparse(path_info)
            or (descriptor_info.st_dev, descriptor_info.st_ino)
            != (path_info.st_dev, path_info.st_ino)
            or descriptor_info.st_size not in {0, 1}
        ):
            raise ComponentLockFileError("component lock file is not privately owned")
        if descriptor_info.st_size == 0:
            os.write(descriptor, b"\0")
            os.fsync(descriptor)
        restrict_component_file(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _try_lock(descriptor: int) -> None:
    """Attempt one non-blocking exclusive native lock."""
    os.lseek(descriptor, 0, os.SEEK_SET)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        return
    fcntl = cast(_FcntlModule, importlib.import_module("fcntl"))
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(descriptor: int) -> None:
    """Release one acquired native lock."""
    os.lseek(descriptor, 0, os.SEEK_SET)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        return
    fcntl = cast(_FcntlModule, importlib.import_module("fcntl"))
    fcntl.flock(descriptor, fcntl.LOCK_UN)


def _is_lock_contention(error: OSError) -> bool:
    """Return whether a native error means another owner holds the byte."""
    return error.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK} or getattr(
        error, "winerror", None
    ) in {33, 36}
