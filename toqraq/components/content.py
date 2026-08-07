"""Deterministic fingerprinting of staged and published component trees."""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Event
from typing import Protocol

from .content_policy import ComponentContentPolicy
from .paths import (
    ComponentPathConflictError,
    ComponentPathNamespace,
    is_link_or_reparse,
    is_portable_component_part,
)

COMPONENT_MANIFEST_NAME = "component.json"
_TREE_FORMAT = b"toqraq-component-tree-v1\0"


class ComponentTreeRejection(StrEnum):
    """Stable reasons an installed content tree cannot be trusted."""

    ROOT_INVALID = "root_invalid"
    MANIFEST_PRESENT = "manifest_present"
    MANIFEST_MISSING = "manifest_missing"
    TOO_MANY_ENTRIES = "too_many_entries"
    INVALID_PATH = "invalid_path"
    PATH_TOO_LONG = "path_too_long"
    PATH_TOO_DEEP = "path_too_deep"
    PATH_CONFLICT = "path_conflict"
    SPECIAL_FILE = "special_file"
    HARD_LINK = "hard_link"
    FILE_TOO_LARGE = "file_too_large"
    TREE_TOO_LARGE = "tree_too_large"
    FILE_CHANGED = "file_changed"


class ComponentTreeRejectedError(ValueError):
    """A staged or published component tree violated its content policy."""

    def __init__(self, reason: ComponentTreeRejection) -> None:
        """Retain the stable reason without exposing an installed path."""
        self.reason = reason
        super().__init__(f"component tree rejected: {reason.value}")


class ComponentTreeCancelledError(Exception):
    """The owning component operation cancelled content verification."""


@dataclass(frozen=True, slots=True)
class ComponentTreeProgress:
    """Exact verified-byte progress for one bounded component tree."""

    completed_bytes: int
    total_bytes: int

    def __post_init__(self) -> None:
        """Reject impossible progress snapshots at their source."""
        if (
            isinstance(self.completed_bytes, bool)
            or not isinstance(self.completed_bytes, int)
            or isinstance(self.total_bytes, bool)
            or not isinstance(self.total_bytes, int)
        ):
            raise ValueError("component tree progress bytes must be integers")
        if not 0 <= self.completed_bytes <= self.total_bytes:
            raise ValueError("component tree progress bytes are outside their total")


@dataclass(frozen=True, slots=True)
class ComponentFileFingerprint:
    """Content identity of one regular file relative to a component root."""

    relative_path: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ComponentTreeFingerprint:
    """Canonical immutable content manifest and its aggregate digest."""

    files: tuple[ComponentFileFingerprint, ...]
    total_bytes: int
    tree_sha256: str


@dataclass(frozen=True, slots=True)
class _PlannedFile:
    """Stable file identity captured before content hashing begins."""

    path: Path
    relative_path: str
    identity: tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class _PlannedDirectory:
    """One checked directory that remains to be scanned without following it."""

    path: Path
    parts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _TreePlan:
    """Complete checked file plan captured before any file descriptor is opened."""

    files: tuple[_PlannedFile, ...]
    total_bytes: int


class ComponentFileValue(Protocol):
    """Structural fields consumed by the canonical tree-digest algorithm."""

    @property
    def relative_path(self) -> str:
        """Return the canonical relative path."""
        ...

    @property
    def size(self) -> int:
        """Return the exact file length."""
        ...

    @property
    def sha256(self) -> str:
        """Return the exact lowercase content digest."""
        ...


def fingerprint_staging_tree(
    root: Path,
    policy: ComponentContentPolicy,
    *,
    cancellation: Event | None = None,
    progress: Callable[[ComponentTreeProgress], None] | None = None,
) -> ComponentTreeFingerprint:
    """Fingerprint staging and require the generated manifest to be absent."""
    return _fingerprint_tree(
        root,
        policy,
        published=False,
        cancellation=cancellation,
        progress=progress,
    )


def fingerprint_published_tree(
    root: Path,
    policy: ComponentContentPolicy,
    *,
    cancellation: Event | None = None,
    progress: Callable[[ComponentTreeProgress], None] | None = None,
) -> ComponentTreeFingerprint:
    """Fingerprint published content while excluding its required manifest."""
    return _fingerprint_tree(
        root,
        policy,
        published=True,
        cancellation=cancellation,
        progress=progress,
    )


def _fingerprint_tree(
    root: Path,
    policy: ComponentContentPolicy,
    *,
    published: bool,
    cancellation: Event | None,
    progress: Callable[[ComponentTreeProgress], None] | None,
) -> ComponentTreeFingerprint:
    """Walk one owned tree without following redirected filesystem objects."""
    _require_not_cancelled(cancellation)
    plan = _plan_tree(_tree_root(root), policy, published=published, cancellation=cancellation)
    return _fingerprint_plan(plan, policy, cancellation=cancellation, progress=progress)


def _tree_root(root: Path) -> Path:
    absolute = Path(os.path.abspath(root))
    try:
        root_info = os.lstat(absolute)
    except OSError as exc:
        raise ComponentTreeRejectedError(ComponentTreeRejection.ROOT_INVALID) from exc
    if is_link_or_reparse(root_info) or not stat.S_ISDIR(root_info.st_mode):
        raise ComponentTreeRejectedError(ComponentTreeRejection.ROOT_INVALID)
    return absolute


def _plan_tree(
    root: Path,
    policy: ComponentContentPolicy,
    *,
    published: bool,
    cancellation: Event | None,
) -> _TreePlan:
    namespace = ComponentPathNamespace()
    namespace.add((COMPONENT_MANIFEST_NAME,), is_directory=False)
    manifest_found = False
    entry_count = 0
    total_bytes = 0
    files: list[_PlannedFile] = []
    pending = [_PlannedDirectory(root, ())]

    while pending:
        _require_not_cancelled(cancellation)
        directory = pending.pop()
        for name in _directory_names(directory.path, cancellation):
            _require_not_cancelled(cancellation)
            item, entry_count = _plan_entry(
                directory.path / name,
                (*directory.parts, name),
                policy,
                published=published,
                namespace=namespace,
                entry_count=entry_count,
            )
            if item is None:
                manifest_found = True
                continue
            if isinstance(item, _PlannedDirectory):
                pending.append(item)
                continue
            total_bytes = _next_total_bytes(total_bytes, item, policy)
            files.append(item)

    if published and not manifest_found:
        raise ComponentTreeRejectedError(ComponentTreeRejection.MANIFEST_MISSING)
    files.sort(key=lambda item: item.relative_path.encode("utf-8"))
    return _TreePlan(files=tuple(files), total_bytes=total_bytes)


def _directory_names(directory: Path, cancellation: Event | None) -> tuple[str, ...]:
    try:
        with os.scandir(directory) as iterator:
            names = []
            for entry in iterator:
                _require_not_cancelled(cancellation)
                names.append(entry.name)
            names.sort(key=lambda name: name.encode())
    except (OSError, UnicodeError) as exc:
        raise ComponentTreeRejectedError(ComponentTreeRejection.FILE_CHANGED) from exc
    return tuple(names)


def _plan_entry(
    path: Path,
    parts: tuple[str, ...],
    policy: ComponentContentPolicy,
    *,
    published: bool,
    namespace: ComponentPathNamespace,
    entry_count: int,
) -> tuple[_PlannedDirectory | _PlannedFile | None, int]:
    _validate_relative_path(parts, policy)
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise ComponentTreeRejectedError(ComponentTreeRejection.FILE_CHANGED) from exc
    if _is_root_manifest(parts):
        _validate_manifest(parts[0], info, published)
        return None, entry_count
    next_entry_count = _next_entry_count(entry_count, policy)
    is_directory = stat.S_ISDIR(info.st_mode) and not is_link_or_reparse(info)
    try:
        namespace.add(parts, is_directory=is_directory)
    except ComponentPathConflictError as exc:
        raise ComponentTreeRejectedError(ComponentTreeRejection.PATH_CONFLICT) from exc
    if is_directory:
        return _PlannedDirectory(path=path, parts=parts), next_entry_count
    _require_owned_regular_file(info)
    if info.st_size < 0 or info.st_size > policy.max_file_bytes:
        raise ComponentTreeRejectedError(ComponentTreeRejection.FILE_TOO_LARGE)
    return (
        _PlannedFile(
            path=path,
            relative_path="/".join(parts),
            identity=_file_identity(info),
        ),
        next_entry_count,
    )


def _is_root_manifest(parts: tuple[str, ...]) -> bool:
    return len(parts) == 1 and parts[0].casefold() == COMPONENT_MANIFEST_NAME


def _validate_manifest(name: str, info: os.stat_result, published: bool) -> None:
    if not published:
        raise ComponentTreeRejectedError(ComponentTreeRejection.MANIFEST_PRESENT)
    if name != COMPONENT_MANIFEST_NAME or not _is_owned_regular_file(info):
        raise ComponentTreeRejectedError(ComponentTreeRejection.SPECIAL_FILE)


def _require_owned_regular_file(info: os.stat_result) -> None:
    if _is_owned_regular_file(info):
        return
    reason = (
        ComponentTreeRejection.HARD_LINK
        if stat.S_ISREG(info.st_mode) and info.st_nlink != 1
        else ComponentTreeRejection.SPECIAL_FILE
    )
    raise ComponentTreeRejectedError(reason)


def _next_entry_count(entry_count: int, policy: ComponentContentPolicy) -> int:
    next_count = entry_count + 1
    if next_count > policy.max_entries:
        raise ComponentTreeRejectedError(ComponentTreeRejection.TOO_MANY_ENTRIES)
    return next_count


def _next_total_bytes(
    total_bytes: int,
    file: _PlannedFile,
    policy: ComponentContentPolicy,
) -> int:
    next_total = total_bytes + file.identity[2]
    if next_total > policy.max_total_bytes:
        raise ComponentTreeRejectedError(ComponentTreeRejection.TREE_TOO_LARGE)
    return next_total


def _fingerprint_plan(
    plan: _TreePlan,
    policy: ComponentContentPolicy,
    *,
    cancellation: Event | None,
    progress: Callable[[ComponentTreeProgress], None] | None,
) -> ComponentTreeFingerprint:
    completed_bytes = 0
    files: list[ComponentFileFingerprint] = []
    _notify(progress, completed_bytes, plan.total_bytes)
    for item in plan.files:
        _require_not_cancelled(cancellation)
        fingerprint = _fingerprint_file(
            item.path,
            item.relative_path,
            item.identity,
            policy,
            cancellation,
            _file_observer(progress, completed_bytes, plan.total_bytes),
        )
        completed_bytes += fingerprint.size
        files.append(fingerprint)
    _require_not_cancelled(cancellation)
    ordered = tuple(files)
    return ComponentTreeFingerprint(
        files=ordered,
        total_bytes=plan.total_bytes,
        tree_sha256=component_tree_digest(ordered, cancellation=cancellation),
    )


def _validate_relative_path(
    parts: tuple[str, ...],
    policy: ComponentContentPolicy,
) -> None:
    """Apply the extraction namespace limits again during verification."""
    if not parts or any(not is_portable_component_part(part) for part in parts):
        raise ComponentTreeRejectedError(ComponentTreeRejection.INVALID_PATH)
    if len(parts) > policy.max_path_depth:
        raise ComponentTreeRejectedError(ComponentTreeRejection.PATH_TOO_DEEP)
    if len("/".join(parts)) > policy.max_path_characters:
        raise ComponentTreeRejectedError(ComponentTreeRejection.PATH_TOO_LONG)


def _is_owned_regular_file(info: os.stat_result) -> bool:
    """Return whether a file is regular, unredirected, and not hard-linked."""
    return stat.S_ISREG(info.st_mode) and not is_link_or_reparse(info) and info.st_nlink == 1


def _fingerprint_file(
    path: Path,
    relative_path: str,
    expected_identity: tuple[int, int, int, int],
    policy: ComponentContentPolicy,
    cancellation: Event | None,
    progress: Callable[[int], None] | None,
) -> ComponentFileFingerprint:
    """Hash one stable regular file through an owned descriptor."""
    _require_not_cancelled(cancellation)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ComponentTreeRejectedError(ComponentTreeRejection.FILE_CHANGED) from exc
    try:
        before = os.fstat(descriptor)
        if not _is_owned_regular_file(before):
            raise ComponentTreeRejectedError(ComponentTreeRejection.SPECIAL_FILE)
        if _file_identity(before) != expected_identity:
            raise ComponentTreeRejectedError(ComponentTreeRejection.FILE_CHANGED)
        if before.st_size < 0 or before.st_size > policy.max_file_bytes:
            raise ComponentTreeRejectedError(ComponentTreeRejection.FILE_TOO_LARGE)
        digest = hashlib.sha256()
        copied = 0
        while True:
            _require_not_cancelled(cancellation)
            chunk = os.read(descriptor, policy.read_chunk_bytes)
            if not chunk:
                break
            _require_not_cancelled(cancellation)
            copied += len(chunk)
            if copied > before.st_size or copied > policy.max_file_bytes:
                raise ComponentTreeRejectedError(ComponentTreeRejection.FILE_CHANGED)
            digest.update(chunk)
            if progress is not None:
                progress(copied)
        _require_not_cancelled(cancellation)
        after = os.fstat(descriptor)
        if copied != before.st_size or _file_identity(before) != _file_identity(after):
            raise ComponentTreeRejectedError(ComponentTreeRejection.FILE_CHANGED)
    finally:
        os.close(descriptor)
    return ComponentFileFingerprint(relative_path, copied, digest.hexdigest())


def _file_identity(info: os.stat_result) -> tuple[int, int, int, int]:
    """Return fields that must stay unchanged while a file is hashed."""
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def component_tree_digest(
    files: Iterable[ComponentFileValue],
    *,
    cancellation: Event | None = None,
) -> str:
    """Hash the documented versioned canonical content-manifest framing."""
    digest = hashlib.sha256(_TREE_FORMAT)
    ordered = sorted(files, key=lambda item: item.relative_path.encode("utf-8"))
    for file in ordered:
        _require_not_cancelled(cancellation)
        path = file.relative_path.encode("utf-8")
        digest.update(len(path).to_bytes(4, "big"))
        digest.update(path)
        digest.update(file.size.to_bytes(8, "big"))
        digest.update(bytes.fromhex(file.sha256))
    return digest.hexdigest()


def _require_not_cancelled(cancellation: Event | None) -> None:
    """Stop at one bounded filesystem verification checkpoint."""
    if cancellation is not None and cancellation.is_set():
        raise ComponentTreeCancelledError


def _notify(
    observer: Callable[[ComponentTreeProgress], None] | None,
    completed_bytes: int,
    total_bytes: int,
) -> None:
    """Publish one immutable exact-byte verification snapshot."""
    if observer is not None:
        observer(ComponentTreeProgress(completed_bytes, total_bytes))


def _file_observer(
    observer: Callable[[ComponentTreeProgress], None] | None,
    completed_before_file: int,
    total_bytes: int,
) -> Callable[[int], None] | None:
    """Bind one file's chunk progress to the tree-wide byte count."""
    if observer is None:
        return None

    def notify(completed_file_bytes: int) -> None:
        observer(
            ComponentTreeProgress(
                completed_before_file + completed_file_bytes,
                total_bytes,
            )
        )

    return notify
