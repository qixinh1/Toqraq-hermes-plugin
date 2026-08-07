"""Common retryable cleanup operations for session lifecycle owners."""

from __future__ import annotations

import asyncio
import contextlib

from ..contracts.events import SessionEventType
from ..contracts.sessions import SessionResult
from ..core.errors import SessionCleanupError, SessionStateError
from ..core.pending_start import PendingStart
from ..core.process_tree import ProcessTreeLauncher
from ..core.session import EngineSession
from ..core.session_registry import SessionRegistry
from .events import SessionEventStream


async def release_registered_session(
    session: EngineSession,
    *,
    registry: SessionRegistry,
    events: SessionEventStream,
    discard: bool,
    publish: bool,
) -> SessionResult:
    """Run common cleanup while retaining every failure in the registry."""
    try:
        await session.close()
    except BaseException as exc:
        error = SessionCleanupError(
            parameters={
                "session_id": session.owner.session_id,
                "run_revision": session.owner.run_revision,
            },
            details={"reason": "resources_remain_owned", "retryable": True},
            cause=exc,
        )
        events.publish_failed(SessionResult.from_snapshot(session.snapshot()), error)
        raise error from exc
    result = SessionResult.from_snapshot(session.snapshot())
    if discard and not registry.discard_if(session):
        raise SessionStateError(
            parameters={"session_id": session.owner.session_id},
            details={"reason": "released_session_not_current"},
        )
    if publish:
        events.publish(SessionEventType.STOPPED, result)
    return result


async def release_orphan_session(session: EngineSession) -> None:
    """Retry cleanup of one promoted run that never entered the registry."""
    try:
        await session.close()
    except BaseException as exc:
        raise SessionCleanupError(
            parameters={"session_id": session.owner.session_id},
            details={"reason": "orphan_resources_remain", "retryable": True},
            cause=exc,
        ) from exc


def pending_cleanup_error(
    pending: PendingStart,
    cause: BaseException,
) -> SessionCleanupError:
    """Translate retained failed-start cleanup into a stable application error."""
    return SessionCleanupError(
        parameters={
            "session_id": pending.owner.session_id,
            "run_revision": pending.owner.run_revision,
        },
        details={"reason": "pending_resources_remain", "retryable": True},
        cause=cause,
    )


def start_rollback_error(
    pending: PendingStart,
    primary: BaseException,
    cleanup: BaseException,
) -> SessionCleanupError:
    """Expose incomplete start rollback without losing either internal cause."""
    if isinstance(primary, Exception) and isinstance(cleanup, Exception):
        cause: BaseException = ExceptionGroup(
            "session start and rollback failed",
            [primary, cleanup],
        )
    else:
        cause = BaseExceptionGroup(
            "session start and rollback failed",
            [primary, cleanup],
        )
    return SessionCleanupError(
        parameters={
            "session_id": pending.owner.session_id,
            "run_revision": pending.owner.run_revision,
        },
        details={"reason": "start_rollback_incomplete", "retryable": True},
        cause=cause,
    )


async def close_process_launcher(launcher: ProcessTreeLauncher) -> None:
    """Finish blocking launcher cleanup before propagating caller cancellation."""
    task = asyncio.create_task(asyncio.to_thread(launcher.close))
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        with contextlib.suppress(Exception):
            await task
        raise
