"""Task binding, worker ownership, revision, and paging tests."""

from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import cast

import pytest
from toqraq.contracts.geometry import SizeValue
from toqraq.contracts.project_inventory import (
    ProjectInventoryRequest,
    ProjectInventorySource,
)
from toqraq.contracts.setup import (
    EngineSetupResult,
    HostSetupResult,
    ProjectSetupResult,
    ProjectState,
    SetupAction,
    SetupRequest,
    SetupResult,
)
from toqraq.core.engine_contribution import (
    EngineProjectFormat,
    ProjectDescription,
)
from toqraq.core.errors import PerceptionStaleError, ProjectNotBoundError
from toqraq.core.project_format_catalog import ProjectFormatCatalog
from toqraq.core.project_inventory import (
    ProjectInventoryCategory,
    ProjectInventoryEntry,
    ProjectInventorySnapshot,
    ProjectInventoryStatistics,
)
from toqraq.core.session import EngineSession
from toqraq.core.session_registry import SessionRegistry
from toqraq.services.project_inventory import ProjectInventoryService
from toqraq.services.workspace_context import WorkspaceContextService


class _Probe:
    engine_id = "godot"

    def probe(self, project_root: Path) -> ProjectDescription | None:
        del project_root
        return None


class _WorkspaceSetup:
    async def check(self, request: SetupRequest) -> SetupResult:
        assert request.project_dir is not None
        return _recognized(request.project_dir)


class _MutableRegistry(SessionRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.current: dict[str, EngineSession] = {}

    def find(self, session_id: str) -> EngineSession | None:
        return self.current.get(session_id)


@dataclass(slots=True)
class _LiveOwner:
    project: ProjectDescription


class _Reader:
    engine_id = "godot"

    def __init__(self, entries: tuple[ProjectInventoryEntry, ...]) -> None:
        self.entries = entries
        self.calls: list[tuple[Path, str | None]] = []

    def scan(
        self,
        project_root: Path,
        scope: str | None,
        cancellation: Event,
    ) -> ProjectInventorySnapshot:
        assert not cancellation.is_set()
        self.calls.append((project_root, scope))
        entries = tuple(
            entry for entry in self.entries if scope is None or entry.path.startswith(f"{scope}/")
        )
        return _snapshot(entries)


class _BlockingReader(_Reader):
    def __init__(self, entries: tuple[ProjectInventoryEntry, ...]) -> None:
        super().__init__(entries)
        self.started = Event()
        self.release = Event()

    def scan(
        self,
        project_root: Path,
        scope: str | None,
        cancellation: Event,
    ) -> ProjectInventorySnapshot:
        self.calls.append((project_root, scope))
        self.started.set()
        while not self.release.wait(0.005):
            if cancellation.is_set():
                raise asyncio.CancelledError
        return _snapshot(self.entries)


class _CancellableReader(_Reader):
    def __init__(self) -> None:
        super().__init__(())
        self.started = Event()
        self.exited = Event()

    def scan(
        self,
        project_root: Path,
        scope: str | None,
        cancellation: Event,
    ) -> ProjectInventorySnapshot:
        self.calls.append((project_root, scope))
        self.started.set()
        cancellation.wait()
        self.exited.set()
        raise asyncio.CancelledError


def _recognized(path: str) -> SetupResult:
    return SetupResult(
        host=HostSetupResult(platform="windows", native_display=True),
        engine=EngineSetupResult(
            id="godot",
            runtime=None,
            available_versions=(),
            required_component_release_ids=(),
            runtime_install_required=False,
        ),
        project=ProjectSetupResult(
            path=path,
            state=ProjectState.READY,
            viewport_size=SizeValue(width=960, height=540),
            probed_engine_ids=("godot",),
        ),
        engine_choices=(),
        action=SetupAction.RUNTIME_UNAVAILABLE,
    )


def _snapshot(
    entries: tuple[ProjectInventoryEntry, ...],
    *,
    complete: bool = True,
) -> ProjectInventorySnapshot:
    return ProjectInventorySnapshot(
        engine_id="godot",
        entries=entries,
        statistics=ProjectInventoryStatistics(
            visited_entries=len(entries) + 3,
            visited_directories=2,
            excluded_links=1,
            excluded_policy=1,
            unreadable=0 if complete else 1,
            unclassified=1,
            complete=complete,
        ),
    )


def _entry(
    path: str,
    category: ProjectInventoryCategory,
    name: str | None = None,
) -> ProjectInventoryEntry:
    return ProjectInventoryEntry(path=path, category=category, name=name)


def _service(
    reader: _Reader,
) -> tuple[ProjectInventoryService, _MutableRegistry, WorkspaceContextService]:
    project_format = EngineProjectFormat(
        engine_id="godot",
        project_probe=_Probe(),
        project_inventory_reader=reader,
    )
    registry = _MutableRegistry()
    workspaces = WorkspaceContextService(_WorkspaceSetup())
    return (
        ProjectInventoryService(ProjectFormatCatalog((project_format,)), registry, workspaces),
        registry,
        workspaces,
    )


async def _bind(workspaces: WorkspaceContextService, task: str, root: Path) -> None:
    await workspaces.update(task, SetupRequest(project_dir=str(root)))


def _live(root: Path) -> EngineSession:
    project = ProjectDescription(
        engine_id="godot",
        project_root=root,
        marker_path=root / "project.godot",
        confidence=100,
    )
    return cast(EngineSession, _LiveOwner(project))


def _decode_cursor(value: str) -> dict[str, object]:
    padding = "=" * (-len(value) % 4)
    decoded: object = json.loads(base64.urlsafe_b64decode(value + padding))
    assert isinstance(decoded, dict)
    return cast(dict[str, object], decoded)


def _encode_cursor(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
    return base64.urlsafe_b64encode(encoded).rstrip(b"=").decode("ascii")


def test_task_isolation_workspace_fallback_and_unbound_failure(tmp_path: Path) -> None:
    async def scenario() -> None:
        reader = _Reader((_entry("main.tscn", ProjectInventoryCategory.SCENE),))
        service, _, workspaces = _service(reader)
        first = tmp_path / "first"
        second = tmp_path / "second"
        await _bind(workspaces, "task-a", first)
        await _bind(workspaces, "task-b", second)

        result_a = await service.read("task-a", ProjectInventoryRequest())
        result_b = await service.read("task-b", ProjectInventoryRequest())

        assert result_a.source is ProjectInventorySource.WORKSPACE
        assert result_b.source is ProjectInventorySource.WORKSPACE
        assert reader.calls == [(first, None), (second, None)]
        with pytest.raises(ProjectNotBoundError):
            await service.read("task-c", ProjectInventoryRequest())

    asyncio.run(scenario())


def test_live_session_has_priority_over_same_tasks_workspace(tmp_path: Path) -> None:
    async def scenario() -> None:
        reader = _Reader((_entry("main.tscn", ProjectInventoryCategory.SCENE),))
        service, registry, workspaces = _service(reader)
        workspace_root = tmp_path / "workspace"
        live_root = tmp_path / "live"
        await _bind(workspaces, "task", workspace_root)
        registry.current["task"] = _live(live_root)

        result = await service.read("task", ProjectInventoryRequest())

        assert result.source is ProjectInventorySource.LIVE
        assert reader.calls == [(live_root, None)]

    asyncio.run(scenario())


@pytest.mark.parametrize("replacement", ["live", "workspace"])
def test_scan_rejects_live_and_workspace_incarnation_replacement(
    tmp_path: Path,
    replacement: str,
) -> None:
    async def scenario() -> None:
        reader = _BlockingReader((_entry("main.tscn", ProjectInventoryCategory.SCENE),))
        service, registry, workspaces = _service(reader)
        root = tmp_path / "game"
        await _bind(workspaces, "task", root)
        if replacement == "live":
            registry.current["task"] = _live(root)
        read = asyncio.create_task(service.read("task", ProjectInventoryRequest()))
        await asyncio.to_thread(reader.started.wait)
        if replacement == "live":
            registry.current["task"] = _live(root)
        else:
            workspaces.clear("task")
            await _bind(workspaces, "task", root)
        reader.release.set()

        with pytest.raises(PerceptionStaleError, match=r"perception\.stale"):
            await read

    asyncio.run(scenario())


def test_live_appearance_invalidates_workspace_scan(tmp_path: Path) -> None:
    async def scenario() -> None:
        reader = _BlockingReader((_entry("main.tscn", ProjectInventoryCategory.SCENE),))
        service, registry, workspaces = _service(reader)
        root = tmp_path / "game"
        await _bind(workspaces, "task", root)
        read = asyncio.create_task(service.read("task", ProjectInventoryRequest()))
        await asyncio.to_thread(reader.started.wait)
        registry.current["task"] = _live(root)
        reader.release.set()

        with pytest.raises(PerceptionStaleError):
            await read

    asyncio.run(scenario())


def test_caller_cancellation_settles_cooperative_thread_before_return(tmp_path: Path) -> None:
    async def scenario() -> None:
        reader = _CancellableReader()
        service, _, workspaces = _service(reader)
        await _bind(workspaces, "task", tmp_path / "game")
        read = asyncio.create_task(service.read("task", ProjectInventoryRequest()))
        await asyncio.to_thread(reader.started.wait)

        read.cancel()
        with pytest.raises(asyncio.CancelledError):
            await read

        assert reader.exited.is_set()

    asyncio.run(scenario())


def test_scope_categories_order_counts_and_partial_statistics(tmp_path: Path) -> None:
    async def scenario() -> None:
        reader = _Reader(
            (
                _entry("scripts/z.gd", ProjectInventoryCategory.SCRIPT),
                _entry("project.godot", ProjectInventoryCategory.SETTING),
                _entry("scripts/a.tscn", ProjectInventoryCategory.SCENE),
                _entry("scripts/input.gd", ProjectInventoryCategory.INPUT, "input/jump"),
            )
        )
        service, _, workspaces = _service(reader)
        await _bind(workspaces, "task", tmp_path / "game")

        result = await service.read(
            "task",
            ProjectInventoryRequest(
                scope="scripts",
                categories=(
                    ProjectInventoryCategory.INPUT,
                    ProjectInventoryCategory.SCENE,
                ),
            ),
        )

        assert reader.calls == [(tmp_path / "game", "scripts")]
        assert result.categories == (
            ProjectInventoryCategory.SCENE,
            ProjectInventoryCategory.INPUT,
        )
        assert tuple(entry.path for entry in result.entries) == (
            "scripts/a.tscn",
            "scripts/input.gd",
        )
        assert result.total_count == 2
        assert result.counts.model_dump() == {
            "scene": 1,
            "script": 1,
            "resource": 0,
            "setting": 0,
            "dependency": 0,
            "input": 1,
        }
        assert result.scan.excluded_links == 1
        assert result.scan.excluded_policy == 1
        assert result.scan.unclassified == 1

    asyncio.run(scenario())


def test_cursor_pages_and_rejects_schema_query_revision_and_offset_changes(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        reader = _Reader(
            tuple(
                _entry(f"scene-{index}.tscn", ProjectInventoryCategory.SCENE) for index in range(3)
            )
        )
        service, _, workspaces = _service(reader)
        await _bind(workspaces, "task", tmp_path / "game")
        first = await service.read("task", ProjectInventoryRequest(limit=1))
        assert first.next_cursor is not None
        second = await service.read(
            "task",
            ProjectInventoryRequest(limit=1, cursor=first.next_cursor),
        )
        assert second.next_cursor is not None
        last = await service.read(
            "task",
            ProjectInventoryRequest(limit=1, cursor=second.next_cursor),
        )
        assert tuple(page.entries[0].path for page in (first, second, last)) == (
            "scene-0.tscn",
            "scene-1.tscn",
            "scene-2.tscn",
        )
        assert not last.truncated

        with pytest.raises(PerceptionStaleError):
            await service.read(
                "task",
                ProjectInventoryRequest(
                    categories=(ProjectInventoryCategory.SCENE,),
                    cursor=first.next_cursor,
                ),
            )

        forged = _decode_cursor(first.next_cursor)
        forged["extra"] = True
        with pytest.raises(PerceptionStaleError):
            await service.read(
                "task",
                ProjectInventoryRequest(cursor=_encode_cursor(forged)),
            )
        forged.pop("extra")
        forged["o"] = 99
        with pytest.raises(PerceptionStaleError):
            await service.read(
                "task",
                ProjectInventoryRequest(cursor=_encode_cursor(forged)),
            )

        reader.entries += (_entry("new.gd", ProjectInventoryCategory.SCRIPT),)
        with pytest.raises(PerceptionStaleError):
            await service.read(
                "task",
                ProjectInventoryRequest(cursor=first.next_cursor),
            )

    asyncio.run(scenario())
