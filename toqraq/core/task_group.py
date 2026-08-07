"""Session-scoped ownership for asynchronous background work."""

from __future__ import annotations

import asyncio
import logging
import math
import threading
from collections.abc import Coroutine
from typing import Any

from .failure_diagnostics import failure_diagnostic
from .tasks import wait_owned_tasks
from .trace import error_trace_id

DEFAULT_TASK_GROUP_CLOSE_SECONDS = 15.0
MAX_TASK_GROUP_CLOSE_SECONDS = 300.0
MAX_TASK_NAME_CHARACTERS = 128

logger = logging.getLogger(__name__)


class OwnedTaskGroup:
    """Strongly own, observe, cancel, and boundedly settle one run's tasks."""

    __slots__ = ("_close_timeout", "_lock", "_sealed", "_tasks")

    def __init__(self, close_timeout_seconds: float = DEFAULT_TASK_GROUP_CLOSE_SECONDS) -> None:
        """Create one open owner with a bounded cross-event-loop close wait."""
        if (
            isinstance(close_timeout_seconds, bool)
            or not isinstance(close_timeout_seconds, int | float)
            or not math.isfinite(close_timeout_seconds)
            or not 0 < close_timeout_seconds <= MAX_TASK_GROUP_CLOSE_SECONDS
        ):
            raise ValueError("task group close timeout is invalid")
        self._close_timeout = float(close_timeout_seconds)
        self._lock = threading.RLock()
        self._tasks: set[asyncio.Task[Any]] = set()
        self._sealed = False

    @property
    def empty(self) -> bool:
        """Return whether no unfinished task remains owned."""
        with self._lock:
            return not self._tasks

    @property
    def sealed(self) -> bool:
        """Return whether cleanup permanently ended task admission."""
        with self._lock:
            return self._sealed

    def create(self, operation: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task[Any]:
        """Schedule one named coroutine and retain it until observed completion."""
        if not isinstance(operation, Coroutine):
            raise ValueError("owned task operation is invalid")
        if not isinstance(name, str) or not name or len(name) > MAX_TASK_NAME_CHARACTERS:
            operation.close()
            raise ValueError("owned task name is invalid")
        with self._lock:
            if self._sealed:
                operation.close()
                raise ValueError("owned task group is sealed")
            task = asyncio.create_task(operation, name=name)
            self._tasks.add(task)
        task.add_done_callback(self._observe)
        return task

    async def close(
        self,
        *,
        cleanup_initiator: asyncio.Task[Any] | None = None,
    ) -> None:
        """Seal admission and settle tasks not driving this cleanup attempt."""
        if cleanup_initiator is not None and not isinstance(cleanup_initiator, asyncio.Task):
            raise ValueError("task group cleanup initiator is invalid")
        current = asyncio.current_task()
        with self._lock:
            self._sealed = True
            self._tasks.discard(current)
            self._tasks.discard(cleanup_initiator)
            tasks = tuple(self._tasks)
        await wait_owned_tasks(tasks, cancel=True, timeout=self._close_timeout)
        with self._lock:
            self._tasks.difference_update(task for task in tasks if task.done())

    def _observe(self, task: asyncio.Task[Any]) -> None:
        """Release completed ownership and log every unexpected failure once."""
        with self._lock:
            self._tasks.discard(task)
        if task.cancelled():
            return
        failure = task.exception()
        if failure is None:
            return
        diagnostic = failure_diagnostic(failure)
        logger.error(
            "unexpected session task failure trace_id=%s exception_type=%s stack_locations=%s",
            error_trace_id(),
            diagnostic.exception_type,
            ",".join(diagnostic.stack_locations),
        )
