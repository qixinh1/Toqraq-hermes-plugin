"""Asynchronous managed-component ownership and contract tests."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable

import pytest
from toqraq.contracts.components import ComponentJobState
from toqraq.core.component import (
    ComponentJobAction,
    ComponentKind,
    ComponentLicense,
    ComponentReadiness,
    ComponentSource,
    ComponentWorkCancelledError,
    ComponentWorkPhase,
    ComponentWorkProgress,
    ManagedComponent,
)
from toqraq.core.errors import (
    ComponentDownloadError,
    ComponentJobLimitError,
    ComponentJobNotFoundError,
    ComponentOperationConflictError,
    ComponentOperationError,
    ComponentOperationTimeoutError,
    ComponentReleaseNotFoundError,
)
from toqraq.services.component_jobs import ComponentJobPolicy, ComponentJobService

_RELEASE_ID = "a" * 64
_OTHER_RELEASE_ID = "b" * 64
_OPERATION_IDS = tuple(f"00000000-0000-4000-8000-{index:012d}" for index in range(1, 20))


def _component(release_id: str = _RELEASE_ID) -> ManagedComponent:
    return ManagedComponent(
        release_id=release_id,
        component_id="engine.godot.windows-x86_64",
        kind=ComponentKind.ENGINE,
        label="Godot 4.5.1",
        version="4.5.1",
        build_id="toqraq.1",
        platform="windows",
        architecture="x86_64",
        package_bytes=50,
        installed_bytes=100,
        package_sha256="c" * 64,
        source=ComponentSource(
            publisher="Toqraq",
            package_url="https://downloads.example.test/godot.zip",
            provenance_url="https://source.example.test/godot",
        ),
        license=ComponentLicense(
            identifier="MIT",
            name="MIT License",
            url="https://licenses.example.test/mit",
            acceptance_required=False,
        ),
        authentication_required=False,
        capabilities=("preview.native", "runtime.inspect"),
        readiness=ComponentReadiness.MISSING,
        in_use=False,
    )


class FakeInventory:
    def __init__(self, *components: ManagedComponent) -> None:
        self.components = {item.release_id: item for item in components}

    def list_components(self) -> tuple[ManagedComponent, ...]:
        return tuple(self.components.values())

    def require_component(self, release_id: str) -> ManagedComponent:
        try:
            return self.components[release_id]
        except KeyError as exc:
            raise ComponentReleaseNotFoundError(parameters={"release_id": release_id}) from exc


class FakeMutations:
    def __init__(
        self,
        prepare: Callable[[threading.Event, Callable[[ComponentWorkProgress], None]], None]
        | None = None,
        remove: Callable[[threading.Event, Callable[[ComponentWorkProgress], None]], None]
        | None = None,
    ) -> None:
        self.prepare = prepare or (lambda _cancellation, _progress: None)
        self.remove = remove or (lambda _cancellation, _progress: None)
        self.calls: list[tuple[str, str]] = []

    def prepare_component(
        self,
        release_id: str,
        cancellation: threading.Event,
        progress: Callable[[ComponentWorkProgress], None],
    ) -> None:
        self.calls.append(("prepare", release_id))
        self.prepare(cancellation, progress)

    def remove_component(
        self,
        release_id: str,
        cancellation: threading.Event,
        progress: Callable[[ComponentWorkProgress], None],
    ) -> None:
        self.calls.append(("remove", release_id))
        self.remove(cancellation, progress)


def _service(
    mutations: FakeMutations,
    *components: ManagedComponent,
    max_active: int = 2,
    max_terminal: int = 4,
    shutdown_timeout: float = 1.0,
    operation_ids: tuple[str, ...] = _OPERATION_IDS,
) -> ComponentJobService:
    ids = iter(operation_ids)
    return ComponentJobService(
        FakeInventory(*(components or (_component(),))),
        mutations,
        mutations,
        ComponentJobPolicy(max_active, max_terminal, shutdown_timeout),
        operation_id_factory=lambda: next(ids),
    )


async def _wait_terminal(service: ComponentJobService, operation_id: str):
    for _ in range(200):
        snapshot = service.get_job(operation_id)
        if snapshot.state in {
            ComponentJobState.READY,
            ComponentJobState.FAILED,
            ComponentJobState.CANCELLED,
        }:
            return snapshot
        await asyncio.sleep(0.005)
    raise AssertionError("component job did not terminate")


def test_policy_rejects_boolean_zero_unbounded_and_nonfinite_values() -> None:
    for values in (
        (False, 1, 1.0),
        (1, 0, 1.0),
        (65, 1, 1.0),
        (1, 1_025, 1.0),
        (1, 1, float("inf")),
        (1, 1, 301.0),
    ):
        with pytest.raises(ValueError):
            ComponentJobPolicy(*values)


def test_inventory_is_translated_without_exposing_local_paths() -> None:
    async def scenario() -> None:
        service = _service(FakeMutations())
        payload = await service.list_components()
        assert payload.model_dump(mode="json") == {
            "releases": [
                {
                    "release_id": _RELEASE_ID,
                    "component_id": "engine.godot.windows-x86_64",
                    "kind": "engine",
                    "label": "Godot 4.5.1",
                    "version": "4.5.1",
                    "build_id": "toqraq.1",
                    "platform": "windows",
                    "architecture": "x86_64",
                    "package_bytes": 50,
                    "installed_bytes": 100,
                    "package_sha256": "c" * 64,
                    "source": {
                        "publisher": "Toqraq",
                        "package_url": "https://downloads.example.test/godot.zip",
                        "provenance_url": "https://source.example.test/godot",
                    },
                    "license": {
                        "identifier": "MIT",
                        "name": "MIT License",
                        "url": "https://licenses.example.test/mit",
                        "acceptance_required": False,
                    },
                    "authentication_required": False,
                    "capabilities": ["preview.native", "runtime.inspect"],
                    "readiness": "missing",
                    "in_use": False,
                }
            ]
        }

    asyncio.run(scenario())


def test_same_active_action_joins_and_opposite_action_conflicts() -> None:
    async def scenario() -> None:
        entered = threading.Event()
        release = threading.Event()

        def prepare(
            _cancellation: threading.Event,
            _progress: Callable[[ComponentWorkProgress], None],
        ) -> None:
            entered.set()
            assert release.wait(2)

        mutations = FakeMutations(prepare=prepare)
        service = _service(mutations)
        first = await service.start_job(_RELEASE_ID, ComponentJobAction.PREPARE)
        assert first.state is ComponentJobState.QUEUED
        assert await asyncio.to_thread(entered.wait, 1)
        joined = await service.start_job(_RELEASE_ID, ComponentJobAction.PREPARE)
        assert joined.operation_id == first.operation_id
        with pytest.raises(ComponentOperationConflictError):
            await service.start_job(_RELEASE_ID, ComponentJobAction.REMOVE)
        release.set()
        assert (await _wait_terminal(service, first.operation_id)).state is ComponentJobState.READY
        assert mutations.calls == [("prepare", _RELEASE_ID)]

    asyncio.run(scenario())


def test_progress_success_and_remove_use_action_specific_paths() -> None:
    async def scenario() -> None:
        def prepare(
            _cancellation: threading.Event,
            progress: Callable[[ComponentWorkProgress], None],
        ) -> None:
            progress(ComponentWorkProgress(ComponentWorkPhase.DOWNLOADING, 25, 50))
            progress(ComponentWorkProgress(ComponentWorkPhase.INSTALLING, 100, 100))
            progress(ComponentWorkProgress(ComponentWorkPhase.READY, 100, 100))

        def remove(
            _cancellation: threading.Event,
            progress: Callable[[ComponentWorkProgress], None],
        ) -> None:
            progress(ComponentWorkProgress(ComponentWorkPhase.REMOVING, 0, 0))

        mutations = FakeMutations(prepare=prepare, remove=remove)
        service = _service(mutations)
        prepared = await service.start_job(_RELEASE_ID, ComponentJobAction.PREPARE)
        result = await _wait_terminal(service, prepared.operation_id)
        assert (result.state, result.phase, result.completed_bytes, result.total_bytes) == (
            ComponentJobState.READY,
            ComponentWorkPhase.READY,
            100,
            100,
        )
        removed = await service.start_job(_RELEASE_ID, ComponentJobAction.REMOVE)
        result = await _wait_terminal(service, removed.operation_id)
        assert (result.state, result.completed_bytes, result.total_bytes) == (
            ComponentJobState.READY,
            0,
            0,
        )
        assert mutations.calls == [
            ("prepare", _RELEASE_ID),
            ("remove", _RELEASE_ID),
        ]

    asyncio.run(scenario())


def test_cancellation_before_commit_is_cancelled() -> None:
    async def scenario() -> None:
        entered = threading.Event()

        def prepare(
            cancellation: threading.Event,
            _progress: Callable[[ComponentWorkProgress], None],
        ) -> None:
            entered.set()
            assert cancellation.wait(2)
            raise ComponentWorkCancelledError

        service = _service(FakeMutations(prepare=prepare))
        started = await service.start_job(_RELEASE_ID, ComponentJobAction.PREPARE)
        assert await asyncio.to_thread(entered.wait, 1)
        cancelling = service.cancel_job(started.operation_id)
        assert cancelling.state is ComponentJobState.CANCELLING
        assert (await _wait_terminal(service, started.operation_id)).state is (
            ComponentJobState.CANCELLED
        )

    asyncio.run(scenario())


def test_success_after_cancellation_reports_committed_ready_state() -> None:
    async def scenario() -> None:
        entered = threading.Event()

        def prepare(
            cancellation: threading.Event,
            _progress: Callable[[ComponentWorkProgress], None],
        ) -> None:
            entered.set()
            assert cancellation.wait(2)

        service = _service(FakeMutations(prepare=prepare))
        started = await service.start_job(_RELEASE_ID, ComponentJobAction.PREPARE)
        assert await asyncio.to_thread(entered.wait, 1)
        service.cancel_job(started.operation_id)
        result = await _wait_terminal(service, started.operation_id)
        assert result.state is ComponentJobState.READY

    asyncio.run(scenario())


def test_application_and_unexpected_failures_become_safe_terminal_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        failures = iter(
            (
                ComponentDownloadError(details={"reason": "network"}),
                RuntimeError("private-token C:/private/project"),
            )
        )

        def prepare(
            _cancellation: threading.Event,
            _progress: Callable[[ComponentWorkProgress], None],
        ) -> None:
            raise next(failures)

        service = _service(FakeMutations(prepare=prepare))
        first = await service.start_job(_RELEASE_ID, ComponentJobAction.PREPARE)
        expected = await _wait_terminal(service, first.operation_id)
        assert expected.error is not None
        assert expected.error.code == "component.download_failed"
        second = await service.start_job(_RELEASE_ID, ComponentJobAction.PREPARE)
        unexpected = await _wait_terminal(service, second.operation_id)
        assert unexpected.error is not None
        assert unexpected.error.code == "internal.unexpected"
        serialized = str(unexpected.model_dump(mode="json")) + caplog.text
        assert "private-token" not in serialized
        assert "C:/private/project" not in serialized

    caplog.set_level(logging.ERROR)
    asyncio.run(scenario())


def test_capacity_retention_not_found_and_operation_identity_bounds() -> None:
    async def scenario() -> None:
        entered = threading.Event()
        release = threading.Event()

        def prepare(
            _cancellation: threading.Event,
            _progress: Callable[[ComponentWorkProgress], None],
        ) -> None:
            entered.set()
            assert release.wait(2)

        service = _service(
            FakeMutations(prepare=prepare),
            _component(),
            _component(_OTHER_RELEASE_ID),
            max_active=1,
            max_terminal=1,
        )
        first = await service.start_job(_RELEASE_ID, ComponentJobAction.PREPARE)
        assert await asyncio.to_thread(entered.wait, 1)
        with pytest.raises(ComponentJobLimitError):
            await service.start_job(_OTHER_RELEASE_ID, ComponentJobAction.PREPARE)
        release.set()
        await _wait_terminal(service, first.operation_id)
        second = await service.start_job(_OTHER_RELEASE_ID, ComponentJobAction.PREPARE)
        await _wait_terminal(service, second.operation_id)
        with pytest.raises(ComponentJobNotFoundError):
            service.get_job(first.operation_id)

        collision = _OPERATION_IDS[0]
        broken = _service(
            FakeMutations(),
            operation_ids=(collision,) * 9,
            max_terminal=4,
        )
        completed = await broken.start_job(_RELEASE_ID, ComponentJobAction.PREPARE)
        await _wait_terminal(broken, completed.operation_id)
        with pytest.raises(ComponentOperationError):
            await broken.start_job(_RELEASE_ID, ComponentJobAction.PREPARE)

    asyncio.run(scenario())


def test_close_requests_cancellation_and_retains_timed_out_worker() -> None:
    async def scenario() -> None:
        entered = threading.Event()
        release = threading.Event()

        def prepare(
            cancellation: threading.Event,
            _progress: Callable[[ComponentWorkProgress], None],
        ) -> None:
            entered.set()
            assert cancellation.wait(2)
            assert release.wait(2)

        service = _service(
            FakeMutations(prepare=prepare),
            shutdown_timeout=0.01,
        )
        started = await service.start_job(_RELEASE_ID, ComponentJobAction.PREPARE)
        assert await asyncio.to_thread(entered.wait, 1)
        with pytest.raises(ComponentOperationTimeoutError):
            await service.close()
        assert service.get_job(started.operation_id).state is ComponentJobState.CANCELLING
        release.set()
        assert (
            await _wait_terminal(service, started.operation_id)
        ).state is ComponentJobState.READY
        await service.close()

    asyncio.run(scenario())


def test_unknown_release_is_rejected_before_allocating_a_job() -> None:
    async def scenario() -> None:
        service = _service(FakeMutations())
        with pytest.raises(ComponentReleaseNotFoundError):
            await service.start_job(_OTHER_RELEASE_ID, ComponentJobAction.PREPARE)
        with pytest.raises(ComponentJobNotFoundError):
            service.cancel_job(_OPERATION_IDS[0])

    asyncio.run(scenario())
