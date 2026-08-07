"""Request trace identity and asynchronous trace ownership."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID, uuid4

_active_trace: ContextVar[TraceId | None] = ContextVar("toqraq_trace_id", default=None)


@dataclass(frozen=True, slots=True)
class TraceId:
    """Canonical UUID text used to correlate one failed operation."""

    value: str

    def __post_init__(self) -> None:
        """Reject non-canonical or non-UUID trace identifiers."""
        try:
            parsed = UUID(self.value)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("trace ID must be canonical UUID text") from exc
        if parsed.version != 4 or self.value != str(parsed):
            raise ValueError("trace ID must be lowercase canonical UUID4 text")

    def __str__(self) -> str:
        """Return the public canonical representation."""
        return self.value

    @classmethod
    def new(cls) -> TraceId:
        """Generate a new random operation trace."""
        return cls(str(uuid4()))


def select_trace_id(candidate: str | None) -> TraceId:
    """Use a canonical host trace or generate a fresh UUID4.

    Args:
        candidate: Optional trace supplied by a trusted Hermes boundary.

    Returns:
        The accepted host trace or a newly generated trace.
    """
    if candidate is not None:
        try:
            return TraceId(candidate)
        except ValueError:
            pass
    return TraceId.new()


def current_trace_id() -> TraceId | None:
    """Return the trace owned by the current asynchronous context."""
    return _active_trace.get()


def error_trace_id() -> TraceId:
    """Return the current trace or a standalone trace for an unscoped error."""
    return current_trace_id() or TraceId.new()


@contextmanager
def trace_scope(candidate: str | None = None) -> Iterator[TraceId]:
    """Own one trace for all work performed inside the context.

    A nested scope without a candidate retains its parent's trace. Supplying a
    canonical host trace intentionally starts a new correlated boundary.

    Args:
        candidate: Optional canonical trace supplied by Hermes.

    Yields:
        The trace active for the scope.
    """
    parent = current_trace_id()
    trace_id = parent if candidate is None and parent is not None else select_trace_id(candidate)
    token = _active_trace.set(trace_id)
    try:
        yield trace_id
    finally:
        _active_trace.reset(token)
