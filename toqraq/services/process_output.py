"""Current-session process-output perception use case."""

from __future__ import annotations

from ..contracts.identifiers import HermesSessionId
from ..contracts.process_output import (
    MAX_PUBLIC_PROCESS_OUTPUT_CHARACTERS,
    ProcessOutputResult,
)
from ..core.errors import SessionStateError
from ..core.process_tree import ProcessOutputChunk, ProcessOutputSnapshot
from ..core.session_registry import SessionRegistry
from .session_gate import SessionOperationGate


class ProcessOutputService:
    """Read one latest tail while the exact session process remains owned."""

    __slots__ = ("_gate", "_registry")

    def __init__(self, registry: SessionRegistry, gate: SessionOperationGate) -> None:
        """Share the exact registry and operation gate with session lifecycle."""
        if not isinstance(registry, SessionRegistry):
            raise ValueError("process output registry is invalid")
        if not isinstance(gate, SessionOperationGate):
            raise ValueError("process output session gate is invalid")
        self._registry = registry
        self._gate = gate

    async def read(self, session_id: HermesSessionId) -> ProcessOutputResult:
        """Snapshot and project the current owner's latest combined output tail."""
        lease = await self._gate.acquire(session_id)
        async with lease:
            session = self._registry.get(session_id)
            process_tree = session.resources.process_tree
            if process_tree is None:
                raise SessionStateError(
                    parameters={"session_id": session_id},
                    details={"reason": "process_owner_missing"},
                )
            return ProcessOutputResult.from_core(_public_tail(process_tree.output()))


def _public_tail(snapshot: ProcessOutputSnapshot) -> ProcessOutputSnapshot:
    """Keep the newest characters without changing stream or sequence identity."""
    if not isinstance(snapshot, ProcessOutputSnapshot):
        raise TypeError("process output snapshot is invalid")
    remaining = MAX_PUBLIC_PROCESS_OUTPUT_CHARACTERS
    projected: list[ProcessOutputChunk] = []
    truncated = snapshot.truncated
    for chunk in reversed(snapshot.chunks):
        if remaining == 0:
            truncated = True
            break
        text = chunk.text
        if len(text) > remaining:
            text = text[-remaining:]
            truncated = True
        projected.append(
            ProcessOutputChunk(sequence=chunk.sequence, stream=chunk.stream, text=text)
        )
        remaining -= len(text)
    projected.reverse()
    return ProcessOutputSnapshot(
        chunks=tuple(projected),
        next_sequence=snapshot.next_sequence,
        truncated=truncated,
        failed_streams=snapshot.failed_streams,
    )
