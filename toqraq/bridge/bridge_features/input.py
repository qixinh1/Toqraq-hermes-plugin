"""Five focused player-input methods over one controlled Bridge connection."""

from __future__ import annotations

from ...contracts.bridge_input import (
    GamepadInputRequest,
    InputAcknowledgementResponse,
    KeyboardInputRequest,
    PointerInputRequest,
    SemanticInputRequest,
    TextInputRequest,
)
from ...contracts.bridge_rpc import BridgeRpcSuccessEnvelope
from ...core.input_control import (
    GamepadInputCommand,
    InputAcknowledgement,
    KeyboardInputCommand,
    PointerInputCommand,
    SemanticInputCommand,
    TextInputCommand,
)
from ..bridge_rpc_codec import decode_expected_success
from ..bridge_rpc_connection import BridgeRpcConnection
from .remote_errors import map_input_remote_error


class BridgeInputController:
    """Keep every input kind on its exact non-executable protocol method."""

    __slots__ = ("_connection",)

    def __init__(self, connection: BridgeRpcConnection) -> None:
        """Bind the controller to one authenticated controlled connection."""
        if not isinstance(connection, BridgeRpcConnection):
            raise TypeError("controlled Bridge connection is invalid")
        self._connection = connection

    async def semantic(self, command: SemanticInputCommand) -> InputAcknowledgement:
        """Dispatch one atomic semantic-action batch."""
        decoded: InputAcknowledgement | None = None

        def request(request_id: str) -> SemanticInputRequest:
            return SemanticInputRequest.from_core(request_id=request_id, command=command)

        def decode(envelope: BridgeRpcSuccessEnvelope) -> InputAcknowledgementResponse:
            nonlocal decoded
            response = decode_expected_success(envelope, InputAcknowledgementResponse)
            decoded = response.result.to_core(command=command)
            return response

        await self._connection.call(request, decode, map_remote_error=map_input_remote_error)
        return _require_acknowledgement(decoded)

    async def keyboard(self, command: KeyboardInputCommand) -> InputAcknowledgement:
        """Dispatch one atomic physical/logical keyboard batch."""
        decoded: InputAcknowledgement | None = None

        def request(request_id: str) -> KeyboardInputRequest:
            return KeyboardInputRequest.from_core(request_id=request_id, command=command)

        def decode(envelope: BridgeRpcSuccessEnvelope) -> InputAcknowledgementResponse:
            nonlocal decoded
            response = decode_expected_success(envelope, InputAcknowledgementResponse)
            decoded = response.result.to_core(command=command)
            return response

        await self._connection.call(request, decode, map_remote_error=map_input_remote_error)
        return _require_acknowledgement(decoded)

    async def pointer(self, command: PointerInputCommand) -> InputAcknowledgement:
        """Dispatch one atomic mouse, pen, or touch batch."""
        decoded: InputAcknowledgement | None = None

        def request(request_id: str) -> PointerInputRequest:
            return PointerInputRequest.from_core(request_id=request_id, command=command)

        def decode(envelope: BridgeRpcSuccessEnvelope) -> InputAcknowledgementResponse:
            nonlocal decoded
            response = decode_expected_success(envelope, InputAcknowledgementResponse)
            decoded = response.result.to_core(command=command)
            return response

        await self._connection.call(request, decode, map_remote_error=map_input_remote_error)
        return _require_acknowledgement(decoded)

    async def text(self, command: TextInputCommand) -> InputAcknowledgement:
        """Dispatch one atomic committed-text batch."""
        decoded: InputAcknowledgement | None = None

        def request(request_id: str) -> TextInputRequest:
            return TextInputRequest.from_core(request_id=request_id, command=command)

        def decode(envelope: BridgeRpcSuccessEnvelope) -> InputAcknowledgementResponse:
            nonlocal decoded
            response = decode_expected_success(envelope, InputAcknowledgementResponse)
            decoded = response.result.to_core(command=command)
            return response

        await self._connection.call(request, decode, map_remote_error=map_input_remote_error)
        return _require_acknowledgement(decoded)

    async def gamepad(self, command: GamepadInputCommand) -> InputAcknowledgement:
        """Dispatch one atomic standard-layout gamepad batch."""
        decoded: InputAcknowledgement | None = None

        def request(request_id: str) -> GamepadInputRequest:
            return GamepadInputRequest.from_core(request_id=request_id, command=command)

        def decode(envelope: BridgeRpcSuccessEnvelope) -> InputAcknowledgementResponse:
            nonlocal decoded
            response = decode_expected_success(envelope, InputAcknowledgementResponse)
            decoded = response.result.to_core(command=command)
            return response

        await self._connection.call(request, decode, map_remote_error=map_input_remote_error)
        return _require_acknowledgement(decoded)


def _require_acknowledgement(
    value: InputAcknowledgement | None,
) -> InputAcknowledgement:
    """Enforce the decoder-to-caller ownership invariant without a fake result."""
    if value is None:
        raise RuntimeError("input response completed without its Core value")
    return value
