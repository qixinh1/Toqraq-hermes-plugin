"""Bounded request identity, deadline, and waiter registry for Bridge RPC."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from ..contracts.base import ContractModel
from ..contracts.identifiers import MAX_JSON_INTEGER
from ..core.errors import BridgeConnectionError, ProtocolError
from .bridge_binary_transfer import BridgeBinaryAnnouncementDecoder
from .bridge_rpc_state import (
    BridgeRemoteErrorMapper,
    BridgeResponseDecoder,
    PendingBridgeRequest,
    acquire_work_slot_or_termination,
    copy_connection_failure,
    observe_pending_future,
)


class BridgeRequestRegistry:
    """Own issued IDs, work capacity, pending waiters, and deadline handles."""

    def __init__(
        self,
        *,
        maximum_work: int,
        termination: asyncio.Event,
        expire_work: Callable[[str], None],
    ) -> None:
        """Create one bounded registry before requests can be issued."""
        self._work_slots = asyncio.BoundedSemaphore(maximum_work)
        self._termination = termination
        self._expire_work = expire_work
        self._pending: dict[str, PendingBridgeRequest] = {}
        self._next_request_number = 1

    @property
    def count(self) -> int:
        """Return ordinary plus the optional cancellation control request."""
        return len(self._pending)

    async def acquire_work(self, *, expires_at: float) -> bool:
        """Wait for ordinary capacity or the connection termination signal."""
        return await acquire_work_slot_or_termination(
            self._work_slots,
            self._termination,
            expires_at=expires_at,
        )

    def release_unregistered_work(self) -> None:
        """Release capacity when request construction fails before registration."""
        self._work_slots.release()

    def issue_id(self) -> str:
        """Issue one exact, monotonically increasing, never-reused host ID."""
        if self._next_request_number > MAX_JSON_INTEGER:
            raise ProtocolError(details={"reason": "request_id_exhausted"})
        value = f"host-{self._next_request_number}"
        self._next_request_number += 1
        return value

    def register_work(
        self,
        *,
        request_id: str,
        decoder: BridgeResponseDecoder,
        map_remote_error: BridgeRemoteErrorMapper,
        expires_at: float,
    ) -> PendingBridgeRequest:
        """Register one ordinary waiter and its hard deadline."""
        pending = self._new_pending(
            request_id=request_id,
            decoder=decoder,
            binary_decoder=None,
            map_remote_error=map_remote_error,
            work=True,
        )
        pending.deadline = asyncio.get_running_loop().call_at(
            expires_at,
            self._expire_work,
            request_id,
        )
        return pending

    def register_binary_work(
        self,
        *,
        request_id: str,
        decoder: BridgeBinaryAnnouncementDecoder,
        map_remote_error: BridgeRemoteErrorMapper,
        expires_at: float,
    ) -> PendingBridgeRequest:
        """Register one work waiter whose success claims the next binary message."""
        pending = self._new_pending(
            request_id=request_id,
            decoder=None,
            binary_decoder=decoder,
            map_remote_error=map_remote_error,
            work=True,
        )
        pending.deadline = asyncio.get_running_loop().call_at(
            expires_at,
            self._expire_work,
            request_id,
        )
        return pending

    def register_control(
        self,
        *,
        request_id: str,
        decoder: BridgeResponseDecoder,
        map_remote_error: BridgeRemoteErrorMapper,
    ) -> PendingBridgeRequest:
        """Register the sole cancellation-control waiter without a work slot."""
        return self._new_pending(
            request_id=request_id,
            decoder=decoder,
            binary_decoder=None,
            map_remote_error=map_remote_error,
            work=False,
        )

    def find(self, request_id: str) -> PendingBridgeRequest | None:
        """Return the currently active owner for one exact host ID."""
        return self._pending.get(request_id)

    def complete(
        self,
        pending: PendingBridgeRequest,
        *,
        result: ContractModel | None = None,
        error: BaseException | None = None,
    ) -> bool:
        """Settle and release one registry owner exactly once."""
        if self._pending.get(pending.request_id) is not pending:
            return False
        del self._pending[pending.request_id]
        pending.terminal = True
        if pending.deadline is not None:
            pending.deadline.cancel()
            pending.deadline = None
        if pending.work:
            self._work_slots.release()
        if not pending.future.done():
            if error is not None:
                pending.future.set_exception(error)
            elif result is not None:
                pending.future.set_result(result)
            else:
                pending.future.set_exception(
                    BridgeConnectionError(details={"reason": "connection_closed"})
                )
        return True

    def fail_all(self, failure: BridgeConnectionError) -> None:
        """Settle every current owner once with one shared connection trace."""
        for pending in tuple(self._pending.values()):
            self.complete(pending, error=copy_connection_failure(failure))

    def _new_pending(
        self,
        *,
        request_id: str,
        decoder: BridgeResponseDecoder | None,
        binary_decoder: BridgeBinaryAnnouncementDecoder | None,
        map_remote_error: BridgeRemoteErrorMapper,
        work: bool,
    ) -> PendingBridgeRequest:
        """Create and publish one future before a peer response can arrive."""
        if (decoder is None) == (binary_decoder is None):
            raise TypeError("bridge request must own exactly one response decoder")
        if decoder is not None and not callable(decoder):
            raise TypeError("bridge response decoder is invalid")
        if binary_decoder is not None and not callable(binary_decoder):
            raise TypeError("bridge binary response decoder is invalid")
        if not callable(map_remote_error):
            raise TypeError("bridge remote error mapper is invalid")
        if request_id in self._pending:
            raise RuntimeError("bridge request ID was reused")
        future: asyncio.Future[ContractModel] = asyncio.get_running_loop().create_future()
        future.add_done_callback(observe_pending_future)
        pending = PendingBridgeRequest(
            request_id=request_id,
            decoder=decoder,
            binary_decoder=binary_decoder,
            map_remote_error=map_remote_error,
            future=future,
            work=work,
        )
        self._pending[request_id] = pending
        return pending
