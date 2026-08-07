"""Cross-platform typing boundary for private component files."""

from __future__ import annotations

import importlib
import os
from typing import Protocol, cast

_PRIVATE_FILE_MODE = 0o600
_PRIVATE_EXECUTABLE_MODE = 0o700


class _PosixOsModule(Protocol):
    """POSIX descriptor operations absent from Windows typing stubs."""

    def fchmod(self, descriptor: int, mode: int) -> None:
        """Apply permissions to an open file descriptor."""
        ...


def restrict_component_file(descriptor: int) -> None:
    """Restrict an owned open file when the host exposes POSIX modes."""
    if os.name == "nt":
        return
    _set_posix_mode(descriptor, _PRIVATE_FILE_MODE)


def make_component_file_executable(descriptor: int) -> None:
    """Grant execution only to the owner of an owned open file."""
    if os.name == "nt":
        return
    _set_posix_mode(descriptor, _PRIVATE_EXECUTABLE_MODE)


def _set_posix_mode(descriptor: int, mode: int) -> None:
    """Apply one exact POSIX mode through the dynamically typed OS boundary."""
    posix_os = cast(_PosixOsModule, importlib.import_module("os"))
    posix_os.fchmod(descriptor, mode)
