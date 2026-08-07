"""Session-scoped asynchronous task ownership tests."""

from __future__ import annotations

import asyncio
import threading

import pytest
from toqraq.core.task_group import OwnedTaskGroup


def test_group_strongly_owns_and_observes_completed_work() -> None:
    """A caller may discard a task reference without discarding its work."""

    async def scenario() -> None:
        group = OwnedTaskGroup()
        completed = asyncio.Event()

        async def work() -> None:
            completed.set()

        group.create(work(), name="complete")
        await asyncio.wait_for(completed.wait(), timeout=1)
        await asyncio.sleep(0)
        assert group.empty
        await group.close()
        assert group.sealed

    asyncio.run(scenario())


def test_close_cancels_and_settles_owned_work() -> None:
    """Cleanup returns only after the task's cancellation path finishes."""

    async def scenario() -> None:
        group = OwnedTaskGroup()
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def work() -> None:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        group.create(work(), name="cancel")
        await started.wait()
        await group.close()
        assert cancelled.is_set()
        assert group.empty

    asyncio.run(scenario())


def test_current_owned_task_can_drive_its_own_group_cleanup() -> None:
    """A natural-exit supervisor does not wait for itself to finish."""

    async def scenario() -> None:
        group = OwnedTaskGroup()
        cleaned = asyncio.Event()

        async def owner() -> None:
            await group.close()
            cleaned.set()

        task = group.create(owner(), name="self-cleanup")
        await asyncio.wait_for(task, timeout=1)
        assert cleaned.is_set()
        assert group.empty

    asyncio.run(scenario())


def test_cleanup_proxy_can_take_ownership_from_its_owned_initiator() -> None:
    """A retryable cleanup task may settle resources for its waiting supervisor."""

    async def scenario() -> None:
        group = OwnedTaskGroup()

        async def owner() -> None:
            initiator = asyncio.current_task()

            async def cleanup() -> None:
                await group.close(cleanup_initiator=initiator)

            await asyncio.create_task(cleanup())

        task = group.create(owner(), name="proxied-cleanup")
        await asyncio.wait_for(task, timeout=1)
        assert group.empty
        assert group.sealed

    asyncio.run(scenario())


def test_close_can_cancel_a_task_owned_by_another_running_event_loop() -> None:
    """Hermes surfaces may finalize work created on another loop."""
    group = OwnedTaskGroup()
    started = threading.Event()
    stopped = threading.Event()
    owner_failure: list[BaseException] = []

    def owner_surface() -> None:
        async def run() -> None:
            async def work() -> None:
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    stopped.set()

            group.create(work(), name="cross-loop")
            settled = await asyncio.to_thread(stopped.wait, 1)
            assert settled

        try:
            asyncio.run(run())
        except BaseException as exc:
            owner_failure.append(exc)

    owner = threading.Thread(target=owner_surface)
    owner.start()
    assert started.wait(timeout=1)
    asyncio.run(group.close())
    owner.join(timeout=1)
    assert not owner.is_alive()
    assert stopped.is_set()
    assert owner_failure == []
    assert group.empty


def test_rejected_task_is_closed_and_never_leaks_a_coroutine_warning() -> None:
    """Once sealed, the group rejects and disposes a transferred coroutine."""

    async def scenario() -> None:
        group = OwnedTaskGroup()
        await group.close()

        async def work() -> None:
            return None

        with pytest.raises(ValueError):
            group.create(work(), name="rejected")

    asyncio.run(scenario())
