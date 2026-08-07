"""Explicit ownership and retryable cleanup for one launched game run."""

from __future__ import annotations

import asyncio
import contextlib
import math
from collections.abc import Coroutine
from dataclasses import dataclass
from threading import Event
from typing import Any, TypeVar

from .errors import ProcessTerminationError
from .process_tree import ProcessTree
from .resource import AsyncResource
from .runtime import PreparedRuntime
from .runtime_features import RuntimeFeatureConnection
from .task_group import OwnedTaskGroup

DEFAULT_RUN_GRACEFUL_CLOSE_SECONDS = 5.0
DEFAULT_RUN_FORCED_CLOSE_SECONDS = 5.0
MAX_RUN_CLOSE_SECONDS = 300.0
T = TypeVar("T")


@dataclass(frozen=True, slots=True, kw_only=True)
class RunCleanupPolicy:
    """Bounds for graceful and forced process-tree release."""

    graceful_timeout_seconds: float = DEFAULT_RUN_GRACEFUL_CLOSE_SECONDS
    forced_timeout_seconds: float = DEFAULT_RUN_FORCED_CLOSE_SECONDS

    def __post_init__(self) -> None:
        """Reject disabled, non-finite, or unbounded cleanup waits."""
        for value in (self.graceful_timeout_seconds, self.forced_timeout_seconds):
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(value)
                or not 0 <= value <= MAX_RUN_CLOSE_SECONDS
            ):
                raise ValueError("run cleanup timeout is invalid")


class GameRunResources:
    """Own the exact runtime, bridge, and process tree for one game run."""

    __slots__ = (
        "_cancellation",
        "_cleanup_task",
        "_connection",
        "_owner_loop",
        "_policy",
        "_preview_attachment",
        "_process_exit_code",
        "_process_tree",
        "_runtime",
        "_sealed",
        "_tasks",
    )

    def __init__(
        self,
        policy: RunCleanupPolicy | None = None,
        cancellation: Event | None = None,
    ) -> None:
        """Create an empty owner before the first fallible acquisition."""
        selected = policy or RunCleanupPolicy()
        if not isinstance(selected, RunCleanupPolicy):
            raise ValueError("run cleanup policy is invalid")
        self._policy = selected
        self._cancellation = cancellation or Event()
        if not isinstance(self._cancellation, Event):
            raise ValueError("run cancellation owner is invalid")
        self._tasks = OwnedTaskGroup()
        try:
            self._owner_loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            self._owner_loop = None
        self._runtime: PreparedRuntime | None = None
        self._connection: RuntimeFeatureConnection | None = None
        self._process_tree: ProcessTree | None = None
        self._preview_attachment: AsyncResource | None = None
        self._process_exit_code: int | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._sealed = False

    @property
    def runtime(self) -> PreparedRuntime | None:
        """Return the exact prepared runtime while it remains owned."""
        return self._runtime

    @property
    def cancellation(self) -> Event:
        """Return the event shared by acquisitions and readiness tasks."""
        return self._cancellation

    @property
    def tasks(self) -> OwnedTaskGroup:
        """Return the run-scoped strong owner for asynchronous work."""
        return self._tasks

    @property
    def connection(self) -> RuntimeFeatureConnection | None:
        """Return the transport-hidden runtime bridge while it remains owned."""
        return self._connection

    @property
    def process_tree(self) -> ProcessTree | None:
        """Return the complete process tree while it remains owned."""
        return self._process_tree

    @property
    def process_exit_code(self) -> int | None:
        """Return the terminal result captured before process ownership release."""
        return self._process_exit_code

    @property
    def preview_attachment(self) -> AsyncResource | None:
        """Return the renderer-created preview mutation while it remains owned."""
        return self._preview_attachment

    @property
    def complete(self) -> bool:
        """Return whether all resources required for promotion are owned."""
        return all(
            resource is not None
            for resource in (self._runtime, self._connection, self._process_tree)
        )

    @property
    def empty(self) -> bool:
        """Return whether every acquired resource completed cleanup."""
        return self._tasks.empty and all(
            resource is None
            for resource in (
                self._runtime,
                self._connection,
                self._process_tree,
                self._preview_attachment,
            )
        )

    @property
    def sealed(self) -> bool:
        """Return whether cleanup permanently ended resource acquisition."""
        return self._sealed

    async def invoke_owned(self, operation: Coroutine[Any, Any, T]) -> T:
        """Run one borrowed async capability call on its acquisition loop."""
        if not isinstance(operation, Coroutine):
            raise ValueError("owned async operation is invalid")
        current_loop = asyncio.get_running_loop()
        owner_loop = self._owner_loop
        if owner_loop is None:
            self._owner_loop = current_loop
            owner_loop = current_loop
        if owner_loop is current_loop:
            return await operation
        if not owner_loop.is_running():
            operation.close()
            raise RuntimeError("run resource owner loop is not running")
        submitted = asyncio.run_coroutine_threadsafe(operation, owner_loop)
        waiter: asyncio.Future[T] = asyncio.wrap_future(submitted)
        try:
            return await waiter
        except asyncio.CancelledError:
            submitted.cancel()
            with contextlib.suppress(BaseException):
                await waiter
            raise

    def retain_runtime(self, runtime: PreparedRuntime) -> None:
        """Take the exact prepared runtime once."""
        if not isinstance(runtime, PreparedRuntime):
            raise ValueError("prepared runtime is invalid")
        if self._runtime is not None:
            raise ValueError("prepared runtime is already owned")
        self._require_mutable()
        self._runtime = runtime

    def retain_connection(self, connection: RuntimeFeatureConnection) -> None:
        """Take one transport-hidden feature connection once."""
        if not isinstance(connection, RuntimeFeatureConnection):
            raise ValueError("runtime feature connection is invalid")
        if self._connection is not None:
            raise ValueError("runtime feature connection is already owned")
        self._require_mutable()
        self._connection = connection

    def retain_process_tree(self, process_tree: ProcessTree) -> None:
        """Take one complete process tree once."""
        if not isinstance(process_tree, ProcessTree):
            raise ValueError("process tree is invalid")
        if self._process_tree is not None:
            raise ValueError("process tree is already owned")
        if self._process_exit_code is not None:
            raise ValueError("process tree terminal result is already retained")
        self._require_mutable()
        self._process_tree = process_tree

    def retain_preview_attachment(self, attachment: AsyncResource) -> None:
        """Take one post-launch preview mutation until explicit detach or run cleanup."""
        if not isinstance(attachment, AsyncResource):
            raise ValueError("preview attachment is invalid")
        if self._preview_attachment is not None:
            raise ValueError("preview attachment is already owned")
        self._require_mutable()
        self._preview_attachment = attachment

    async def close_preview_attachment(self) -> None:
        """Restore and release the current preview mutation, retaining failures."""
        attachment = self._preview_attachment
        if attachment is None:
            return
        await attachment.close()
        if self._preview_attachment is attachment:
            self._preview_attachment = None

    async def close(self) -> None:
        """Settle cleanup on the acquisition loop and retain every failed owner."""
        self._cancellation.set()
        current_loop = asyncio.get_running_loop()
        owner_loop = self._owner_loop
        if owner_loop is None:
            self._owner_loop = current_loop
            owner_loop = current_loop
        if owner_loop is current_loop:
            await self._close_on_owner_loop()
            return
        if not owner_loop.is_running():
            raise RuntimeError("run resource owner loop is not running")
        submitted = asyncio.run_coroutine_threadsafe(self._close_on_owner_loop(), owner_loop)
        waiter: asyncio.Future[None] = asyncio.wrap_future(submitted)
        try:
            await asyncio.shield(waiter)
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await waiter
            raise

    async def _close_on_owner_loop(self) -> None:
        """Run the shared cleanup task only where async resources were acquired."""
        self._sealed = True
        if self.empty:
            return
        task = self._cleanup_task
        if task is None:
            initiator = asyncio.current_task()
            task = asyncio.create_task(
                self._close_attempt(initiator),
                name="toqraq-run-cleanup",
            )
            self._cleanup_task = task
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await task
            raise
        finally:
            if task.done() and self._cleanup_task is task:
                self._cleanup_task = None

    async def _close_attempt(
        self,
        cleanup_initiator: asyncio.Task[Any] | None,
    ) -> None:
        """Release in dependency order while preserving failed fields."""
        failures: list[Exception] = []
        await self._close_tasks(cleanup_initiator, failures)

        try:
            await self.close_preview_attachment()
        except Exception as exc:
            failures.append(exc)

        await self._close_process_tree(failures)
        await self._close_connection(failures)
        await self._close_runtime(failures)

        if failures:
            raise ExceptionGroup("game run cleanup failed", failures)

    async def _close_tasks(
        self,
        cleanup_initiator: asyncio.Task[Any] | None,
        failures: list[Exception],
    ) -> None:
        """Drain asynchronous borrowers before releasing their resources."""
        try:
            await self._tasks.close(cleanup_initiator=cleanup_initiator)
        except Exception as exc:
            failures.append(exc)
        if not self._tasks.empty:
            if not failures:
                failures.append(RuntimeError("owned session tasks remain active"))
            raise ExceptionGroup("game run cleanup failed", failures)

    async def _close_process_tree(self, failures: list[Exception]) -> None:
        """Terminate one process tree and retain it until exit is observable."""
        process_tree = self._process_tree
        if process_tree is None:
            return
        try:
            await asyncio.to_thread(
                process_tree.close,
                graceful_timeout=self._policy.graceful_timeout_seconds,
                forced_timeout=self._policy.forced_timeout_seconds,
            )
        except Exception as exc:
            failures.append(exc)
            return
        exit_code = process_tree.poll()
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            failures.append(
                ProcessTerminationError(
                    details={
                        "reason": "process_exit_not_observable",
                        "retryable": True,
                    }
                )
            )
            return
        self._process_exit_code = exit_code
        self._process_tree = None

    async def _close_connection(self, failures: list[Exception]) -> None:
        """Close the Bridge owner and clear it only after confirmed release."""
        connection = self._connection
        if connection is None:
            return
        try:
            await connection.close()
        except Exception as exc:
            failures.append(exc)
        else:
            self._connection = None

    async def _close_runtime(self, failures: list[Exception]) -> None:
        """Release runtime leases only after the process no longer uses them."""
        runtime = self._runtime
        if runtime is None or self._process_tree is not None:
            return
        runtime_failures: list[Exception] = []
        for resource in reversed(runtime.owned_resources):
            try:
                await resource.close()
            except Exception as exc:
                runtime_failures.append(exc)
        if runtime_failures:
            failures.extend(runtime_failures)
        else:
            self._runtime = None

    def _require_mutable(self) -> None:
        """Reject acquisition after cleanup has begun."""
        if self._sealed:
            raise ValueError("run resources are sealed")
