"""Task-bound project inventory, revision, cursor, and paging policy."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Protocol, TypeGuard

from ..contracts.identifiers import HermesSessionId
from ..contracts.project_inventory import (
    ProjectInventoryCategoryCounts,
    ProjectInventoryEntryValue,
    ProjectInventoryRequest,
    ProjectInventoryResult,
    ProjectInventoryScanResult,
    ProjectInventorySource,
)
from ..core.absolute_path import require_absolute_normalized_path
from ..core.errors import (
    PerceptionStaleError,
    ProjectIntrospectionError,
    ProjectNotBoundError,
)
from ..core.project_format_catalog import ProjectFormatCatalog
from ..core.project_inventory import (
    MAX_PROJECT_INVENTORY_RECORDS,
    PROJECT_INVENTORY_CATEGORIES,
    ProjectInventoryCategory,
    ProjectInventoryEntry,
    ProjectInventorySnapshot,
    project_inventory_entry_key,
)
from ..core.session import EngineSession
from ..core.session_registry import SessionRegistry
from .workspace_context import WorkspaceContextService, WorkspaceContextSnapshot

logger = logging.getLogger(__name__)
_CURSOR_VERSION = 1
_REVISION_DOMAIN = b"toqraq.project.inventory.shape.v1"
_QUERY_DOMAIN = b"toqraq.project.inventory.query.v1"


class _Digest(Protocol):
    """Minimal hashlib surface used by deterministic length framing."""

    def update(self, payload: bytes) -> None:
        """Consume one immutable byte segment."""
        ...


@dataclass(frozen=True, slots=True, kw_only=True)
class _ProjectBinding:
    """One captured task binding whose owner object is its incarnation."""

    source: ProjectInventorySource
    engine_id: str
    project_root: Path
    incarnation: EngineSession | WorkspaceContextSnapshot


@dataclass(frozen=True, slots=True, kw_only=True)
class _Cursor:
    """Decoded strict stateless continuation state."""

    revision: str
    query: str
    offset: int


class ProjectInventoryService:
    """Read one stable metadata page from the caller's preferred project binding."""

    __slots__ = ("_formats", "_registry", "_workspaces")

    def __init__(
        self,
        formats: ProjectFormatCatalog,
        registry: SessionRegistry,
        workspaces: WorkspaceContextService,
    ) -> None:
        """Bind the exact recognition catalog and both task-incarnation owners."""
        if not isinstance(formats, ProjectFormatCatalog):
            raise ValueError("project inventory format catalog is invalid")
        if not isinstance(registry, SessionRegistry):
            raise ValueError("project inventory session registry is invalid")
        if not isinstance(workspaces, WorkspaceContextService):
            raise ValueError("project inventory workspace owner is invalid")
        self._formats = formats
        self._registry = registry
        self._workspaces = workspaces

    async def read(
        self,
        owner_id: HermesSessionId,
        request: ProjectInventoryRequest,
    ) -> ProjectInventoryResult:
        """Scan, revalidate, filter, and page the caller's current project shape."""
        if not isinstance(request, ProjectInventoryRequest):
            raise ValueError("project inventory request is invalid")
        binding = self._find_binding(owner_id)
        if binding is None:
            raise ProjectNotBoundError(details={"reason": "task_project_absent"})
        project_format = self._formats.require(binding.engine_id)
        cancellation = Event()
        worker = asyncio.create_task(
            asyncio.to_thread(
                project_format.project_inventory_reader.scan,
                binding.project_root,
                request.scope,
                cancellation,
            ),
            name="toqraq-project-inventory-scan",
        )
        try:
            snapshot = await asyncio.shield(worker)
        except asyncio.CancelledError:
            cancellation.set()
            await _settle_cancelled_worker(worker)
            raise
        self._require_current(owner_id, binding)
        if (
            not isinstance(snapshot, ProjectInventorySnapshot)
            or snapshot.engine_id != binding.engine_id
        ):
            raise ProjectIntrospectionError(
                parameters={"engine": binding.engine_id},
                details={"reason": "inventory_identity_mismatch"},
            )
        return self._page(binding, snapshot, request)

    def _find_binding(self, owner_id: HermesSessionId) -> _ProjectBinding | None:
        """Prefer one exact live owner, then the exact workspace snapshot object."""
        session = self._registry.find(owner_id)
        if session is not None:
            return _ProjectBinding(
                source=ProjectInventorySource.LIVE,
                engine_id=session.project.engine_id,
                project_root=session.project.project_root,
                incarnation=session,
            )
        workspace = self._workspaces.find(owner_id)
        if workspace is None:
            return None
        project_root = require_absolute_normalized_path(
            Path(workspace.project_path),
            "workspace inventory project root",
        )
        return _ProjectBinding(
            source=ProjectInventorySource.WORKSPACE,
            engine_id=workspace.engine_id,
            project_root=project_root,
            incarnation=workspace,
        )

    def _require_current(self, owner_id: str, expected: _ProjectBinding) -> None:
        """Reject every source or object-incarnation change after filesystem work."""
        current = self._find_binding(owner_id)
        if (
            current is None
            or current.source is not expected.source
            or current.incarnation is not expected.incarnation
        ):
            raise PerceptionStaleError(details={"reason": "project_binding_replaced"})

    def _page(
        self,
        binding: _ProjectBinding,
        snapshot: ProjectInventorySnapshot,
        request: ProjectInventoryRequest,
    ) -> ProjectInventoryResult:
        """Apply canonical query policy and create one strict continuation."""
        entries = tuple(sorted(snapshot.entries, key=project_inventory_entry_key))
        if any(not _in_scope(entry.path, request.scope) for entry in entries):
            raise ProjectIntrospectionError(
                parameters={"engine": binding.engine_id},
                details={"reason": "inventory_scope_mismatch"},
            )
        revision = _shape_revision(snapshot, entries)
        categories = _effective_categories(request.categories)
        query = _query_fingerprint(request.scope, categories)
        offset = (
            0 if request.cursor is None else self._decode_cursor(request.cursor, revision, query)
        )
        selected = tuple(entry for entry in entries if entry.category in categories)
        if offset > len(selected) or (offset == len(selected) and offset != 0):
            raise _stale("inventory_cursor_offset_invalid", revision)
        page = selected[offset : offset + request.limit]
        next_offset = offset + len(page)
        truncated = next_offset < len(selected)
        next_cursor = _encode_cursor(revision, query, next_offset) if truncated else None
        counts = _category_counts(entries)
        statistics = snapshot.statistics
        return ProjectInventoryResult(
            engine=binding.engine_id,
            source=binding.source,
            revision=revision,
            scope=request.scope,
            categories=categories,
            counts=counts,
            scan=ProjectInventoryScanResult(
                visited_entries=statistics.visited_entries,
                visited_directories=statistics.visited_directories,
                excluded_links=statistics.excluded_links,
                excluded_policy=statistics.excluded_policy,
                unreadable=statistics.unreadable,
                unclassified=statistics.unclassified,
                complete=statistics.complete,
            ),
            total_count=len(selected),
            entries=tuple(ProjectInventoryEntryValue.from_core(entry) for entry in page),
            truncated=truncated,
            next_cursor=next_cursor,
        )

    def _decode_cursor(self, value: str, revision: str, query: str) -> int:
        """Verify canonical encoding, schema, query, revision, and offset."""
        try:
            payload = _base64url_decode(value)
        except (ValueError, binascii.Error):
            raise _stale("inventory_cursor_invalid", revision) from None
        decoded = _cursor_payload(payload, revision)
        if decoded.query != query:
            raise _stale("inventory_cursor_query_mismatch", revision)
        if decoded.revision != revision:
            raise _stale("inventory_shape_changed", revision)
        return decoded.offset


async def _settle_cancelled_worker(
    worker: asyncio.Task[ProjectInventorySnapshot],
) -> None:
    """Keep observing one cooperative worker despite repeated caller cancellation."""
    while not worker.done():
        try:
            await asyncio.shield(worker)
        except asyncio.CancelledError:
            continue
        except Exception:
            break
    try:
        worker.result()
    except (asyncio.CancelledError, Exception) as exc:
        logger.debug(
            "project inventory worker settled after caller cancellation exception_type=%s",
            f"{type(exc).__module__}.{type(exc).__qualname__}",
        )


def _effective_categories(
    requested: tuple[ProjectInventoryCategory, ...] | None,
) -> tuple[ProjectInventoryCategory, ...]:
    """Return the canonical effective category set for query identity."""
    if requested is None:
        return PROJECT_INVENTORY_CATEGORIES
    return tuple(category for category in PROJECT_INVENTORY_CATEGORIES if category in requested)


def _in_scope(path: str, scope: str | None) -> bool:
    """Match only descendants of one already validated directory scope."""
    return scope is None or path.startswith(f"{scope}/")


def _shape_revision(
    snapshot: ProjectInventorySnapshot,
    entries: tuple[ProjectInventoryEntry, ...],
) -> str:
    """Hash only policy-visible inventory shape and completeness."""
    digest = hashlib.sha256(_REVISION_DOMAIN)
    _feed_text(digest, snapshot.engine_id)
    statistics = snapshot.statistics
    digest.update(b"\x01" if statistics.complete else b"\x00")
    for count in (
        statistics.visited_entries,
        statistics.visited_directories,
        statistics.excluded_links,
        statistics.excluded_policy,
        statistics.unreadable,
        statistics.unclassified,
    ):
        digest.update(count.to_bytes(8, "big"))
    for entry in entries:
        digest.update(b"e")
        _feed_text(digest, entry.path)
        _feed_text(digest, entry.category.value)
        _feed_text(digest, entry.name or "")
    return digest.hexdigest()


def _query_fingerprint(
    scope: str | None,
    categories: tuple[ProjectInventoryCategory, ...],
) -> str:
    """Hash the canonical filter shape bound into a continuation cursor."""
    digest = hashlib.sha256(_QUERY_DOMAIN)
    _feed_text(digest, scope or "")
    for category in categories:
        _feed_text(digest, category.value)
    return digest.hexdigest()


def _feed_text(digest: _Digest, value: str) -> None:
    """Feed unambiguous length-prefixed UTF-8 into one hashlib object."""
    payload = value.encode("utf-8")
    digest.update(len(payload).to_bytes(4, "big"))
    digest.update(payload)


def _base64url_encode(payload: bytes) -> str:
    """Return canonical unpadded URL-safe base64."""
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _encode_cursor(revision: str, query: str, offset: int) -> str:
    """Encode one strict fixed-schema stateless continuation payload."""
    payload = json.dumps(
        {"v": _CURSOR_VERSION, "r": revision, "q": query, "o": offset},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return _base64url_encode(payload)


def _base64url_decode(value: str) -> bytes:
    """Decode only a canonical unpadded URL-safe base64 value."""
    if not value or "=" in value:
        raise ValueError("cursor base64 is invalid")
    padding = "=" * (-len(value) % 4)
    decoded = base64.b64decode(value + padding, altchars=b"-_", validate=True)
    if _base64url_encode(decoded) != value:
        raise ValueError("cursor base64 is not canonical")
    return decoded


def _cursor_payload(payload: bytes, current_revision: str) -> _Cursor:
    """Decode and immediately type one fixed cursor JSON object."""
    try:
        candidate: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise _stale("inventory_cursor_invalid", current_revision) from None
    if not isinstance(candidate, dict) or set(candidate) != {"v", "r", "q", "o"}:
        raise _stale("inventory_cursor_invalid", current_revision)
    version = candidate.get("v")
    revision = candidate.get("r")
    query = candidate.get("q")
    offset = candidate.get("o")
    if (
        type(version) is not int
        or version != _CURSOR_VERSION
        or not _is_digest(revision)
        or not _is_digest(query)
        or type(offset) is not int
        or not 1 <= offset <= MAX_PROJECT_INVENTORY_RECORDS
    ):
        raise _stale("inventory_cursor_invalid", current_revision)
    return _Cursor(revision=revision, query=query, offset=offset)


def _is_digest(value: object) -> TypeGuard[str]:
    """Recognize one lowercase SHA-256 text without coercion."""
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _category_counts(
    entries: tuple[ProjectInventoryEntry, ...],
) -> ProjectInventoryCategoryCounts:
    """Count every fixed category over the observed scoped shape."""
    counts = {category: 0 for category in PROJECT_INVENTORY_CATEGORIES}
    for entry in entries:
        counts[entry.category] += 1
    return ProjectInventoryCategoryCounts(
        scene=counts[ProjectInventoryCategory.SCENE],
        script=counts[ProjectInventoryCategory.SCRIPT],
        resource=counts[ProjectInventoryCategory.RESOURCE],
        setting=counts[ProjectInventoryCategory.SETTING],
        dependency=counts[ProjectInventoryCategory.DEPENDENCY],
        input=counts[ProjectInventoryCategory.INPUT],
    )


def _stale(reason: str, revision: str) -> PerceptionStaleError:
    """Create one safe inventory stale failure with the current shape revision."""
    return PerceptionStaleError(details={"reason": reason, "current_revision": revision})
