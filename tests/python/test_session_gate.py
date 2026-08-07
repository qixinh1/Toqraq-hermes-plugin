"""Cross-loop and cancellation tests for session-operation serialization."""

from __future__ import annotations

import asyncio
import threading

import pytest
from toqraq.core.errors import SessionStateError
from toqraq.services.session_gate import SessionOperationGate


def test_same_session_is_fifo_and_different_sessions_remain_parallel() -> None:
    """A session owner blocks only its own ordered successors."""

    async def scenario() -> None:
        gate = SessionOperationGate()
        owner = await gate.acquire("owner")
        entered: list[str] = []

        async def enter(session_id: str) -> None:
            async with await gate.acquire(session_id):
                entered.append(session_id)

        same = asyncio.create_task(enter("owner"))
        other = asyncio.create_task(enter("other"))
        await asyncio.wait_for(other, timeout=1)
        assert entered == ["other"]
        assert not same.done()

        owner.close()
        await asyncio.wait_for(same, timeout=1)
        assert entered == ["other", "owner"]

    asyncio.run(scenario())


def test_cancelled_waiter_preserves_the_fifo_barrier_for_its_successor() -> None:
    """Cancellation relays release only after the true predecessor leaves."""

    async def scenario() -> None:
        gate = SessionOperationGate()
        owner = await gate.acquire("owner")
        cancelled = asyncio.create_task(gate.acquire("owner"))
        await asyncio.sleep(0)
        successor = asyncio.create_task(gate.acquire("owner"))
        await asyncio.sleep(0)

        cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled
        assert not successor.done()

        owner.close()
        lease = await asyncio.wait_for(successor, timeout=1)
        lease.close()

    asyncio.run(scenario())


def test_queue_bound_rejects_work_without_disturbing_existing_owners() -> None:
    """An overload failure neither overwrites nor releases admitted positions."""

    async def scenario() -> None:
        gate = SessionOperationGate(maximum_operations_per_session=2)
        owner = await gate.acquire("owner")
        waiter = asyncio.create_task(gate.acquire("owner"))
        await asyncio.sleep(0)

        with pytest.raises(SessionStateError) as captured:
            await gate.acquire("owner")
        assert captured.value.details == {
            "reason": "operation_queue_full",
            "retryable": True,
        }
        assert not waiter.done()

        owner.close()
        lease = await asyncio.wait_for(waiter, timeout=1)
        lease.close()

    asyncio.run(scenario())


def test_gate_serializes_the_same_session_across_distinct_event_loops() -> None:
    """Two Hermes surfaces cannot mutate one owner concurrently."""
    gate = SessionOperationGate()
    first_entered = threading.Event()
    release_first = threading.Event()
    second_attempting = threading.Event()
    second_entered = threading.Event()
    failures: list[BaseException] = []

    def first_surface() -> None:
        async def run() -> None:
            async with await gate.acquire("shared"):
                first_entered.set()
                released = await asyncio.to_thread(release_first.wait, 1)
                assert released

        try:
            asyncio.run(run())
        except BaseException as exc:
            failures.append(exc)

    def second_surface() -> None:
        async def run() -> None:
            second_attempting.set()
            async with await gate.acquire("shared"):
                second_entered.set()

        try:
            asyncio.run(run())
        except BaseException as exc:
            failures.append(exc)

    first = threading.Thread(target=first_surface)
    second = threading.Thread(target=second_surface)
    first.start()
    assert first_entered.wait(timeout=1)
    second.start()
    assert second_attempting.wait(timeout=1)
    assert not second_entered.is_set()

    release_first.set()
    first.join(timeout=1)
    second.join(timeout=1)
    assert not first.is_alive()
    assert not second.is_alive()
    assert second_entered.is_set()
    assert failures == []
