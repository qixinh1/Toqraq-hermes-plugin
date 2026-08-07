"""Immutable resource bounds for one engine-bridge listener."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .bridge_rpc_state import BridgeRpcPolicy

_MAX_POLICY_SECONDS = 300.0
_MIN_WRITE_BUFFER_BYTES = 1_024
_MAX_WRITE_BUFFER_BYTES = 1_048_576


@dataclass(frozen=True, slots=True, kw_only=True)
class BridgeListenerPolicy:
    """All listener queue, buffer, and wall-clock bounds."""

    start_timeout_seconds: float = 5.0
    open_timeout_seconds: float = 5.0
    first_message_timeout_seconds: float = 5.0
    send_timeout_seconds: float = 5.0
    ping_interval_seconds: float = 20.0
    ping_timeout_seconds: float = 10.0
    close_timeout_seconds: float = 2.0
    shutdown_timeout_seconds: float = 5.0
    write_buffer_bytes: int = 32_768
    rpc: BridgeRpcPolicy = field(default_factory=BridgeRpcPolicy)

    def __post_init__(self) -> None:
        """Reject disabled, unbounded, and nonsensical transport policies."""
        for value in (
            self.start_timeout_seconds,
            self.open_timeout_seconds,
            self.first_message_timeout_seconds,
            self.send_timeout_seconds,
            self.ping_interval_seconds,
            self.ping_timeout_seconds,
            self.close_timeout_seconds,
            self.shutdown_timeout_seconds,
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(value)
                or not 0 < value <= _MAX_POLICY_SECONDS
            ):
                raise ValueError("bridge listener timeout policy is invalid")
        if (
            isinstance(self.write_buffer_bytes, bool)
            or not isinstance(self.write_buffer_bytes, int)
            or not _MIN_WRITE_BUFFER_BYTES <= self.write_buffer_bytes <= _MAX_WRITE_BUFFER_BYTES
        ):
            raise ValueError("bridge listener write-buffer policy is invalid")
        if not isinstance(self.rpc, BridgeRpcPolicy):
            raise ValueError("bridge listener RPC policy is invalid")
