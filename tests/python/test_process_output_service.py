"""Bounded current-owner process-output perception tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError
from toqraq.contracts.process_output import (
    MAX_PUBLIC_PROCESS_OUTPUT_CHARACTERS,
    ProcessOutputChunkValue,
    ProcessOutputResult,
)
from toqraq.core.process_tree import (
    ProcessOutputChunk,
    ProcessOutputSnapshot,
    ProcessOutputStream,
)
from toqraq.core.session_registry import SessionRegistry
from toqraq.services.process_output import ProcessOutputService
from toqraq.services.session_gate import SessionOperationGate

from _session_domain_support import make_session


def _snapshot(
    chunks: tuple[ProcessOutputChunk, ...] = (),
    *,
    truncated: bool = False,
    failed_streams: frozenset[ProcessOutputStream] = frozenset(),
) -> ProcessOutputSnapshot:
    """Build one valid source snapshot with its exact next sequence."""
    return ProcessOutputSnapshot(
        chunks=chunks,
        next_sequence=chunks[-1].sequence + 1 if chunks else 1,
        truncated=truncated,
        failed_streams=failed_streams,
    )


def test_read_keeps_latest_ordered_public_tail_and_collection_state(tmp_path: Path) -> None:
    async def run() -> None:
        registry = SessionRegistry()
        gate = SessionOperationGate()
        owner = registry.issue_owner("hermes-session")
        session, process, _connection, _ports, _lease = make_session(tmp_path, owner)
        source = _snapshot(
            (
                ProcessOutputChunk(
                    sequence=1,
                    stream=ProcessOutputStream.STDOUT,
                    text="discarded",
                ),
                ProcessOutputChunk(
                    sequence=2,
                    stream=ProcessOutputStream.STDERR,
                    text="x" * MAX_PUBLIC_PROCESS_OUTPUT_CHARACTERS,
                ),
                ProcessOutputChunk(
                    sequence=3,
                    stream=ProcessOutputStream.STDOUT,
                    text="end",
                ),
            ),
            failed_streams=frozenset((ProcessOutputStream.STDERR, ProcessOutputStream.STDOUT)),
        )
        process.output_snapshot = source
        assert registry.compare_and_swap(None, session)
        try:
            result = await ProcessOutputService(registry, gate).read("hermes-session")

            assert tuple(chunk.sequence for chunk in result.chunks) == (2, 3)
            assert result.chunks[0].stream == "stderr"
            assert result.chunks[0].text == "x" * (MAX_PUBLIC_PROCESS_OUTPUT_CHARACTERS - 3)
            assert result.chunks[1].text == "end"
            assert sum(len(chunk.text) for chunk in result.chunks) == (
                MAX_PUBLIC_PROCESS_OUTPUT_CHARACTERS
            )
            assert result.next_sequence == 4
            assert result.truncated is True
            assert result.failed_streams == ("stdout", "stderr")
        finally:
            await session.close()
            assert registry.discard_if(session)

    asyncio.run(run())


def test_read_waits_for_the_shared_session_gate_before_touching_process(
    tmp_path: Path,
) -> None:
    async def run() -> None:
        registry = SessionRegistry()
        gate = SessionOperationGate()
        owner = registry.issue_owner("hermes-session")
        session, process, _connection, _ports, _lease = make_session(tmp_path, owner)
        assert registry.compare_and_swap(None, session)
        lifecycle_lease = await gate.acquire("hermes-session")
        try:
            pending = asyncio.create_task(
                ProcessOutputService(registry, gate).read("hermes-session")
            )
            await asyncio.sleep(0)
            assert process.output_calls == 0
            lifecycle_lease.close()
            assert await pending == ProcessOutputResult(
                chunks=(),
                next_sequence=1,
                truncated=False,
                failed_streams=(),
            )
            assert process.output_calls == 1
        finally:
            lifecycle_lease.close()
            await session.close()
            assert registry.discard_if(session)

    asyncio.run(run())


def test_public_contract_rejects_oversized_or_noncanonical_snapshots() -> None:
    first = ProcessOutputChunkValue(sequence=1, stream="stdout", text="a")
    oversized = ProcessOutputChunkValue(
        sequence=2,
        stream="stderr",
        text="b" * MAX_PUBLIC_PROCESS_OUTPUT_CHARACTERS,
    )
    with pytest.raises(ValidationError):
        ProcessOutputResult(
            chunks=(first, oversized),
            next_sequence=3,
            truncated=True,
            failed_streams=(),
        )
    with pytest.raises(ValidationError):
        ProcessOutputResult(
            chunks=(),
            next_sequence=1,
            truncated=False,
            failed_streams=("stderr", "stdout"),
        )
