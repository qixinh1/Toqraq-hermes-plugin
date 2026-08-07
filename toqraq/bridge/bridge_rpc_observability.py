"""Payload-safe observation of asynchronous Bridge RPC ownership failures."""

from __future__ import annotations

import asyncio
import logging

from ..core.failure_diagnostics import failure_diagnostic
from ..core.trace import error_trace_id

logger = logging.getLogger(__name__)


def observe_bridge_ownership_task(task: asyncio.Task[None]) -> None:
    """Log only failure type and locations, never exception args or frame values."""
    if task.cancelled():
        return
    failure = task.exception()
    if failure is None:
        return
    observe_bridge_failure(failure)


def observe_bridge_failure(failure: BaseException) -> None:
    """Record one caught failure without formatting its arguments."""
    diagnostic = failure_diagnostic(failure)
    logger.error(
        "bridge RPC ownership failure trace_id=%s exception_type=%s stack_locations=%s",
        error_trace_id(),
        diagnostic.exception_type,
        ",".join(diagnostic.stack_locations),
    )
