"""Cancellation-safe acquisition transaction for one engine session start."""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from ..contracts.bridge_launch import encode_bridge_launch_bootstrap
from ..core.bridge import BRIDGE_CREDENTIAL_BYTES, BridgeHandshakeExpectation
from ..core.errors import ComponentReleaseInvalidError
from ..core.failure_diagnostics import failure_diagnostic
from ..core.pending_start import PendingStart
from ..core.process_tree import ProcessEnvironment, ProcessTreeLauncher
from ..core.project_runtime import ProjectRuntimeReady
from ..core.runtime_features import RuntimeFeatureConnectionFactory
from ..core.session import EngineSession
from ..core.trace import error_trace_id

T = TypeVar("T")
Clock = Callable[[], float]
logger = logging.getLogger(__name__)


def new_bridge_credential() -> str:
    """Return one canonical random 256-bit credential for a new run."""
    return secrets.token_hex(BRIDGE_CREDENTIAL_BYTES)


class SessionStartTransaction:
    """Acquire, validate, and promote one exact selected engine run."""

    __slots__ = (
        "_connection_factory",
        "_environment",
        "_expectation",
        "_launcher",
        "_pending",
        "_selection",
    )

    def __init__(
        self,
        *,
        selection: ProjectRuntimeReady,
        pending: PendingStart,
        expectation: BridgeHandshakeExpectation,
        connection_factory: RuntimeFeatureConnectionFactory,
        launcher: ProcessTreeLauncher,
        environment: ProcessEnvironment,
    ) -> None:
        """Bind the exact selection and every concrete external owner once."""
        if not isinstance(selection, ProjectRuntimeReady):
            raise ValueError("session start selection is invalid")
        if not isinstance(pending, PendingStart):
            raise ValueError("session pending owner is invalid")
        if not isinstance(expectation, BridgeHandshakeExpectation):
            raise ValueError("session Bridge expectation is invalid")
        if expectation.owner != pending.owner or expectation.release is not selection.release:
            raise ValueError("session start identities differ")
        if not isinstance(connection_factory, RuntimeFeatureConnectionFactory):
            raise ValueError("session feature connection factory is invalid")
        if not isinstance(launcher, ProcessTreeLauncher):
            raise ValueError("session process launcher is invalid")
        if not isinstance(environment, ProcessEnvironment):
            raise ValueError("session process environment is invalid")
        self._selection = selection
        self._pending = pending
        self._expectation = expectation
        self._connection_factory = connection_factory
        self._launcher = launcher
        self._environment = environment

    async def prepare(self) -> None:
        """Acquire the exact prepared runtime and bound listener before replacement."""
        resources = self._pending.resources
        if resources.runtime is not None or resources.connection is not None:
            raise ValueError("session start preparation already began")
        contribution = self._selection.contribution
        release = self._selection.release
        await _transfer_blocking(
            lambda: contribution.runtime_provisioner.prepare(
                release,
                self._pending.cancellation,
            ),
            pending=self._pending,
            retain=self._pending.retain_runtime,
        )
        runtime = resources.runtime
        if runtime is None or runtime.release is not release:
            raise ComponentReleaseInvalidError(
                parameters={"engine": contribution.engine_id},
                details={"reason": "runtime_release_substituted"},
            )
        await _transfer_async(
            self._connection_factory.open(self._expectation),
            pending=self._pending,
            retain=self._pending.retain_connection,
        )

    async def launch(self, clock: Clock) -> EngineSession:
        """Launch the prepared command and atomically transfer it into a session."""
        if not callable(clock):
            raise ValueError("session start clock is invalid")
        resources = self._pending.resources
        runtime = resources.runtime
        connection = resources.connection
        if runtime is None or connection is None or resources.process_tree is not None:
            raise ValueError("session start is not launchable")
        bootstrap = encode_bridge_launch_bootstrap(self._pending.take_bootstrap())
        command = self._selection.contribution.game_launch_planner.plan(
            self._selection.project,
            runtime,
            connection.endpoint,
            self._environment,
            bootstrap,
        )
        await _transfer_blocking(
            lambda: self._launcher.launch(command),
            pending=self._pending,
            retain=self._pending.retain_process_tree,
        )
        return self._pending.promote(
            project=self._selection.project,
            started_at=float(clock()),
        )

    async def close(self) -> None:
        """Cancel and retry release of every resource not promoted."""
        await self._pending.close()


async def _transfer_blocking(
    acquire: Callable[[], T],
    *,
    pending: PendingStart,
    retain: Callable[[T], None],
) -> None:
    """Settle a blocking acquisition before propagating caller cancellation."""
    task = asyncio.create_task(asyncio.to_thread(acquire))
    await _transfer_task(task, pending=pending, retain=retain)


async def _transfer_async(
    acquire: Coroutine[Any, Any, T],
    *,
    pending: PendingStart,
    retain: Callable[[T], None],
) -> None:
    """Settle an async acquisition before propagating caller cancellation."""
    task = asyncio.create_task(acquire)
    await _transfer_task(task, pending=pending, retain=retain)


async def _transfer_task(
    task: asyncio.Task[T],
    *,
    pending: PendingStart,
    retain: Callable[[T], None],
) -> None:
    """Transfer a completed result even when cancellation arrived first."""
    try:
        value = await asyncio.shield(task)
    except asyncio.CancelledError:
        pending.cancel()
        try:
            value = await _finish_task(task)
        except Exception as exc:
            _log_cancelled_acquisition_failure(exc)
        else:
            retain(value)
        raise
    retain(value)


async def _finish_task(task: asyncio.Task[T]) -> T:
    """Ignore repeated waiter cancellation until one acquisition is terminal."""
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    return task.result()


def _log_cancelled_acquisition_failure(exception: BaseException) -> None:
    """Observe a failed cancelled acquisition without formatting its message."""
    diagnostic = failure_diagnostic(exception)
    logger.error(
        "cancelled session acquisition failed trace_id=%s exception_type=%s stack_locations=%s",
        error_trace_id(),
        diagnostic.exception_type,
        ",".join(diagnostic.stack_locations),
    )
