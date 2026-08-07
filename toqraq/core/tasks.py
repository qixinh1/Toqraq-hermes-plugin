"""Cross-event-loop settlement for explicitly owned tasks."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Coroutine, Iterable
from typing import Any


async def wait_owned_tasks(
    tasks: Iterable[asyncio.Task[Any]],
    *,
    cancel: bool,
    timeout: float,
) -> None:
    """Settle tasks on their owning event loops within one deadline.

    A process-local plugin can receive work from more than one Hermes surface.
    A task must therefore be cancelled and awaited on the loop that created it,
    even when plugin disposal is initiated by another surface.

    Args:
        tasks: Strongly owned tasks to settle.
        cancel: Request cancellation before waiting.
        timeout: Maximum total wait in seconds.

    Raises:
        RuntimeError: If a pending task's owner loop is no longer running.
        TimeoutError: If any owner loop does not settle before the deadline.
    """
    pending = tuple(dict.fromkeys(task for task in tasks if not task.done()))
    if not pending:
        return
    current_loop = asyncio.get_running_loop()
    by_loop: dict[asyncio.AbstractEventLoop, list[asyncio.Task[Any]]] = defaultdict(list)
    for task in pending:
        by_loop[task.get_loop()].append(task)

    unavailable = [
        owner_loop
        for owner_loop in by_loop
        if owner_loop is not current_loop and not owner_loop.is_running()
    ]
    if unavailable:
        raise RuntimeError("an owned task event loop is not running")

    waits: list[asyncio.Future[Any] | Coroutine[Any, Any, None]] = []
    for owner_loop, owned in by_loop.items():
        operation = _wait_on_owner_loop(tuple(owned), cancel=cancel)
        if owner_loop is current_loop:
            waits.append(operation)
            continue
        submitted = asyncio.run_coroutine_threadsafe(operation, owner_loop)
        waits.append(asyncio.wrap_future(submitted))

    await asyncio.wait_for(asyncio.gather(*waits), timeout=timeout)


async def _wait_on_owner_loop(
    tasks: tuple[asyncio.Task[Any], ...],
    *,
    cancel: bool,
) -> None:
    """Settle one task group while running on its owner loop."""
    current = asyncio.current_task()
    owned = tuple(task for task in tasks if task is not current and not task.done())
    if cancel:
        for task in owned:
            task.cancel()
    if owned:
        waits = owned if cancel else tuple(asyncio.shield(task) for task in owned)
        await asyncio.gather(*waits, return_exceptions=True)
