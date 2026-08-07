"""Focused simulation controller over one controlled Bridge connection."""

from __future__ import annotations

from ...contracts.bridge_rpc import BridgeRpcSuccessEnvelope
from ...contracts.bridge_simulation import (
    SimulationSetPausedRequest,
    SimulationSetPausedResponse,
    SimulationStepRequest,
    SimulationStepResponse,
)
from ...core.simulation_control import (
    SetPausedAcknowledgement,
    SetPausedCommand,
    StepFramesAcknowledgement,
    StepFramesCommand,
)
from ..bridge_rpc_codec import decode_expected_success
from ..bridge_rpc_connection import BridgeRpcConnection
from .remote_errors import map_simulation_remote_error


class BridgeSimulationController:
    """Construct exact immediate controls and return correlated acknowledgements."""

    __slots__ = ("_connection",)

    def __init__(self, connection: BridgeRpcConnection) -> None:
        """Bind the controller to one authenticated controlled connection."""
        if not isinstance(connection, BridgeRpcConnection):
            raise TypeError("controlled Bridge connection is invalid")
        self._connection = connection

    async def set_paused(self, command: SetPausedCommand) -> SetPausedAcknowledgement:
        """Set one desired pause state and correlate the resulting state exactly."""
        decoded: SetPausedAcknowledgement | None = None

        def request(request_id: str) -> SimulationSetPausedRequest:
            return SimulationSetPausedRequest.from_core(
                request_id=request_id,
                command=command,
            )

        def decode(envelope: BridgeRpcSuccessEnvelope) -> SimulationSetPausedResponse:
            nonlocal decoded
            response = decode_expected_success(envelope, SimulationSetPausedResponse)
            decoded = response.result.to_core(command=command)
            return response

        await self._connection.call(
            request,
            decode,
            map_remote_error=map_simulation_remote_error,
        )
        if decoded is None:
            raise RuntimeError("pause response completed without its Core value")
        return decoded

    async def step(self, command: StepFramesCommand) -> StepFramesAcknowledgement:
        """Advance the exact requested frame count and correlate its acknowledgement."""
        decoded: StepFramesAcknowledgement | None = None

        def request(request_id: str) -> SimulationStepRequest:
            return SimulationStepRequest.from_core(
                request_id=request_id,
                command=command,
            )

        def decode(envelope: BridgeRpcSuccessEnvelope) -> SimulationStepResponse:
            nonlocal decoded
            response = decode_expected_success(envelope, SimulationStepResponse)
            decoded = response.result.to_core(command=command)
            return response

        await self._connection.call(
            request,
            decode,
            map_remote_error=map_simulation_remote_error,
        )
        if decoded is None:
            raise RuntimeError("step response completed without its Core value")
        return decoded
