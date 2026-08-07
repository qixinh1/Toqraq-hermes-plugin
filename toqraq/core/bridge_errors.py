"""Stable failures produced by the untrusted engine-bridge boundary."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from .error_values import ErrorFields
from .errors import ErrorCategory, ToqraqError
from .trace import TraceId


class BridgeHandshakeField(StrEnum):
    """Exact handshake identity field that failed comparison."""

    CREDENTIAL = "credential"
    SESSION_ID = "session_id"
    RUN_REVISION = "run_revision"
    ENGINE_ID = "engine_id"
    ENGINE_VERSION = "engine_version"
    BUILD_ID = "build_id"
    DISTRIBUTION_ID = "distribution_id"
    PLATFORM = "platform"
    ARCHITECTURE = "architecture"
    BRIDGE_ID = "bridge_id"
    PROTOCOL = "protocol"
    CAPABILITIES = "capabilities"


class BridgeWireError(ToqraqError):
    """Base for a bridge failure with one JSON-RPC error number."""

    rpc_code: ClassVar[int]

    def __init__(
        self,
        *,
        request_id: str | None = None,
        parameters: ErrorFields | None = None,
        details: ErrorFields | None = None,
        cause: BaseException | None = None,
        trace_id: TraceId | None = None,
    ) -> None:
        """Retain only a request ID already validated by the envelope decoder."""
        self.request_id = request_id
        super().__init__(
            parameters=parameters,
            details=details,
            cause=cause,
            trace_id=trace_id,
        )


class BridgeJsonInvalidError(BridgeWireError):
    """A text frame is not one unambiguous finite JSON value."""

    code = "bridge.json_invalid"
    category = ErrorCategory.INVALID
    rpc_code = -32700


class BridgeRequestInvalidError(BridgeWireError):
    """A decoded value is not a valid bounded JSON-RPC request."""

    code = "bridge.request_invalid"
    category = ErrorCategory.INVALID
    rpc_code = -32600


class BridgeMethodNotFoundError(BridgeWireError):
    """The first valid request does not name the handshake method."""

    code = "bridge.method_not_found"
    category = ErrorCategory.INVALID
    rpc_code = -32601


class BridgeParamsInvalidError(BridgeWireError):
    """Handshake parameters do not satisfy their exact schema."""

    code = "bridge.params_invalid"
    category = ErrorCategory.INVALID
    rpc_code = -32602

    def __init__(self, *, location: str, request_id: str | None = None) -> None:
        """Retain only a bounded schema location, never rejected input."""
        super().__init__(request_id=request_id, details={"location": location})


class BridgeHandshakeMismatchError(BridgeWireError):
    """A valid handshake offer differs from its immutable expectation."""

    code = "bridge.handshake_mismatch"
    category = ErrorCategory.UNAUTHENTICATED
    rpc_code = -32001

    def __init__(
        self,
        *,
        field: BridgeHandshakeField,
        request_id: str | None = None,
    ) -> None:
        """Identify the compared field without retaining either value."""
        self.field = field
        super().__init__(request_id=request_id, parameters={"field": field.value})


class BridgeCredentialMismatchError(BridgeHandshakeMismatchError):
    """Internal marker for a candidate that has not proved the launch secret."""

    def __init__(self, *, request_id: str | None = None) -> None:
        """Remain wire-identical to every other exact handshake mismatch."""
        super().__init__(field=BridgeHandshakeField.CREDENTIAL, request_id=request_id)


class BridgeMessageTooLargeError(BridgeWireError):
    """A bridge text frame exceeds the pre-parse byte limit."""

    code = "bridge.message_too_large"
    category = ErrorCategory.INVALID
    rpc_code = -32002

    def __init__(
        self,
        *,
        actual_bytes: int,
        maximum_bytes: int,
        request_id: str | None = None,
    ) -> None:
        """Record only byte counts needed to diagnose the rejected frame."""
        super().__init__(
            request_id=request_id,
            parameters={"actual_bytes": actual_bytes, "maximum_bytes": maximum_bytes},
        )


BRIDGE_WIRE_ERROR_TYPES: tuple[type[BridgeWireError], ...] = (
    BridgeJsonInvalidError,
    BridgeRequestInvalidError,
    BridgeMethodNotFoundError,
    BridgeParamsInvalidError,
    BridgeHandshakeMismatchError,
    BridgeMessageTooLargeError,
)
