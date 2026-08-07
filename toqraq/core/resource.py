"""Async resource handle owned by an engine session."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AsyncResource(Protocol):
    """Idempotent asynchronous lifecycle resource."""

    async def close(self) -> None:
        """Release the resource idempotently."""
        ...
