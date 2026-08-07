"""Bounded collector for sequenced Windows process output."""

from __future__ import annotations

import codecs
import math
import threading
from collections import deque
from dataclasses import dataclass
from typing import Protocol

from ...core.process_tree import (
    ProcessOutputChunk,
    ProcessOutputSnapshot,
    ProcessOutputStream,
)
from .process_ownership import OwnedHandle
from .process_types import NativeHandle


class ProcessPipeReader(Protocol):
    """Non-blocking read operation required by the collector."""

    def read_pipe(self, handle: NativeHandle, maximum_bytes: int) -> bytes | None:
        """Read available bytes, empty while idle, or None at EOF."""
        ...


@dataclass(slots=True)
class _StreamState:
    """One owned pipe and its incremental UTF-8 decoder."""

    handle: OwnedHandle
    decoder: codecs.IncrementalDecoder
    reading: bool = True


class WindowsProcessOutput:
    """Own two read handles and retain one bounded combined text tail."""

    def __init__(
        self,
        pipes: ProcessPipeReader,
        *,
        stdout_read: OwnedHandle,
        stderr_read: OwnedHandle,
        character_limit: int,
        read_size: int,
        idle_interval: float,
    ) -> None:
        """Receive both pipe owners before the reader thread exists."""
        if isinstance(character_limit, bool) or character_limit < 1:
            raise ValueError("process output character limit is invalid")
        if isinstance(read_size, bool) or read_size < 1:
            raise ValueError("process output read size is invalid")
        if (
            isinstance(idle_interval, bool)
            or not math.isfinite(idle_interval)
            or idle_interval <= 0
        ):
            raise ValueError("process output idle interval is invalid")
        self._pipes = pipes
        self._states = {
            ProcessOutputStream.STDOUT: _StreamState(
                stdout_read,
                codecs.getincrementaldecoder("utf-8")(errors="replace"),
            ),
            ProcessOutputStream.STDERR: _StreamState(
                stderr_read,
                codecs.getincrementaldecoder("utf-8")(errors="replace"),
            ),
        }
        self._character_limit = character_limit
        self._read_size = read_size
        self._idle_interval = idle_interval
        self._chunks: deque[ProcessOutputChunk] = deque()
        self._characters = 0
        self._next_sequence = 1
        self._truncated = False
        self._failed_streams: set[ProcessOutputStream] = set()
        self._state_lock = threading.RLock()
        self._close_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="toqraq-process-output",
            daemon=True,
        )
        self._started = False

    def start(self) -> None:
        """Start collection exactly once."""
        with self._state_lock:
            if self._started:
                raise RuntimeError("process output collector already started")
            self._thread.start()
            self._started = True

    def snapshot(self) -> ProcessOutputSnapshot:
        """Return an immutable point-in-time view of the bounded tail."""
        with self._state_lock:
            return ProcessOutputSnapshot(
                chunks=tuple(self._chunks),
                next_sequence=self._next_sequence,
                truncated=self._truncated,
                failed_streams=frozenset(self._failed_streams),
            )

    def close(self, timeout: float, *, drain: bool) -> None:
        """Drain ended writers or abort collection, then close owned pipes."""
        if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout < 0:
            raise ValueError("process output close timeout is invalid")
        with self._close_lock:
            if not drain:
                self._stop.set()
            if self._started:
                self._thread.join(timeout)
                if self._thread.is_alive():
                    raise TimeoutError("process output collector did not stop")
            first_failure: OSError | None = None
            with self._state_lock:
                states = tuple(self._states.items())
            for stream, state in states:
                try:
                    state.handle.close()
                except OSError as exc:
                    with self._state_lock:
                        self._failed_streams.add(stream)
                    if first_failure is None:
                        first_failure = exc
            if first_failure is not None:
                raise first_failure

    def _run(self) -> None:
        """Poll both streams; any reader failure closes that unread pipe."""
        while True:
            made_progress = False
            with self._state_lock:
                active = tuple(
                    (stream, state) for stream, state in self._states.items() if state.reading
                )
            if not active:
                return
            for stream, state in active:
                try:
                    data = self._pipes.read_pipe(state.handle.value, self._read_size)
                    if data is None:
                        with self._state_lock:
                            self._append(stream, state.decoder.decode(b"", final=True))
                        self._retire(stream, state, failed=False)
                    elif data:
                        with self._state_lock:
                            self._append(stream, state.decoder.decode(data, final=False))
                        made_progress = True
                except Exception:
                    self._retire(stream, state, failed=True)
            if not made_progress and self._stop.wait(self._idle_interval):
                for stream, state in active:
                    self._retire(stream, state, failed=False)

    def _retire(
        self,
        stream: ProcessOutputStream,
        state: _StreamState,
        *,
        failed: bool,
    ) -> None:
        """Stop one reader and close its pipe so the child cannot block on it."""
        with self._state_lock:
            if not state.reading:
                return
            state.reading = False
            if failed:
                self._failed_streams.add(stream)
        try:
            state.handle.close()
        except OSError:
            with self._state_lock:
                self._failed_streams.add(stream)

    def _append(self, stream: ProcessOutputStream, text: str) -> None:
        if not text:
            return
        if len(text) > self._character_limit:
            text = text[-self._character_limit :]
            self._truncated = True
        chunk = ProcessOutputChunk(
            sequence=self._next_sequence,
            stream=stream,
            text=text,
        )
        self._next_sequence += 1
        self._chunks.append(chunk)
        self._characters += len(text)
        self._trim()

    def _trim(self) -> None:
        while self._characters > self._character_limit:
            first = self._chunks.popleft()
            excess = self._characters - self._character_limit
            if excess < len(first.text):
                self._chunks.appendleft(
                    ProcessOutputChunk(
                        sequence=first.sequence,
                        stream=first.stream,
                        text=first.text[excess:],
                    )
                )
                self._characters -= excess
            else:
                self._characters -= len(first.text)
            self._truncated = True
