"""Bounded diagnostics for failures caught at outer process boundaries."""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from types import TracebackType

_MAX_STACK_LOCATIONS = 8
_MAX_SYMBOL_LENGTH = 96
_UNSAFE_SYMBOL = re.compile(r"[^A-Za-z0-9_.<>-]")


@dataclass(frozen=True, slots=True)
class FailureDiagnostic:
    """Log-safe exception type and source locations without exception data."""

    exception_type: str
    stack_locations: tuple[str, ...]


def failure_diagnostic(exception: BaseException) -> FailureDiagnostic:
    """Extract bounded source identity without messages, arguments, or locals.

    Args:
        exception: Unexpected boundary failure.

    Returns:
        A diagnostic safe for a structured log record.
    """
    try:
        exception_type = _exception_type(exception)
        locations: list[str] = []
        traceback = object.__getattribute__(exception, "__traceback__")
        for frame in _bounded_traceback(traceback):
            module_value = frame.tb_frame.f_globals.get("__name__")
            module = _safe_symbol(module_value if isinstance(module_value, str) else "unknown")
            function = _safe_symbol(frame.tb_frame.f_code.co_name)
            locations.append(f"{module}:{function}:{frame.tb_lineno}")
        return FailureDiagnostic(
            exception_type=exception_type,
            stack_locations=tuple(locations) or ("unknown:unknown:0",),
        )
    except BaseException:
        return FailureDiagnostic("unknown", ("unknown:unknown:0",))


def _bounded_traceback(traceback: TracebackType | None) -> tuple[TracebackType, ...]:
    """Return only the last bounded set of traceback frames."""
    frames: deque[TracebackType] = deque(maxlen=_MAX_STACK_LOCATIONS)
    while traceback is not None:
        frames.append(traceback)
        traceback = traceback.tb_next
    return tuple(frames)


def _safe_symbol(value: str) -> str:
    """Bound and constrain code symbols before logging them."""
    sanitized = _UNSAFE_SYMBOL.sub("?", value)
    return sanitized[:_MAX_SYMBOL_LENGTH] or "unknown"


def _exception_type(exception: BaseException) -> str:
    """Read class identity without invoking instance or foreign string hooks."""
    exception_class = type(exception)
    module = type.__getattribute__(exception_class, "__module__")
    qualified_name = type.__getattribute__(exception_class, "__qualname__")
    safe_module = module if isinstance(module, str) else "unknown"
    safe_name = qualified_name if isinstance(qualified_name, str) else "unknown"
    return _safe_symbol(f"{safe_module}.{safe_name}")
