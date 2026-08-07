"""Recovery reads for process-owned component jobs."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable

import pytest
from pydantic import ValidationError
from toqraq.contracts.components import (
    ComponentActiveJobsResult,
    ComponentJobState,
)
from toqraq.core.component import (
    ComponentJobAction,
    ComponentKind,
    ComponentLicense,
    ComponentReadiness,
    ComponentSource,
    ComponentWorkPhase,
    ComponentWorkProgress,
    ManagedComponent,
)
from toqraq.core.errors import ComponentReleaseNotFoundError
from toqraq.services.component_jobs import ComponentJobPolicy, ComponentJobService

_FIRST_RELEASE = "a" * 64
_SECOND_RELEASE = "b" * 64
_OPERATION_IDS = (
    "00000000-0000-4000-8000-000000000001",
    "00000000-0000-4000-8000-000000000002",
)


def _component(release_id: str) -> ManagedComponent:
    return ManagedComponent(
        release_id=release_id,
        component_id=f"engine.recovery-{release_id[0]}",
        kind=ComponentKind.ENGINE,
        label="Recovery engine",
        version="1.0",
        build_id="recovery.1",
        platform="windows",
        architecture="x86_64",
        package_bytes=10,
        installed_bytes=20,
        package_sha256="c" * 64,
        source=ComponentSource(
            publisher="Toqraq",
            package_url="https://downloads.example.test/runtime.zip",
            provenance_url="https://source.example.test/runtime",
        ),
        license=ComponentLicense(
            identifier="MIT",
            name="MIT License",
            url="https://licenses.example.test/mit",
            acceptance_required=False,
        ),
        authentication_required=False,
        capabilities=("runtime.launch",),
        readiness=ComponentReadiness.MISSING,
        in_use=False,
    )


class _Inventory:
    def __init__(self) -> None:
        self._components = {
            release_id: _component(release_id) for release_id in (_FIRST_RELEASE, _SECOND_RELEASE)
        }

    def list_components(self) -> tuple[ManagedComponent, ...]:
        return tuple(self._components.values())

    def require_component(self, release_id: str) -> ManagedComponent:
        try:
            return self._components[release_id]
        except KeyError as exc:
            raise ComponentReleaseNotFoundError(parameters={"release_id": release_id}) from exc


class _BlockingMutations:
    def __init__(self, release: threading.Event) -> None:
        self._release = release

    def prepare_component(
        self,
        _release_id: str,
        _cancellation: threading.Event,
        _progress: Callable[[ComponentWorkProgress], None],
    ) -> None:
        if not self._release.wait(2):
            raise AssertionError("test did not release component worker")

    def remove_component(
        self,
        release_id: str,
        cancellation: threading.Event,
        progress: Callable[[ComponentWorkProgress], None],
    ) -> None:
        self.prepare_component(release_id, cancellation, progress)


def _service(release: threading.Event) -> ComponentJobService:
    operation_ids = iter(_OPERATION_IDS)
    mutations = _BlockingMutations(release)
    return ComponentJobService(
        _Inventory(),
        mutations,
        mutations,
        ComponentJobPolicy(2, 2, 1.0),
        operation_id_factory=lambda: next(operation_ids),
    )


def test_active_job_snapshot_is_bounded_public_and_creation_ordered() -> None:
    async def scenario() -> None:
        release = threading.Event()
        service = _service(release)
        first = await service.start_job(_FIRST_RELEASE, ComponentJobAction.PREPARE)
        second = await service.start_job(_SECOND_RELEASE, ComponentJobAction.PREPARE)
        try:
            recovered = service.list_active_jobs()

            assert tuple(job.operation_id for job in recovered.jobs) == (
                first.operation_id,
                second.operation_id,
            )
            assert all(
                job.state
                in {
                    ComponentJobState.QUEUED,
                    ComponentJobState.RUNNING,
                    ComponentJobState.CANCELLING,
                }
                for job in recovered.jobs
            )
            assert set(recovered.model_dump(mode="json")) == {"jobs"}
            assert all(
                set(job)
                == {
                    "operation_id",
                    "release_id",
                    "component_id",
                    "action",
                    "state",
                    "phase",
                    "completed_bytes",
                    "total_bytes",
                    "revision",
                    "error",
                }
                for job in recovered.model_dump(mode="json")["jobs"]
            )
            duplicate_operation = recovered.jobs[1].model_copy(
                update={"operation_id": recovered.jobs[0].operation_id}
            )
            duplicate_release = recovered.jobs[1].model_copy(
                update={"release_id": recovered.jobs[0].release_id}
            )
            terminal = recovered.jobs[0].model_copy(
                update={
                    "state": ComponentJobState.READY,
                    "phase": ComponentWorkPhase.READY,
                }
            )
            with pytest.raises(ValidationError, match="operations must be unique"):
                ComponentActiveJobsResult(jobs=(recovered.jobs[0], duplicate_operation))
            with pytest.raises(ValidationError, match="releases must be unique"):
                ComponentActiveJobsResult(jobs=(recovered.jobs[0], duplicate_release))
            with pytest.raises(ValidationError, match="contains a terminal job"):
                ComponentActiveJobsResult(jobs=(terminal,))
        finally:
            release.set()
            await service.close()
        assert service.list_active_jobs().jobs == ()
        assert service.get_job(first.operation_id).state is ComponentJobState.READY

    asyncio.run(scenario())
