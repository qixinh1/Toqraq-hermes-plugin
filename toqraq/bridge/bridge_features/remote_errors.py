"""Method-specific remote error mappings for common Bridge feature ports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar

from ...contracts.json_values import FrozenJson
from ...core.error_values import ErrorFields
from ...core.errors import (
    BridgeConnectionError,
    CapabilityUnavailableError,
    InputRejectedError,
    PerceptionFrameUnavailableError,
    PerceptionObjectNotFoundError,
    PerceptionStaleError,
    ProtocolError,
    SimulationStateError,
    ToqraqError,
)
from ..bridge_remote_error import BridgeRemoteError

ErrorT = TypeVar("ErrorT", bound=ToqraqError)


def map_perception_reference_remote_error(failure: BridgeRemoteError) -> ToqraqError:
    """Map capability, staleness, and missing-reference perception failures."""
    if _is_application(failure, PerceptionStaleError):
        return _copy_remote(PerceptionStaleError, failure)
    if _is_application(failure, PerceptionObjectNotFoundError):
        return _copy_remote(PerceptionObjectNotFoundError, failure)
    return _map_common(failure)


def map_perception_stale_remote_error(failure: BridgeRemoteError) -> ToqraqError:
    """Map capability and revision or cursor staleness failures."""
    if _is_application(failure, PerceptionStaleError):
        return _copy_remote(PerceptionStaleError, failure)
    return _map_common(failure)


def map_frame_remote_error(failure: BridgeRemoteError) -> ToqraqError:
    """Map only frame capability and current-frame availability failures."""
    if _is_application(failure, PerceptionFrameUnavailableError):
        return _copy_remote(PerceptionFrameUnavailableError, failure)
    return _map_common(failure)


def map_simulation_remote_error(failure: BridgeRemoteError) -> ToqraqError:
    """Map only simulation capability and live-state conflicts."""
    if _is_application(failure, SimulationStateError):
        return _copy_remote(SimulationStateError, failure)
    return _map_common(failure)


def map_input_remote_error(failure: BridgeRemoteError) -> ToqraqError:
    """Map only input capability and dynamic game-state rejection."""
    if _is_application(failure, InputRejectedError):
        return _copy_remote(InputRejectedError, failure)
    return _map_common(failure)


def _map_common(failure: BridgeRemoteError) -> ToqraqError:
    """Map the two errors explicitly allowed for every focused method."""
    if _is_application(failure, CapabilityUnavailableError):
        return _copy_remote(CapabilityUnavailableError, failure)
    if failure.rpc_code == -32603:
        return BridgeConnectionError(
            details={"reason": "remote_internal"},
            cause=failure,
            trace_id=failure.local_trace_id,
        )
    raise ProtocolError(details={"reason": "unmapped_remote_error"})


def _is_application(failure: BridgeRemoteError, error_type: type[ToqraqError]) -> bool:
    """Match one exact non-internal application code and category pair."""
    return (
        failure.rpc_code == -32000
        and failure.remote.code == error_type.code
        and failure.remote.category is error_type.category
    )


def _copy_remote(error_type: type[ErrorT], failure: BridgeRemoteError) -> ErrorT:
    """Create a registered local failure with a local trace and safe fields."""
    return error_type(
        parameters=_error_fields(failure.remote.parameters),
        details=_error_fields(failure.remote.details),
        cause=failure,
        trace_id=failure.local_trace_id,
    )


def _error_fields(values: Mapping[str, FrozenJson]) -> ErrorFields:
    """Project already frozen public JSON into the equivalent Core value type."""
    return {key: value.data for key, value in values.items()}
