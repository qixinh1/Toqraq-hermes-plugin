"""Focused tests for synchronized unfinished session-owner records."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from toqraq.core.bridge_launch import BridgeLaunchBootstrap
from toqraq.core.errors import SessionCleanupError, SessionStateError
from toqraq.core.run_resources import RunCleanupPolicy
from toqraq.core.session_capacity import MAX_CONCURRENT_GAME_SESSIONS
from toqraq.services.session_ownership import SessionOwnership

from _session_service_support import CREDENTIAL, make_fixture, make_transaction


def _ownership() -> SessionOwnership:
    return SessionOwnership(RunCleanupPolicy(graceful_timeout_seconds=0, forced_timeout_seconds=0))


def _bootstrap(session_id: str = "hermes-session") -> BridgeLaunchBootstrap:
    return BridgeLaunchBootstrap(
        credential=CREDENTIAL,
        session_id=session_id,
        run_revision=1,
    )


def test_finalization_cancels_and_settles_the_exact_pending_owner() -> None:
    async def scenario() -> None:
        ownership = _ownership()
        ownership.reserve_start("hermes-session")
        pending = ownership.create_pending(_bootstrap())

        ownership.finalize("hermes-session")

        assert pending.cancellation.is_set()
        with pytest.raises(SessionStateError) as captured:
            ownership.require_start_allowed("hermes-session")
        assert captured.value.details == {"reason": "session_finalized"}
        await ownership.retry_pending("hermes-session")
        assert not ownership.has_unsettled

    asyncio.run(scenario())


def test_orphan_cleanup_failure_remains_owned_until_the_next_attempt(tmp_path: Path) -> None:
    async def scenario() -> None:
        fixture = make_fixture(tmp_path, process_close_failures=1)
        transaction = make_transaction(fixture)
        await transaction.prepare()
        session = await transaction.launch(lambda: 100.0)
        ownership = _ownership()
        ownership.reserve_start("hermes-session")
        ownership.retain_orphan(session)

        with pytest.raises(SessionCleanupError):
            await ownership.release_orphan(session)

        assert ownership.has_unsettled
        assert fixture.launcher.processes[0].closed == 1
        assert await ownership.release_orphans("hermes-session") == []
        assert fixture.launcher.processes[0].closed == 2
        assert not ownership.has_unsettled

    asyncio.run(scenario())


def test_plugin_closure_seals_active_and_pending_session_ids() -> None:
    ownership = _ownership()
    ownership.reserve_start("pending")
    pending = ownership.create_pending(_bootstrap("pending"))

    ownership.begin_close(("active",))

    assert pending.cancellation.is_set()
    assert ownership.close_session_ids() == ("active", "pending")
    with pytest.raises(SessionStateError) as captured:
        ownership.require_start_allowed("new-session")
    assert captured.value.details == {"reason": "plugin_closing"}


def test_capacity_reservation_is_atomic_and_released_after_idle_cleanup() -> None:
    ownership = _ownership()
    barrier = Barrier(MAX_CONCURRENT_GAME_SESSIONS + 1)

    def reserve(index: int) -> bool:
        barrier.wait(timeout=2)
        try:
            ownership.reserve_start(f"session-{index}")
        except SessionStateError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_GAME_SESSIONS + 1) as executor:
        outcomes = tuple(executor.map(reserve, range(MAX_CONCURRENT_GAME_SESSIONS + 1)))

    assert outcomes.count(True) == MAX_CONCURRENT_GAME_SESSIONS
    assert outcomes.count(False) == 1
    for index, reserved in enumerate(outcomes):
        if reserved:
            ownership.release_if_idle(f"session-{index}", active=False)
    ownership.reserve_start("reused-slot")
