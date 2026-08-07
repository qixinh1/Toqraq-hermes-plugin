"""Immutable policy and mutable per-request state for controlled Bridge RPC."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from ..contracts.base import ContractModel
from ..contracts.bridge_rpc import BridgeRpcSuccessEnvelope
from ..core.errors import BridgeConnectionError, ProtocolError, ToqraqError
from .bridge_binary_transfer import BridgeBinaryAnnouncementDecoder
from .bridge_remote_error import BridgeRemoteError

_MAX_POLICY_SECONDS = 300.0
_MIN_POLICY_SECONDS = 0.001

BridgeResponseDecoder: TypeAlias = Callable[[BridgeRpcSuccessEnvelope], ContractModel]
BridgeRemoteErrorMapper: TypeAlias = Callable[[BridgeRemoteError], ToqraqError]


class BridgeDisconnectionKind(StrEnum):
    """Safe first cause that ended one controlled connection."""

    OWNER = "owner"
    REMOTE = "remote"
    PROTOCOL = "protocol"
    TRANSPORT = "transport"
    CANCELLATION_CONTROL = "cancellation_control"


@dataclass(frozen=True, slots=True, kw_only=True)
class BridgeDisconnection:
    """Observable terminal fact without a frame or native error string."""

    kind: BridgeDisconnectionKind


@dataclass(frozen=True, slots=True, kw_only=True)
class BridgeRpcPolicy:
    """Hard wall-clock bounds owned by the controlled connection."""

    work_timeout_seconds: float = 15.0
    maximum_work_timeout_seconds: float = 300.0
    send_timeout_seconds: float = 5.0
    cancellation_grace_seconds: float = 2.0
    close_timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        """Reject disabled, infinite, and contradictory bounds."""
        for value in (
            self.work_timeout_seconds,
            self.maximum_work_timeout_seconds,
            self.send_timeout_seconds,
            self.cancellation_grace_seconds,
            self.close_timeout_seconds,
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(value)
                or not _MIN_POLICY_SECONDS <= value <= _MAX_POLICY_SECONDS
            ):
                raise ValueError("bridge RPC timeout policy is invalid")
        if self.work_timeout_seconds > self.maximum_work_timeout_seconds:
            raise ValueError("bridge RPC work timeout policy is inconsistent")

    def validate_work_timeout(self, value: float | None) -> float:
        """Select one finite positive deadline no larger than policy allows."""
        selected = self.work_timeout_seconds if value is None else value
        if (
            isinstance(selected, bool)
            or not isinstance(selected, int | float)
            or not math.isfinite(selected)
            or not _MIN_POLICY_SECONDS <= selected <= self.maximum_work_timeout_seconds
        ):
            raise ValueError("bridge RPC work timeout is invalid")
        return float(selected)


@dataclass(slots=True)
class PendingBridgeRequest:
    """Exactly one issued ID, decoder, waiter, and deadline owner."""

    request_id: str
    decoder: BridgeResponseDecoder | None
    binary_decoder: BridgeBinaryAnnouncementDecoder | None
    map_remote_error: BridgeRemoteErrorMapper
    future: asyncio.Future[ContractModel]
    work: bool
    deadline: asyncio.TimerHandle | None = None
    send_task: asyncio.Task[None] | None = None
    cancel_task: asyncio.Task[None] | None = None
    dispatched: bool = False
    terminal: bool = False
    expired: bool = False


def reject_unmapped_remote_error(_failure: BridgeRemoteError) -> ToqraqError:
    """Fail closed unless a focused adapter declares an explicit mapping."""
    raise ProtocolError(details={"reason": "unmapped_remote_error"})


def copy_connection_failure(failure: BridgeConnectionError | None) -> BridgeConnectionError:
    """Give each waiter its own exception with one connection trace."""
    if failure is None:
        return BridgeConnectionError(details={"reason": "connection_closed"})
    if isinstance(failure, ProtocolError):
        return ProtocolError(
            parameters=failure.parameters,
            details=failure.details,
            trace_id=failure.trace_id,
        )
    return BridgeConnectionError(
        parameters=failure.parameters,
        details=failure.details,
        trace_id=failure.trace_id,
    )


def observe_pending_future(future: asyncio.Future[ContractModel]) -> None:
    """Retrieve an exception when caller cancellation orphaned a waiter."""
    if not future.cancelled():
        future.exception()


async def acquire_work_slot_or_termination(
    semaphore: asyncio.BoundedSemaphore,
    termination: asyncio.Event,
    *,
    expires_at: float,
) -> bool:
    """Wait for capacity while allowing connection close to wake the caller."""
    acquire_task = asyncio.create_task(semaphore.acquire())
    termination_task = asyncio.create_task(termination.wait())
    slot_transferred = False
    slot_released = False
    try:
        async with asyncio.timeout_at(expires_at):
            completed, _pending = await asyncio.wait(
                (acquire_task, termination_task),
                return_when=asyncio.FIRST_COMPLETED,
            )
        if termination.is_set():
            if acquire_task in completed and acquire_task.result():
                semaphore.release()
                slot_released = True
            return False
        slot_transferred = acquire_task.result()
        return slot_transferred
    finally:
        for task in (acquire_task, termination_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(acquire_task, termination_task, return_exceptions=True)
        if (
            not slot_transferred
            and not slot_released
            and acquire_task.done()
            and not acquire_task.cancelled()
            and acquire_task.exception() is None
            and acquire_task.result()
        ):
            semaphore.release()
