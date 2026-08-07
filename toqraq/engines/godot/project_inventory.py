"""No-follow bounded metadata inventory for standard Godot projects."""

from __future__ import annotations

import asyncio
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event

from ...core.absolute_path import require_absolute_normalized_path
from ...core.errors import ProjectIntrospectionError
from ...core.project_inventory import (
    MAX_PROJECT_INVENTORY_DEPTH,
    MAX_PROJECT_INVENTORY_DIRECTORIES,
    MAX_PROJECT_INVENTORY_RECORDS,
    MAX_PROJECT_INVENTORY_SCAN_NODES,
    ProjectInventoryEntry,
    ProjectInventorySnapshot,
    ProjectInventoryStatistics,
    validate_project_inventory_path,
)
from .identity import GODOT_ENGINE_ID
from .inventory_policy import (
    classify_inventory_file,
    excludes_inventory_name,
    marker_declaration_entries,
)
from .project import (
    GODOT_PROJECT_FILE_NAME,
    MAX_GODOT_PROJECT_FILE_BYTES,
    GodotProjectFile,
)

_READ_CHUNK_BYTES = 64 << 10
_REPARSE_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


@dataclass(slots=True)
class _ScanState:
    """Invocation-owned mutable counters before immutable snapshot publication."""

    record_limit: int
    entries: list[ProjectInventoryEntry] = field(default_factory=list)
    visited_entries: int = 0
    visited_directories: int = 0
    excluded_links: int = 0
    excluded_policy: int = 0
    unreadable: int = 0
    unclassified: int = 0
    complete: bool = True
    stopped: bool = False

    def append(self, entry: ProjectInventoryEntry) -> None:
        """Append one record or stop at the global observed-record bound."""
        if len(self.entries) >= self.record_limit:
            self.complete = False
            self.stopped = True
            return
        self.entries.append(entry)

    def merge(self, batch: _ScanState) -> None:
        """Commit one identity-stable directory batch to the published scan state."""
        self.entries.extend(batch.entries)
        self.visited_entries += batch.visited_entries
        self.visited_directories += batch.visited_directories
        self.excluded_links += batch.excluded_links
        self.excluded_policy += batch.excluded_policy
        self.unreadable += batch.unreadable
        self.unclassified += batch.unclassified
        self.complete = self.complete and batch.complete
        self.stopped = self.stopped or batch.stopped


class GodotProjectInventoryReader:
    """Read Godot project metadata without following or exposing filesystem links."""

    @property
    def engine_id(self) -> str:
        """Return the stable Godot project-format identity."""
        return GODOT_ENGINE_ID

    def scan(
        self,
        project_root: Path,
        scope: str | None,
        cancellation: Event,
    ) -> ProjectInventorySnapshot:
        """Return one bounded policy-visible project shape."""
        require_absolute_normalized_path(project_root, "project inventory root")
        if not isinstance(cancellation, Event):
            raise ValueError("project inventory cancellation is invalid")
        if scope is not None:
            validate_project_inventory_path(scope)
        scoped_root, prefix, scoped_identity = _require_scope_directory(
            project_root,
            scope,
            cancellation,
        )
        project = _read_marker(project_root, cancellation) if scope is None else None
        state = _scan_tree(
            project_root,
            scoped_root,
            prefix,
            scoped_identity,
            cancellation,
        )
        if project is not None:
            declarations = marker_declaration_entries(project)
            while not state.stopped:
                _raise_if_cancelled(cancellation)
                try:
                    entry = next(declarations)
                except StopIteration:
                    break
                if entry is None:
                    state.excluded_policy += 1
                    continue
                state.append(entry)
        return ProjectInventorySnapshot(
            engine_id=self.engine_id,
            entries=tuple(state.entries),
            statistics=ProjectInventoryStatistics(
                visited_entries=state.visited_entries,
                visited_directories=state.visited_directories,
                excluded_links=state.excluded_links,
                excluded_policy=state.excluded_policy,
                unreadable=state.unreadable,
                unclassified=state.unclassified,
                complete=state.complete,
            ),
        )


def _scan_tree(
    project_root: Path,
    scoped_root: Path,
    prefix: tuple[str, ...],
    scoped_identity: tuple[int, int],
    cancellation: Event,
) -> _ScanState:
    """Commit only directory batches whose pathname identity stayed stable."""
    state = _ScanState(record_limit=MAX_PROJECT_INVENTORY_RECORDS)
    stack: list[tuple[Path, tuple[str, ...], tuple[int, int]]] = [
        (scoped_root, prefix, scoped_identity)
    ]
    while stack and not state.stopped:
        _raise_if_cancelled(cancellation)
        directory, parts, expected_identity = stack.pop()
        if state.visited_directories >= MAX_PROJECT_INVENTORY_DIRECTORIES:
            state.complete = False
            state.stopped = True
            break
        try:
            before = os.lstat(directory)
            if not _safe_directory(before) or _directory_identity(before) != expected_identity:
                raise OSError("inventory directory identity changed before enumeration")
            batch = _ScanState(
                record_limit=max(
                    0,
                    MAX_PROJECT_INVENTORY_RECORDS - len(state.entries),
                )
            )
            batch_stack: list[tuple[Path, tuple[str, ...], tuple[int, int]]] = []
            with os.scandir(directory) as children:
                batch.visited_directories = 1
                for child in children:
                    _raise_if_cancelled(cancellation)
                    if (
                        state.visited_entries + batch.visited_entries
                        >= MAX_PROJECT_INVENTORY_SCAN_NODES
                    ):
                        batch.complete = False
                        batch.stopped = True
                        break
                    batch.visited_entries += 1
                    _visit_child(
                        batch,
                        child,
                        parts,
                        batch_stack,
                        project_root,
                    )
                    if batch.stopped:
                        break
            after = os.lstat(directory)
            if not _safe_directory(after) or _directory_identity(after) != expected_identity:
                raise OSError("inventory directory identity changed during enumeration")
        except OSError as exc:
            if directory == scoped_root:
                raise ProjectIntrospectionError(
                    parameters={"engine": GODOT_ENGINE_ID},
                    details={"reason": "inventory_scope_unreadable"},
                    cause=exc,
                ) from exc
            state.unreadable += 1
            state.complete = False
            continue
        state.merge(batch)
        stack.extend(batch_stack)
    return state


def _visit_child(
    state: _ScanState,
    child: os.DirEntry[str],
    parts: tuple[str, ...],
    stack: list[tuple[Path, tuple[str, ...], tuple[int, int]]],
    project_root: Path,
) -> None:
    """Classify one visited directory entry without acquiring file contents."""
    try:
        metadata = child.stat(follow_symlinks=False)
    except OSError:
        state.unreadable += 1
        state.complete = False
        return
    directory_entry = stat.S_ISDIR(metadata.st_mode)
    if excludes_inventory_name(child.name, directory=directory_entry):
        state.excluded_policy += 1
        return
    if _is_link_or_reparse(metadata):
        state.excluded_links += 1
        return
    child_parts = (*parts, child.name)
    relative_path = "/".join(child_parts)
    child_path = Path(child.path)
    if not _lexically_within(project_root, child_path):
        state.excluded_policy += 1
        state.complete = False
        return
    if not _representable_path(relative_path):
        state.excluded_policy += 1
        return
    if directory_entry:
        if len(child_parts) > MAX_PROJECT_INVENTORY_DEPTH:
            state.excluded_policy += 1
            state.complete = False
        else:
            try:
                directory_metadata = os.lstat(child_path)
            except OSError:
                state.unreadable += 1
                state.complete = False
                return
            if not _safe_directory(directory_metadata):
                state.excluded_links += 1
                return
            stack.append((child_path, child_parts, _directory_identity(directory_metadata)))
        return
    if not stat.S_ISREG(metadata.st_mode):
        state.unclassified += 1
        return
    category = classify_inventory_file(relative_path)
    if category is None:
        state.unclassified += 1
        return
    state.append(ProjectInventoryEntry(path=relative_path, category=category))


def _read_marker(project_root: Path, cancellation: Event) -> GodotProjectFile:
    """Read one regular stable marker identity through a bounded descriptor."""
    path = project_root / GODOT_PROJECT_FILE_NAME
    try:
        before = os.lstat(path)
        if not stat.S_ISREG(before.st_mode) or _is_link_or_reparse(before):
            raise OSError("project marker is not a regular no-follow file")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or _is_link_or_reparse(opened):
                raise OSError("opened project marker is not a regular file")
            if _file_identity(before) != _file_identity(opened):
                raise OSError("project marker identity changed before open")
            payload = _read_bounded_descriptor(descriptor, cancellation)
            after_read = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        after_path = os.lstat(path)
        identity = _file_identity(before)
        if (
            identity != _file_identity(after_read)
            or identity != _file_identity(after_path)
            or _is_link_or_reparse(after_path)
        ):
            raise OSError("project marker identity changed during read")
        text = payload.decode("utf-8-sig")
    except asyncio.CancelledError:
        raise
    except (OSError, UnicodeError) as exc:
        raise ProjectIntrospectionError(
            parameters={"engine": GODOT_ENGINE_ID},
            details={"reason": "project_file_unreadable"},
            cause=exc,
        ) from exc
    return GodotProjectFile.parse(
        text,
        check_cancelled=lambda: _raise_if_cancelled(cancellation),
    )


def _read_bounded_descriptor(descriptor: int, cancellation: Event) -> bytes:
    """Read marker bytes in cancellable chunks under the existing parser bound."""
    chunks: list[bytes] = []
    total = 0
    while True:
        _raise_if_cancelled(cancellation)
        chunk = os.read(descriptor, _READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_GODOT_PROJECT_FILE_BYTES:
            raise ProjectIntrospectionError(
                parameters={"maximum_bytes": MAX_GODOT_PROJECT_FILE_BYTES},
                details={"reason": "project_file_too_large"},
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _require_scope_directory(
    project_root: Path,
    scope: str | None,
    cancellation: Event,
) -> tuple[Path, tuple[str, ...], tuple[int, int]]:
    """Resolve exact on-disk segments without pathname alias interpretation."""
    parts = tuple(scope.split("/")) if scope is not None else ()
    if len(parts) > MAX_PROJECT_INVENTORY_DEPTH:
        raise ProjectIntrospectionError(
            parameters={"engine": GODOT_ENGINE_ID},
            details={"reason": "inventory_scope_too_deep"},
        )
    current = project_root
    metadata = _require_scope_metadata(current)
    lookup_count = 0
    for segment in parts:
        if excludes_inventory_name(segment, directory=True):
            raise ProjectIntrospectionError(
                parameters={"engine": GODOT_ENGINE_ID},
                details={"reason": "inventory_scope_excluded"},
            )
        current, metadata, visited = _find_exact_scope_directory(
            project_root,
            current,
            metadata,
            segment,
            MAX_PROJECT_INVENTORY_SCAN_NODES - lookup_count,
            cancellation,
        )
        lookup_count += visited
    return current, parts, _directory_identity(metadata)


def _find_exact_scope_directory(
    project_root: Path,
    parent: Path,
    parent_metadata: os.stat_result,
    segment: str,
    lookup_budget: int,
    cancellation: Event,
) -> tuple[Path, os.stat_result, int]:
    """Find one exact DirEntry name and commit it after parent revalidation."""
    child_path: Path | None = None
    child_metadata: os.stat_result | None = None
    visited = 0
    try:
        if not _lexically_within(project_root, parent):
            raise OSError("inventory scope parent escaped its captured root")
        parent_before = os.lstat(parent)
        if not _safe_directory(parent_before) or _directory_identity(
            parent_before
        ) != _directory_identity(parent_metadata):
            raise OSError("inventory scope parent identity changed before lookup")
        with os.scandir(parent) as children:
            for child in children:
                _raise_if_cancelled(cancellation)
                visited += 1
                if visited > lookup_budget:
                    raise OSError("inventory scope directory exceeds lookup bound")
                if child.name != segment:
                    continue
                child_path = Path(child.path)
                if not _lexically_within(project_root, child_path):
                    raise OSError("inventory scope escaped its captured root")
                child_metadata = os.lstat(child_path)
                break
        parent_after = os.lstat(parent)
    except asyncio.CancelledError:
        raise
    except OSError as exc:
        raise ProjectIntrospectionError(
            parameters={"engine": GODOT_ENGINE_ID},
            details={"reason": "inventory_scope_unreadable"},
            cause=exc,
        ) from exc
    if not _safe_directory(parent_after) or _directory_identity(
        parent_after
    ) != _directory_identity(parent_metadata):
        raise ProjectIntrospectionError(
            parameters={"engine": GODOT_ENGINE_ID},
            details={"reason": "inventory_scope_changed"},
        )
    if child_path is None or child_metadata is None:
        raise ProjectIntrospectionError(
            parameters={"engine": GODOT_ENGINE_ID},
            details={"reason": "inventory_scope_unreadable"},
        )
    if not _safe_directory(child_metadata):
        raise ProjectIntrospectionError(
            parameters={"engine": GODOT_ENGINE_ID},
            details={"reason": "inventory_scope_unsafe"},
        )
    return child_path, child_metadata, visited


def _lexically_within(project_root: Path, candidate: Path) -> bool:
    """Check absolute lexical confinement without resolving filesystem links."""
    return candidate.is_absolute() and candidate.is_relative_to(project_root)


def _require_scope_metadata(path: Path) -> os.stat_result:
    """Read one safe directory identity for scope traversal."""
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise ProjectIntrospectionError(
            parameters={"engine": GODOT_ENGINE_ID},
            details={"reason": "inventory_scope_unreadable"},
            cause=exc,
        ) from exc
    if not _safe_directory(metadata):
        raise ProjectIntrospectionError(
            parameters={"engine": GODOT_ENGINE_ID},
            details={"reason": "inventory_scope_unsafe"},
        )
    return metadata


def _safe_directory(metadata: os.stat_result) -> bool:
    """Recognize one ordinary directory that is neither linked nor reparsed."""
    return stat.S_ISDIR(metadata.st_mode) and not _is_link_or_reparse(metadata)


def _directory_identity(metadata: os.stat_result) -> tuple[int, int]:
    """Return stable filesystem identity without mutable directory metadata."""
    return metadata.st_dev, metadata.st_ino


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    """Recognize POSIX links and Windows reparse-point metadata."""
    attributes = getattr(metadata, "st_file_attributes", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & _REPARSE_ATTRIBUTE)


def _file_identity(metadata: os.stat_result) -> tuple[int, int, int, int]:
    """Return the stable standard-library identity facts compared around a read."""
    return metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns


def _representable_path(value: str) -> bool:
    """Return whether one filesystem name fits the public relative-path policy."""
    try:
        validate_project_inventory_path(value)
    except ValueError:
        return False
    return True


def _raise_if_cancelled(cancellation: Event) -> None:
    """Cooperatively stop one worker without converting caller cancellation."""
    if cancellation.is_set():
        raise asyncio.CancelledError
