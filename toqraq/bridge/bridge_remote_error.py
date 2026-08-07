"""Safe internal boundary for one engine-authored operation failure."""

from __future__ import annotations

from ..contracts.bridge_rpc import BridgeOperationRpcCode
from ..contracts.errors import PublicError
from ..core.trace import TraceId, error_trace_id


class BridgeRemoteError(Exception):
    """Preserve a validated remote error without claiming local semantics.

    Focused feature adapters must map only the remote codes their contract
    explicitly allows. This exception never crosses a service presenter.
    """

    __slots__ = ("local_trace_id", "remote", "rpc_code")

    def __init__(
        self,
        *,
        rpc_code: BridgeOperationRpcCode,
        remote: PublicError,
    ) -> None:
        """Own separate local and remote traces without retaining wire prose."""
        if rpc_code not in {-32601, -32602, -32603, -32000, -32800}:
            raise ValueError("bridge remote RPC code is invalid")
        if not isinstance(remote, PublicError):
            raise ValueError("bridge remote public error is invalid")
        self.rpc_code = rpc_code
        self.remote = remote
        self.local_trace_id: TraceId = error_trace_id()
        super().__init__("bridge remote operation failed")

    def __repr__(self) -> str:
        """Exclude technical message text, frame data, and remote detail values."""
        return (
            "BridgeRemoteError("
            f"rpc_code={self.rpc_code!r}, remote_code={self.remote.code!r}, "
            f"local_trace_id={str(self.local_trace_id)!r}, "
            f"remote_trace_id={self.remote.trace_id!r})"
        )
