"""Cross-event-loop serialization for one Hermes session's mutations."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from types import TracebackType

from ..core.bridge import validate_bridge_session_id
from ..core.errors import SessionStateError

DEFAULT_MAX_SESSION_OPERATIONS = 64


@dataclass(slots=True)
class _OperationNode:
    """One FIFO position whose completion releases exactly one successor."""

    session_id: str
    completion: Future[None]
    finished: bool = False


class SessionOperationLease:
    """Idempotent ownership token for one admitted session mutation."""

    __slots__ = ("_gate", "_node")

    def __init__(self, gate: SessionOperationGate, node: _OperationNode) -> None:
        """Retain the gate position until the mutation leaves its scope."""
        self._gate = gate
        self._node: _OperationNode | None = node

    async def __aenter__(self) -> SessionOperationLease:
        """Return the already-acquired lease."""
        return self

    async def __aexit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Release the FIFO position on every scope exit."""
        self.close()

    def close(self) -> None:
        """Release this mutation position exactly once."""
        node = self._node
        if node is None:
            return
        self._node = None
        self._gate._finish(node)


class SessionOperationGate:
    """Serialize one session's mutations without coupling unrelated sessions."""

    __slots__ = ("_counts", "_lock", "_maximum", "_tails")

    def __init__(
        self,
        maximum_operations_per_session: int = DEFAULT_MAX_SESSION_OPERATIONS,
    ) -> None:
        """Create a bounded process-local FIFO shared by every host event loop."""
        if (
            isinstance(maximum_operations_per_session, bool)
            or not isinstance(maximum_operations_per_session, int)
            or maximum_operations_per_session < 1
        ):
            raise ValueError("session operation bound is invalid")
        self._maximum = maximum_operations_per_session
        self._lock = threading.Lock()
        self._tails: dict[str, Future[None]] = {}
        self._counts: dict[str, int] = {}

    async def acquire(self, session_id: str) -> SessionOperationLease:
        """Wait for prior ownership without letting cancellation open the gate."""
        validate_bridge_session_id(session_id)
        completion: Future[None] = Future()
        node = _OperationNode(session_id=session_id, completion=completion)
        with self._lock:
            count = self._counts.get(session_id, 0)
            if count >= self._maximum:
                raise SessionStateError(
                    parameters={"session_id": session_id},
                    details={"reason": "operation_queue_full", "retryable": True},
                )
            predecessor = self._tails.get(session_id)
            self._tails[session_id] = completion
            self._counts[session_id] = count + 1

        if predecessor is not None:
            try:
                await asyncio.shield(asyncio.wrap_future(predecessor))
            except asyncio.CancelledError:
                predecessor.add_done_callback(lambda _completed: self._finish(node))
                raise
        return SessionOperationLease(self, node)

    def _finish(self, node: _OperationNode) -> None:
        """Complete one queue position and remove its retained bookkeeping."""
        with self._lock:
            if node.finished:
                return
            node.finished = True
            count = self._counts[node.session_id] - 1
            if count:
                self._counts[node.session_id] = count
            else:
                del self._counts[node.session_id]
            if self._tails.get(node.session_id) is node.completion:
                del self._tails[node.session_id]
        node.completion.set_result(None)
