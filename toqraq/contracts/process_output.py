"""Strict public contract for one bounded process-output tail."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import BeforeValidator, Field, StringConstraints, model_validator

from ..core.process_tree import ProcessOutputChunk, ProcessOutputSnapshot, ProcessOutputStream
from .base import ContractModel, freeze_sequence
from .identifiers import MAX_JSON_INTEGER

MAX_PUBLIC_PROCESS_OUTPUT_CHARACTERS = 16 * 1024
MAX_PUBLIC_PROCESS_OUTPUT_CHUNKS = MAX_PUBLIC_PROCESS_OUTPUT_CHARACTERS
ProcessOutputStreamValue: TypeAlias = Literal["stdout", "stderr"]
ProcessOutputText: TypeAlias = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_PUBLIC_PROCESS_OUTPUT_CHARACTERS),
]


class ProcessOutputChunkValue(ContractModel):
    """One globally ordered piece of stdout or stderr text."""

    sequence: int = Field(ge=1, le=MAX_JSON_INTEGER)
    stream: ProcessOutputStreamValue
    text: ProcessOutputText

    @classmethod
    def from_core(cls, value: ProcessOutputChunk) -> ProcessOutputChunkValue:
        """Create one strict public chunk from its pure value."""
        return cls(sequence=value.sequence, stream=value.stream.value, text=value.text)


class ProcessOutputResult(ContractModel):
    """Latest bounded combined tail and its collection-loss state."""

    chunks: Annotated[
        tuple[ProcessOutputChunkValue, ...],
        BeforeValidator(freeze_sequence),
        Field(max_length=MAX_PUBLIC_PROCESS_OUTPUT_CHUNKS),
    ]
    next_sequence: int = Field(ge=1, le=MAX_JSON_INTEGER)
    truncated: bool
    failed_streams: Annotated[
        tuple[ProcessOutputStreamValue, ...],
        BeforeValidator(freeze_sequence),
        Field(max_length=2),
    ]

    @model_validator(mode="after")
    def validate_snapshot(self) -> ProcessOutputResult:
        """Require strict order, a bounded aggregate, and canonical stream state."""
        sequences = tuple(chunk.sequence for chunk in self.chunks)
        if sequences != tuple(sorted(set(sequences))):
            raise ValueError("process output chunks are not strictly sequenced")
        if sequences and sequences[-1] >= self.next_sequence:
            raise ValueError("process output next sequence does not follow its chunks")
        if sum(len(chunk.text) for chunk in self.chunks) > MAX_PUBLIC_PROCESS_OUTPUT_CHARACTERS:
            raise ValueError("process output character limit is exceeded")
        if self.failed_streams not in ((), ("stdout",), ("stderr",), ("stdout", "stderr")):
            raise ValueError("process output failed streams are not canonical")
        return self

    @classmethod
    def from_core(cls, value: ProcessOutputSnapshot) -> ProcessOutputResult:
        """Create one strict result from an already public-bounded snapshot."""
        return cls(
            chunks=tuple(ProcessOutputChunkValue.from_core(chunk) for chunk in value.chunks),
            next_sequence=value.next_sequence,
            truncated=value.truncated,
            failed_streams=tuple(
                stream.value for stream in ProcessOutputStream if stream in value.failed_streams
            ),
        )
