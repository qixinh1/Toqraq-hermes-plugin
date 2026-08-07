"""Pending-start transfer and retryable run-resource ownership tests."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest
from toqraq.core.bridge import BridgeOwnerKey
from toqraq.core.engine_contribution import ProjectDescription
from toqraq.core.pending_start import PendingStart
from toqraq.core.run_resources import GameRunResources, RunCleanupPolicy

from _run_ownership_support import (
    CREDENTIAL,
    POLICY,
    Connection,
    PreviewAttachment,
    ProcessTree,
    RuntimeResource,
    bootstrap,
    complete_pending,
    promote,
    runtime,
)


def test_pending_start_retains_owner_after_consuming_private_bootstrap() -> None:
    pending = PendingStart(bootstrap(), POLICY)

    value = pending.take_bootstrap()

    assert pending.owner.session_id == "hermes-session"
    assert pending.owner.run_revision == 7
    assert CREDENTIAL not in repr(pending)
    assert CREDENTIAL not in repr(value)
    with pytest.raises(ValueError, match="consumed"):
        pending.take_bootstrap()


@pytest.mark.parametrize("value", [True, -1, float("nan"), 301])
def test_cleanup_policy_rejects_invalid_bounds(value: float) -> None:
    with pytest.raises(ValueError, match="timeout"):
        RunCleanupPolicy(
            graceful_timeout_seconds=value,
            forced_timeout_seconds=0,
        )


def test_resource_acquisition_is_single_and_cleanup_seals_owner(tmp_path: Path) -> None:
    async def run() -> None:
        order: list[str] = []
        resource = RuntimeResource(order)
        prepared_runtime = runtime(tmp_path, resource)
        resources = GameRunResources(POLICY)
        resources.retain_runtime(prepared_runtime)

        with pytest.raises(ValueError, match="already owned"):
            resources.retain_runtime(prepared_runtime)
        await resources.close()

        assert resources.empty
        assert resources.sealed
        with pytest.raises(ValueError, match="sealed"):
            resources.retain_connection(Connection(order))

    asyncio.run(run())


def test_pending_start_rejects_connection_owned_by_another_run() -> None:
    pending = PendingStart(bootstrap(), POLICY)
    connection = Connection(
        [],
        owner=BridgeOwnerKey(session_id="hermes-session", run_revision=8),
    )

    with pytest.raises(ValueError, match="owner differs"):
        pending.retain_connection(connection)

    assert pending.resources.connection is connection
    asyncio.run(pending.close())


def test_promotion_rejects_incomplete_or_already_exited_run(tmp_path: Path) -> None:
    pending = PendingStart(bootstrap(), POLICY)
    pending.take_bootstrap()
    with pytest.raises(ValueError, match="not promotable"):
        promote(pending, tmp_path)
    asyncio.run(pending.close())

    pending, process, _connection, _resource, _order = complete_pending(tmp_path)
    process.exit(2)
    with pytest.raises(ValueError, match="not running"):
        promote(pending, tmp_path)
    asyncio.run(pending.close())


def test_promotion_transfers_one_complete_live_owner(tmp_path: Path) -> None:
    async def run() -> None:
        pending, process, connection, resource, order = complete_pending(tmp_path)

        resources = promote(pending, tmp_path)
        await pending.close()

        assert resources.process_tree is process
        assert resources.connection is connection
        assert resources.runtime is not None
        assert resources.cancellation is pending.cancellation
        with pytest.raises(ValueError, match="transferred"):
            _ = pending.resources
        await resources.close()
        assert resources.empty
        assert resources.process_exit_code == 0
        assert order == ["process", "connection", "runtime"]
        assert resource.close_count == 1

    asyncio.run(run())


def test_failed_session_construction_leaves_pending_owner_intact(tmp_path: Path) -> None:
    pending, process, connection, resource, _order = complete_pending(tmp_path)
    mismatched = ProjectDescription(
        engine_id="unity",
        project_root=tmp_path,
        marker_path=tmp_path / "ProjectSettings" / "ProjectVersion.txt",
        confidence=100,
    )

    with pytest.raises(ValueError, match="engines differ"):
        pending.promote(project=mismatched, started_at=1.0)

    assert pending.resources.process_tree is process
    assert pending.resources.connection is connection
    assert pending.resources.runtime is not None
    asyncio.run(pending.close())
    assert resource.close_count == 1


def test_cleanup_cancels_owned_tasks_before_their_process_and_bridge(tmp_path: Path) -> None:
    """Readiness work releases before every native prerequisite it can access."""

    async def run() -> None:
        pending, _process, _connection, _resource, order = complete_pending(tmp_path)
        resources = promote(pending, tmp_path)
        started = asyncio.Event()

        async def readiness() -> None:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                order.append("task")

        resources.tasks.create(readiness(), name="readiness")
        await started.wait()
        await resources.close()

        assert resources.cancellation.is_set()
        assert order == ["task", "process", "connection", "runtime"]

    asyncio.run(run())


def test_preview_mutation_is_restored_before_process_termination(tmp_path: Path) -> None:
    async def run() -> None:
        pending, _process, _connection, _resource, order = complete_pending(tmp_path)
        resources = promote(pending, tmp_path)
        attachment = PreviewAttachment(order)
        resources.retain_preview_attachment(attachment)

        await resources.close()

        assert resources.preview_attachment is None
        assert attachment.close_count == 1
        assert order == ["preview", "process", "connection", "runtime"]

    asyncio.run(run())


def test_failed_preview_restoration_remains_owned_for_cleanup_retry(tmp_path: Path) -> None:
    async def run() -> None:
        pending, _process, _connection, _resource, order = complete_pending(tmp_path)
        resources = promote(pending, tmp_path)
        attachment = PreviewAttachment(order, failures=1)
        resources.retain_preview_attachment(attachment)

        with pytest.raises(ExceptionGroup):
            await resources.close()

        assert resources.preview_attachment is attachment
        assert not resources.empty
        await resources.close()
        assert resources.empty
        assert attachment.close_count == 2
        assert order == ["preview", "process", "connection", "runtime", "preview"]

    asyncio.run(run())


def test_failed_process_cleanup_retains_runtime_lease_for_retry(tmp_path: Path) -> None:
    async def run() -> None:
        pending, process, connection, resource, order = complete_pending(
            tmp_path,
            process_failures=1,
        )
        resources = promote(pending, tmp_path)

        with pytest.raises(ExceptionGroup):
            await resources.close()

        assert resources.process_tree is process
        assert resources.connection is None
        assert resources.runtime is not None
        assert resource.close_count == 0
        with pytest.raises(ValueError, match="sealed"):
            resources.retain_connection(connection)

        await resources.close()
        assert resources.empty
        assert order == ["process", "connection", "process", "runtime"]

    asyncio.run(run())


def test_unobservable_process_exit_retains_owner_and_prerequisites(tmp_path: Path) -> None:
    async def run() -> None:
        order: list[str] = []
        process = ProcessTree(order, observable_after_close=False)
        connection = Connection(order)
        resource = RuntimeResource(order)
        resources = GameRunResources(POLICY)
        resources.retain_runtime(runtime(tmp_path, resource))
        resources.retain_connection(connection)
        resources.retain_process_tree(process)

        with pytest.raises(ExceptionGroup) as captured:
            await resources.close()

        assert any(
            "runtime.termination_failed" in str(error) for error in captured.value.exceptions
        )
        assert resources.process_tree is process
        assert resources.connection is None
        assert resources.runtime is not None
        assert resources.process_exit_code is None
        assert resource.close_count == 0

    asyncio.run(run())


def test_independent_cleanup_failures_remain_owned_until_retry(tmp_path: Path) -> None:
    async def run() -> None:
        pending, _process, connection, resource, _order = complete_pending(
            tmp_path,
            connection_failures=1,
            runtime_failures=1,
        )
        resources = promote(pending, tmp_path)

        with pytest.raises(ExceptionGroup) as captured:
            await resources.close()
        assert len(captured.value.exceptions) == 2
        assert resources.process_tree is None
        assert resources.connection is connection
        assert resources.runtime is not None

        await resources.close()
        assert resources.empty
        assert connection.close_count == 2
        assert resource.close_count == 2

    asyncio.run(run())


def test_cancelling_waiter_does_not_interrupt_resource_cleanup(tmp_path: Path) -> None:
    async def run() -> None:
        order: list[str] = []
        started = threading.Event()
        release = threading.Event()
        process = ProcessTree(order, started=started, release=release)
        connection = Connection(order)
        resource = RuntimeResource(order)
        resources = GameRunResources(POLICY)
        resources.retain_runtime(runtime(tmp_path, resource))
        resources.retain_connection(connection)
        resources.retain_process_tree(process)

        cleanup = asyncio.create_task(resources.close())
        assert await asyncio.to_thread(started.wait, 2)
        cleanup.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await cleanup

        assert resources.empty
        assert order == ["process", "connection", "runtime"]

    asyncio.run(run())


def test_cleanup_runs_async_resources_on_their_acquisition_loop(tmp_path: Path) -> None:
    created = threading.Event()
    release_owner = threading.Event()
    failures: list[BaseException] = []
    owned: list[tuple[GameRunResources, list[str]]] = []
    owner_thread_ids: list[int] = []

    def owner_surface() -> None:
        async def run() -> None:
            pending, _process, _connection, _resource, order = complete_pending(tmp_path)
            owned.append((promote(pending, tmp_path), order))
            owner_thread_ids.append(threading.get_ident())
            created.set()
            assert await asyncio.to_thread(release_owner.wait, 2)

        try:
            asyncio.run(run())
        except BaseException as exc:
            failures.append(exc)

    owner = threading.Thread(target=owner_surface)
    owner.start()
    assert created.wait(timeout=1)

    resources, order = owned[0]

    async def probe_owner_loop() -> int:
        return threading.get_ident()

    assert asyncio.run(resources.invoke_owned(probe_owner_loop())) == owner_thread_ids[0]
    asyncio.run(resources.close())
    release_owner.set()
    owner.join(timeout=1)

    assert not owner.is_alive()
    assert failures == []
    assert resources.empty
    assert order == ["process", "connection", "runtime"]


def test_cancelled_pending_start_retains_late_acquisition_for_cleanup(tmp_path: Path) -> None:
    async def run() -> None:
        pending = PendingStart(bootstrap(), POLICY)
        pending.cancel()

        pending.retain_runtime(runtime(tmp_path, RuntimeResource([])))
        with pytest.raises(ValueError, match="not active"):
            pending.take_bootstrap()
        await pending.close()
        assert pending.resources.empty

    asyncio.run(run())
