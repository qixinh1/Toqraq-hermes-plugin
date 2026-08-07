"""Task-owned workspace context lifecycle and stale-update tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from toqraq.contracts.geometry import SizeValue
from toqraq.contracts.setup import (
    EngineSetupResult,
    HostSetupResult,
    ProjectSetupResult,
    ProjectState,
    SetupAction,
    SetupRequest,
    SetupResult,
)
from toqraq.services.workspace_context import WorkspaceContextService


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


def _unrecognized(path: str) -> SetupResult:
    return SetupResult(
        host=HostSetupResult(platform="windows", native_display=True),
        engine=None,
        project=ProjectSetupResult(
            path=path,
            state=ProjectState.NOT_DETECTED,
            viewport_size=None,
            probed_engine_ids=("godot",),
        ),
        engine_choices=(),
        action=SetupAction.SELECT_PROJECT,
    )


class ImmediateSetup:
    """Return one path-keyed setup result without external work."""

    async def check(self, request: SetupRequest) -> SetupResult:
        assert request.project_dir is not None
        return _recognized(request.project_dir)


@dataclass(slots=True)
class PendingProbe:
    """Controllable setup probe used to order competing updates."""

    result: SetupResult
    started: asyncio.Event
    release: asyncio.Event


class ControlledSetup:
    """Resolve each project only when its test-owned gate opens."""

    def __init__(self, probes: dict[str, PendingProbe]) -> None:
        self._probes = probes

    async def check(self, request: SetupRequest) -> SetupResult:
        assert request.project_dir is not None
        probe = self._probes[request.project_dir]
        probe.started.set()
        await probe.release.wait()
        return probe.result


def test_recognized_workspace_is_cached_and_clear_is_probe_free() -> None:
    async def scenario() -> None:
        service = WorkspaceContextService(ImmediateSetup())

        result = await service.update("task-1", SetupRequest(project_dir="D:/game"))

        assert result == _recognized("D:/game")
        snapshot = service.find("task-1")
        assert snapshot is not None
        assert snapshot.project_path == "D:/game"
        assert snapshot.engine_id == "godot"
        assert snapshot.runtime_version is None
        assert snapshot.setup_action is SetupAction.RUNTIME_UNAVAILABLE
        assert snapshot.viewport_size == SizeValue(width=960, height=540)

        assert await service.update("task-1", SetupRequest()) is None
        assert service.find("task-1") is None
        assert service._updates == {}

    asyncio.run(scenario())


def test_non_ready_result_withdraws_the_previous_snapshot() -> None:
    class SwitchingSetup:
        recognized = True

        async def check(self, request: SetupRequest) -> SetupResult:
            assert request.project_dir is not None
            if self.recognized:
                return _recognized(request.project_dir)
            return _unrecognized(request.project_dir)

    async def scenario() -> None:
        setup = SwitchingSetup()
        service = WorkspaceContextService(setup)
        await service.update("task-1", SetupRequest(project_dir="D:/game"))
        assert service.find("task-1") is not None
        setup.recognized = False

        result = await service.update("task-1", SetupRequest(project_dir="D:/other"))

        assert result == _unrecognized("D:/other")
        assert service.find("task-1") is None

    asyncio.run(scenario())


def test_failed_probe_withdraws_snapshot_and_releases_update_identity() -> None:
    class SwitchingSetup:
        failing = False

        async def check(self, request: SetupRequest) -> SetupResult:
            assert request.project_dir is not None
            if self.failing:
                raise RuntimeError("probe failed")
            return _recognized(request.project_dir)

    async def scenario() -> None:
        setup = SwitchingSetup()
        service = WorkspaceContextService(setup)
        await service.update("task-1", SetupRequest(project_dir="D:/game"))
        setup.failing = True

        with pytest.raises(RuntimeError, match="probe failed"):
            await service.update("task-1", SetupRequest(project_dir="D:/broken"))

        assert service.find("task-1") is None
        assert service._updates == {}

    asyncio.run(scenario())


def test_new_update_clears_immediately_and_late_probe_cannot_replace_it() -> None:
    async def scenario() -> None:
        old = PendingProbe(_recognized("D:/old"), asyncio.Event(), asyncio.Event())
        new = PendingProbe(_recognized("D:/new"), asyncio.Event(), asyncio.Event())
        service = WorkspaceContextService(ControlledSetup({"D:/old": old, "D:/new": new}))

        old_task = asyncio.create_task(service.update("task-1", SetupRequest(project_dir="D:/old")))
        await old.started.wait()
        assert service.find("task-1") is None

        new_task = asyncio.create_task(service.update("task-1", SetupRequest(project_dir="D:/new")))
        await new.started.wait()
        new.release.set()
        await new_task
        snapshot = service.find("task-1")
        assert snapshot is not None
        assert snapshot.project_path == "D:/new"

        old.release.set()
        await old_task
        snapshot = service.find("task-1")
        assert snapshot is not None
        assert snapshot.project_path == "D:/new"

    asyncio.run(scenario())


def test_finalization_clear_and_close_block_late_publication() -> None:
    async def scenario() -> None:
        probe = PendingProbe(_recognized("D:/game"), asyncio.Event(), asyncio.Event())
        service = WorkspaceContextService(ControlledSetup({"D:/game": probe}))
        task = asyncio.create_task(service.update("task-1", SetupRequest(project_dir="D:/game")))
        await probe.started.wait()

        service.clear("task-1")
        probe.release.set()
        await task
        assert service.find("task-1") is None

        closing_probe = PendingProbe(_recognized("D:/closing"), asyncio.Event(), asyncio.Event())
        closing_service = WorkspaceContextService(ControlledSetup({"D:/closing": closing_probe}))
        closing_task = asyncio.create_task(
            closing_service.update("task-1", SetupRequest(project_dir="D:/closing"))
        )
        await closing_probe.started.wait()
        closing_service.close()
        closing_probe.release.set()
        await closing_task
        assert closing_service.find("task-1") is None
        with pytest.raises(RuntimeError, match="closed"):
            await closing_service.update("task-1", SetupRequest(project_dir="D:/closing"))

    asyncio.run(scenario())


def test_owner_validation_matches_the_live_session_boundary() -> None:
    service = WorkspaceContextService(ImmediateSetup())

    with pytest.raises(ValueError):
        service.find("task\nother")
