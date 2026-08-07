"""Exact-release and cancellation ownership tests for a start transaction."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest
from toqraq.core.errors import ComponentReleaseInvalidError

from _session_service_support import make_fixture, make_transaction, runtime_release


def test_exact_catalog_release_flows_unchanged_through_launch_and_session(tmp_path: Path) -> None:
    async def scenario() -> None:
        fixture = make_fixture(tmp_path)
        transaction = make_transaction(fixture)

        await transaction.prepare()
        session = await transaction.launch(lambda: 123.5)

        assert fixture.provisioner.selected == [fixture.release]
        assert session.resources.runtime is not None
        assert session.resources.runtime.release is fixture.release
        assert fixture.planner.runtimes == [session.resources.runtime]
        assert fixture.planner.endpoints == [fixture.connections.connections[0].endpoint]
        assert session.snapshot().runtime_identity is fixture.release.identity
        await transaction.close()
        assert fixture.launcher.processes[0].closed == 0
        await session.close()
        assert fixture.launcher.processes[0].closed == 1
        assert fixture.connections.connections[0].closed == 1
        assert fixture.provisioner.leases[0].closed == 1

    asyncio.run(scenario())


def test_cancelled_blocking_prepare_retains_late_runtime_for_cleanup(tmp_path: Path) -> None:
    async def scenario() -> None:
        entered = threading.Event()
        unblock = threading.Event()
        fixture = make_fixture(tmp_path, provisioner_events=(entered, unblock))
        transaction = make_transaction(fixture)
        task = asyncio.create_task(transaction.prepare())
        assert await asyncio.to_thread(entered.wait, 1)

        task.cancel()
        unblock.set()
        with pytest.raises(asyncio.CancelledError):
            await task

        await transaction.close()
        assert fixture.provisioner.leases[0].closed == 1

    asyncio.run(scenario())


def test_cancelled_listener_open_retains_late_connection_for_cleanup(tmp_path: Path) -> None:
    async def scenario() -> None:
        entered = asyncio.Event()
        unblock = asyncio.Event()
        fixture = make_fixture(tmp_path, connection_events=(entered, unblock))
        transaction = make_transaction(fixture)
        task = asyncio.create_task(transaction.prepare())
        await entered.wait()

        task.cancel()
        unblock.set()
        with pytest.raises(asyncio.CancelledError):
            await task

        connection = fixture.connections.connections[0]
        await transaction.close()
        assert connection.closed == 1
        assert fixture.provisioner.leases[0].closed == 1

    asyncio.run(scenario())


def test_substituted_runtime_remains_owned_and_fails_closed(tmp_path: Path) -> None:
    async def scenario() -> None:
        selected = runtime_release()
        substituted = runtime_release()
        fixture = make_fixture(
            tmp_path,
            selected_release=selected,
            returned_release=substituted,
        )
        transaction = make_transaction(fixture)

        with pytest.raises(ComponentReleaseInvalidError) as captured:
            await transaction.prepare()

        assert captured.value.details == {"reason": "runtime_release_substituted"}
        await transaction.close()
        assert fixture.provisioner.leases[0].closed == 1

    asyncio.run(scenario())
