"""Pure values and ports for an owned engine process tree."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable

MAX_PROCESS_ENVIRONMENT_VARIABLES = 64
MAX_PROCESS_ENVIRONMENT_NAME_CHARACTERS = 128
MAX_PROCESS_ENVIRONMENT_VALUE_CHARACTERS = 4 * 1024
MAX_PROCESS_BOOTSTRAP_BYTES = 4 * 1024
_PROCESS_ENVIRONMENT_NAME = re.compile(r"[A-Z_][A-Z0-9_]*\Z")


class ProcessOutputStream(StrEnum):
    """Closed set of process output streams captured by a launcher."""

    STDOUT = "stdout"
    STDERR = "stderr"


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcessEnvironmentVariable:
    """One reviewed non-secret value supplied to a managed child process."""

    name: str
    value: str

    def __post_init__(self) -> None:
        """Keep environment names portable, deterministic, and bounded."""
        if (
            not isinstance(self.name, str)
            or len(self.name) > MAX_PROCESS_ENVIRONMENT_NAME_CHARACTERS
            or _PROCESS_ENVIRONMENT_NAME.fullmatch(self.name) is None
        ):
            raise ValueError("process environment variable name is invalid")
        if (
            not isinstance(self.value, str)
            or len(self.value) > MAX_PROCESS_ENVIRONMENT_VALUE_CHARACTERS
            or "\0" in self.value
        ):
            raise ValueError("process environment variable value is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcessEnvironment:
    """Explicit immutable child environment that never implies parent inheritance."""

    variables: tuple[ProcessEnvironmentVariable, ...]

    def __post_init__(self) -> None:
        """Reject mutable, oversized, untyped, or duplicate collections."""
        if (
            not isinstance(self.variables, tuple)
            or len(self.variables) > MAX_PROCESS_ENVIRONMENT_VARIABLES
            or any(
                not isinstance(variable, ProcessEnvironmentVariable) for variable in self.variables
            )
        ):
            raise ValueError("process environment collection is invalid")
        names = tuple(variable.name.casefold() for variable in self.variables)
        if len(set(names)) != len(names):
            raise ValueError("process environment variable name is duplicated")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcessBootstrap:
    """Bounded one-launch data delivered through the child's standard input."""

    payload: bytes = field(repr=False)

    def __post_init__(self) -> None:
        """Require an immutable non-empty value small enough for one pipe write."""
        if (
            not isinstance(self.payload, bytes)
            or not self.payload
            or len(self.payload) > MAX_PROCESS_BOOTSTRAP_BYTES
        ):
            raise ValueError("process bootstrap payload is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcessLaunch:
    """One exact executable invocation with no command-shell interpretation."""

    executable: Path
    arguments: tuple[str, ...]
    working_directory: Path
    environment: ProcessEnvironment
    bootstrap: ProcessBootstrap

    def __post_init__(self) -> None:
        """Reject relative paths, shell text, and invalid native strings."""
        _require_absolute_normalized_path(self.executable, "executable")
        _require_absolute_normalized_path(self.working_directory, "working directory")
        if not isinstance(self.arguments, tuple):
            raise ValueError("process arguments must be a tuple")
        if any(not isinstance(argument, str) or "\0" in argument for argument in self.arguments):
            raise ValueError("process argument is invalid")
        if not isinstance(self.environment, ProcessEnvironment):
            raise ValueError("process environment is invalid")
        if not isinstance(self.bootstrap, ProcessBootstrap):
            raise ValueError("process bootstrap is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcessOutputChunk:
    """One globally sequenced piece of decoded process output."""

    sequence: int
    stream: ProcessOutputStream
    text: str

    def __post_init__(self) -> None:
        """Reject values that cannot be a captured output record."""
        if isinstance(self.sequence, bool) or self.sequence < 1:
            raise ValueError("process output sequence is invalid")
        if not isinstance(self.stream, ProcessOutputStream):
            raise ValueError("process output stream is invalid")
        if not isinstance(self.text, str) or not self.text:
            raise ValueError("process output text is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcessOutputSnapshot:
    """Bounded output tail and its loss or collection state."""

    chunks: tuple[ProcessOutputChunk, ...]
    next_sequence: int
    truncated: bool
    failed_streams: frozenset[ProcessOutputStream]

    def __post_init__(self) -> None:
        """Require a strictly ordered immutable snapshot."""
        sequences = tuple(chunk.sequence for chunk in self.chunks)
        if sequences != tuple(sorted(set(sequences))):
            raise ValueError("process output chunks are not strictly sequenced")
        if isinstance(self.next_sequence, bool) or self.next_sequence < 1:
            raise ValueError("process output next sequence is invalid")
        if sequences and sequences[-1] >= self.next_sequence:
            raise ValueError("process output cursor does not follow its chunks")
        if any(not isinstance(stream, ProcessOutputStream) for stream in self.failed_streams):
            raise ValueError("process output failed stream is invalid")


@runtime_checkable
class ProcessTree(Protocol):
    """Owned process tree with bounded observation and shutdown."""

    @property
    def root_pid(self) -> int:
        """Return the operating-system ID of the root process."""
        ...

    def poll(self) -> int | None:
        """Return the root exit code once the complete tree has ended."""
        ...

    def wait(self, timeout: float) -> int:
        """Wait a bounded duration for the complete tree to end."""
        ...

    def output(self) -> ProcessOutputSnapshot:
        """Return the bounded sequenced stdout and stderr tail."""
        ...

    def close(self, *, graceful_timeout: float, forced_timeout: float) -> None:
        """Stop the complete tree within two bounds and release ownership."""
        ...


@runtime_checkable
class ProcessTreeLauncher(Protocol):
    """Platform boundary that atomically starts and owns failed launch cleanup."""

    def launch(self, command: ProcessLaunch) -> ProcessTree:
        """Launch one exact executable invocation without a command shell."""
        ...

    def close(self) -> None:
        """Release active trees, launch transactions, and platform guardians."""
        ...


def _require_absolute_normalized_path(value: Path, label: str) -> None:
    """Require one lexical absolute path without touching the filesystem."""
    if (
        not isinstance(value, Path)
        or "\0" in str(value)
        or not value.is_absolute()
        or value != Path(os.path.abspath(value))
    ):
        raise ValueError(f"process {label} must be absolute and normalized")
