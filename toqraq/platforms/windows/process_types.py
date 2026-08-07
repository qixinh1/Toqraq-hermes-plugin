"""Small immutable values exchanged by Windows process primitives."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...core.process_tree import ProcessEnvironment

NativeHandle = int
NativeWindow = int


@dataclass(frozen=True, slots=True)
class NativeCommand:
    """Trusted internal process invocation without a bootstrap channel."""

    executable: Path
    arguments: tuple[str, ...]
    working_directory: Path
    environment: ProcessEnvironment


@dataclass(frozen=True, slots=True)
class NativePipe:
    """Two non-inheritable handles for one anonymous pipe."""

    read: NativeHandle
    write: NativeHandle


@dataclass(frozen=True, slots=True)
class NativeProcess:
    """Non-inheritable process and initial-thread handles."""

    process: NativeHandle
    thread: NativeHandle
    pid: int
