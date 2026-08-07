"""Idempotent single-owner wrappers for native process resources."""

from __future__ import annotations

from typing import Protocol

from .process_types import NativeHandle


class HandleCloser(Protocol):
    """One operation required by a native handle owner."""

    def close_handle(self, handle: NativeHandle) -> None:
        """Close one exact native handle."""
        ...


class OwnedHandle:
    """Retain one handle until its native close succeeds."""

    __slots__ = ("_closer", "_value")

    def __init__(self, closer: HandleCloser, value: NativeHandle) -> None:
        """Receive one live handle and its exact release boundary."""
        if isinstance(value, bool) or value <= 0:
            raise ValueError("native handle is invalid")
        self._closer = closer
        self._value: NativeHandle | None = value

    @property
    def value(self) -> NativeHandle:
        """Return the live handle or reject use after release."""
        if self._value is None:
            raise RuntimeError("native handle is already closed")
        return self._value

    @property
    def closed(self) -> bool:
        """Return whether native close has succeeded."""
        return self._value is None

    def close(self) -> None:
        """Close once and retain ownership when the native call fails."""
        if self._value is None:
            return
        self._closer.close_handle(self._value)
        self._value = None
