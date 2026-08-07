"""Bounded extraction for managed ZIP component packages."""

from __future__ import annotations

import os
import stat
import zipfile
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PureWindowsPath
from threading import Event
from typing import IO

from .content_policy import ComponentContentPolicy
from .paths import (
    ComponentPathConflict,
    ComponentPathConflictError,
    ComponentPathNamespace,
    is_link_or_reparse,
    is_portable_component_part,
)

_ENCRYPTED_FLAG = 1


class ArchiveRejection(StrEnum):
    """Stable reasons why a component archive is unsafe."""

    DESTINATION_INVALID = "destination_invalid"
    DESTINATION_NOT_EMPTY = "destination_not_empty"
    TOO_MANY_ENTRIES = "too_many_entries"
    INVALID_PATH = "invalid_path"
    PATH_TOO_LONG = "path_too_long"
    PATH_TOO_DEEP = "path_too_deep"
    NON_PORTABLE_PATH = "non_portable_path"
    DUPLICATE_PATH = "duplicate_path"
    PATH_TYPE_CONFLICT = "path_type_conflict"
    ENCRYPTED_ENTRY = "encrypted_entry"
    SPECIAL_FILE = "special_file"
    ENTRY_TOO_LARGE = "entry_too_large"
    ARCHIVE_TOO_LARGE = "archive_too_large"
    ENTRY_SIZE_MISMATCH = "entry_size_mismatch"
    DESTINATION_REDIRECTED = "destination_redirected"


class ArchiveRejectedError(ValueError):
    """A component archive violated a stable extraction policy."""

    def __init__(self, reason: ArchiveRejection) -> None:
        """Retain the stable reason without including untrusted member text."""
        self.reason = reason
        super().__init__(f"component archive rejected: {reason.value}")


class ArchiveCancelledError(Exception):
    """The owning component operation cancelled archive extraction."""


@dataclass(frozen=True, slots=True)
class ArchiveProgress:
    """Authoritative uncompressed-byte progress for one archive."""

    completed_bytes: int
    total_bytes: int


@dataclass(frozen=True)
class ZipExtractionPolicy:
    """ZIP-specific extraction behavior composed with content-tree limits."""

    content: ComponentContentPolicy
    copy_chunk_bytes: int

    def __post_init__(self) -> None:
        """Reject unusable limits at composition time."""
        if (
            isinstance(self.copy_chunk_bytes, bool)
            or not isinstance(self.copy_chunk_bytes, int)
            or self.copy_chunk_bytes <= 0
        ):
            raise ValueError("ZIP copy chunk size must be a positive integer")


@dataclass(frozen=True)
class _PlannedEntry:
    info: zipfile.ZipInfo
    parts: tuple[str, ...]
    is_directory: bool


def extract_zip(
    archive: zipfile.ZipFile,
    destination: Path,
    policy: ZipExtractionPolicy,
    *,
    cancellation: Event | None = None,
    progress: Callable[[ArchiveProgress], None] | None = None,
) -> None:
    """Extract regular members into one empty, private staging directory.

    Args:
        archive: Open ZIP package.
        destination: Existing empty staging directory owned by the caller.
        policy: Trusted limits selected by the component provider.
        cancellation: Owning operation cancellation signal.
        progress: Optional immutable uncompressed-byte observer.

    Raises:
        ArchiveRejectedError: If the destination or package is unsafe.
        OSError: If filesystem I/O fails.
        zipfile.BadZipFile: If compressed data is corrupt.
    """
    root = _validate_destination(destination)
    planned = _plan_entries(archive.infolist(), policy, cancellation)
    total_bytes = sum(entry.info.file_size for entry in planned)
    completed_bytes = 0
    _notify(progress, completed_bytes, total_bytes)

    for entry in planned:
        _require_not_cancelled(cancellation)
        target = root.joinpath(*entry.parts)
        _prepare_parent_directories(root, entry.parts[:-1])
        if entry.is_directory:
            target.mkdir(exist_ok=True)
            _require_regular_directory(target)
            continue

        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(target, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as output:
                descriptor = -1
                with archive.open(entry.info) as source:
                    copied = _copy_entry(
                        source,
                        output,
                        expected_size=entry.info.file_size,
                        policy=policy,
                        cancellation=cancellation,
                        progress=_entry_observer(
                            progress,
                            completed_bytes,
                            total_bytes,
                        ),
                    )
                    completed_bytes += copied
        finally:
            if descriptor >= 0:
                os.close(descriptor)
    _require_not_cancelled(cancellation)


def _validate_destination(destination: Path) -> Path:
    """Return one existing, empty directory that is not redirected."""
    root = Path(os.path.abspath(destination))
    try:
        info = os.lstat(root)
    except OSError as exc:
        raise ArchiveRejectedError(ArchiveRejection.DESTINATION_INVALID) from exc
    if is_link_or_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise ArchiveRejectedError(ArchiveRejection.DESTINATION_INVALID)
    with os.scandir(root) as entries:
        if next(entries, None) is not None:
            raise ArchiveRejectedError(ArchiveRejection.DESTINATION_NOT_EMPTY)
    return root


def _plan_entries(
    entries: list[zipfile.ZipInfo],
    policy: ZipExtractionPolicy,
    cancellation: Event | None,
) -> tuple[_PlannedEntry, ...]:
    """Validate the complete namespace and size budget before writing."""
    limits = policy.content
    if len(entries) > limits.max_entries:
        raise ArchiveRejectedError(ArchiveRejection.TOO_MANY_ENTRIES)

    namespace = ComponentPathNamespace()
    planned: list[_PlannedEntry] = []
    total_bytes = 0

    for info in entries:
        _require_not_cancelled(cancellation)
        parts, is_directory = _entry_path(info, policy)
        try:
            namespace.add(parts, is_directory=is_directory)
        except ComponentPathConflictError as exc:
            rejection = (
                ArchiveRejection.DUPLICATE_PATH
                if exc.conflict is ComponentPathConflict.DUPLICATE
                else ArchiveRejection.PATH_TYPE_CONFLICT
            )
            raise ArchiveRejectedError(rejection) from exc
        _validate_entry_type(info, is_directory)
        if info.flag_bits & _ENCRYPTED_FLAG:
            raise ArchiveRejectedError(ArchiveRejection.ENCRYPTED_ENTRY)
        if is_directory and info.file_size != 0:
            raise ArchiveRejectedError(ArchiveRejection.ENTRY_SIZE_MISMATCH)
        if info.file_size < 0 or info.file_size > limits.max_file_bytes:
            raise ArchiveRejectedError(ArchiveRejection.ENTRY_TOO_LARGE)
        total_bytes += info.file_size
        if total_bytes > limits.max_total_bytes:
            raise ArchiveRejectedError(ArchiveRejection.ARCHIVE_TOO_LARGE)
        planned.append(_PlannedEntry(info=info, parts=parts, is_directory=is_directory))

    return tuple(planned)


def _entry_path(
    info: zipfile.ZipInfo,
    policy: ZipExtractionPolicy,
) -> tuple[tuple[str, ...], bool]:
    """Return canonical path parts and a cross-platform collision key."""
    raw = info.filename.replace("\\", "/")
    is_directory = info.is_dir()
    if raw.startswith("/") or PureWindowsPath(raw).drive:
        raise ArchiveRejectedError(ArchiveRejection.INVALID_PATH)
    raw_parts = raw.split("/")
    if is_directory and raw_parts and raw_parts[-1] == "":
        raw_parts.pop()
    if not raw_parts or any(part in {"", ".", ".."} for part in raw_parts):
        raise ArchiveRejectedError(ArchiveRejection.INVALID_PATH)
    limits = policy.content
    if len(raw_parts) > limits.max_path_depth:
        raise ArchiveRejectedError(ArchiveRejection.PATH_TOO_DEEP)
    if len("/".join(raw_parts)) > limits.max_path_characters:
        raise ArchiveRejectedError(ArchiveRejection.PATH_TOO_LONG)
    if any(not is_portable_component_part(part) for part in raw_parts):
        raise ArchiveRejectedError(ArchiveRejection.NON_PORTABLE_PATH)

    parts = tuple(raw_parts)
    return parts, is_directory


def _validate_entry_type(info: zipfile.ZipInfo, is_directory: bool) -> None:
    """Reject links, devices, and contradictory directory metadata."""
    mode = info.external_attr >> 16 if info.create_system == 3 else 0
    file_type = stat.S_IFMT(mode)
    if is_directory:
        if file_type not in (0, stat.S_IFDIR):
            raise ArchiveRejectedError(ArchiveRejection.SPECIAL_FILE)
    elif file_type not in (0, stat.S_IFREG):
        raise ArchiveRejectedError(ArchiveRejection.SPECIAL_FILE)


def _prepare_parent_directories(root: Path, parts: tuple[str, ...]) -> None:
    """Create and revalidate every parent below the private staging root."""
    current = root
    for part in parts:
        current /= part
        with suppress(FileExistsError):
            current.mkdir()
        _require_regular_directory(current)


def _require_regular_directory(path: Path) -> None:
    """Reject a directory replaced by a link or reparse point."""
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise ArchiveRejectedError(ArchiveRejection.DESTINATION_REDIRECTED) from exc
    if is_link_or_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise ArchiveRejectedError(ArchiveRejection.DESTINATION_REDIRECTED)


def _copy_entry(
    source: IO[bytes],
    output: IO[bytes],
    *,
    expected_size: int,
    policy: ZipExtractionPolicy,
    cancellation: Event | None = None,
    progress: Callable[[int], None] | None = None,
) -> int:
    """Copy one member while enforcing its declared and policy sizes."""
    copied = 0
    while chunk := source.read(policy.copy_chunk_bytes):
        _require_not_cancelled(cancellation)
        copied += len(chunk)
        if copied > expected_size or copied > policy.content.max_file_bytes:
            raise ArchiveRejectedError(ArchiveRejection.ENTRY_SIZE_MISMATCH)
        output.write(chunk)
        if progress is not None:
            progress(copied)
    if copied != expected_size:
        raise ArchiveRejectedError(ArchiveRejection.ENTRY_SIZE_MISMATCH)
    return copied


def _require_not_cancelled(cancellation: Event | None) -> None:
    """Raise at bounded planning and copy checkpoints after cancellation."""
    if cancellation is not None and cancellation.is_set():
        raise ArchiveCancelledError


def _notify(
    progress: Callable[[ArchiveProgress], None] | None,
    completed: int,
    total: int,
) -> None:
    """Publish one immutable extraction snapshot when observed."""
    if progress is not None:
        progress(ArchiveProgress(completed, total))


def _entry_observer(
    observer: Callable[[ArchiveProgress], None] | None,
    completed_before_entry: int,
    total: int,
) -> Callable[[int], None] | None:
    """Bind global progress for one archive member without a loop closure."""
    if observer is None:
        return None

    def notify(completed_in_entry: int) -> None:
        observer(ArchiveProgress(completed_before_entry + completed_in_entry, total))

    return notify
