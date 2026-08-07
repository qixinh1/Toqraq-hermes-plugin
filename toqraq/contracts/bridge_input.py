"""Strict JSON-RPC contracts for five focused engine-neutral input methods."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, BeforeValidator, Field, StringConstraints, model_validator

from ..core.input_control import (
    MAX_GAMEPAD_SLOT,
    MAX_INPUT_EVENTS,
    MAX_POINTER_ID,
    MAX_TEXT_INPUT_BYTES,
    GamepadInputCommand,
    InputAcknowledgement,
    InputCommand,
    KeyboardInputCommand,
    PointerInputCommand,
    SemanticInputCommand,
    TextInputCommand,
    validate_input_acknowledgement,
)
from ..core.observation import validate_observation_text
from ..core.player_input import PointerCoordinateSpace, PointerKind
from .base import ContractModel, freeze_sequence
from .bridge import JSON_RPC_VERSION
from .bridge_input_events import (
    GamepadInputEventValue,
    KeyboardInputEventValue,
    PointerInputEventValue,
    SemanticInputEventValue,
    gamepad_event_from_core,
    pointer_event_from_core,
)
from .bridge_rpc import BridgeHostRequestId

SEMANTIC_INPUT_METHOD: Literal["toqraq.input.semantic"] = "toqraq.input.semantic"
KEYBOARD_INPUT_METHOD: Literal["toqraq.input.keyboard"] = "toqraq.input.keyboard"
POINTER_INPUT_METHOD: Literal["toqraq.input.pointer"] = "toqraq.input.pointer"
TEXT_INPUT_METHOD: Literal["toqraq.input.text"] = "toqraq.input.text"
GAMEPAD_INPUT_METHOD: Literal["toqraq.input.gamepad"] = "toqraq.input.gamepad"

PointerKindValue: TypeAlias = Literal["mouse", "pen", "touch"]
PointerCoordinateSpaceValue: TypeAlias = Literal[
    "viewport_pixels",
    "viewport_normalized",
]
SemanticInputEventValues: TypeAlias = Annotated[
    tuple[SemanticInputEventValue, ...],
    BeforeValidator(freeze_sequence),
    Field(min_length=1, max_length=MAX_INPUT_EVENTS),
]
KeyboardInputEventValues: TypeAlias = Annotated[
    tuple[KeyboardInputEventValue, ...],
    BeforeValidator(freeze_sequence),
    Field(min_length=1, max_length=MAX_INPUT_EVENTS),
]
PointerInputEventValues: TypeAlias = Annotated[
    tuple[PointerInputEventValue, ...],
    BeforeValidator(freeze_sequence),
    Field(min_length=1, max_length=MAX_INPUT_EVENTS),
]
GamepadInputEventValues: TypeAlias = Annotated[
    tuple[GamepadInputEventValue, ...],
    BeforeValidator(freeze_sequence),
    Field(min_length=1, max_length=MAX_INPUT_EVENTS),
]


def _validate_input_text(value: str) -> str:
    """Apply the exact UTF-8 byte and null rules hidden by JSON Schema."""
    return validate_observation_text(
        value,
        maximum_bytes=MAX_TEXT_INPUT_BYTES,
        allow_empty=False,
    )


InputText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_TEXT_INPUT_BYTES),
    AfterValidator(_validate_input_text),
]


class SemanticInputParams(ContractModel):
    """One ordered validation-atomic semantic-action batch."""

    events: SemanticInputEventValues

    def to_core(self) -> SemanticInputCommand:
        """Convert strict semantic events to the pure focused command."""
        return SemanticInputCommand(events=tuple(event.to_core() for event in self.events))

    @classmethod
    def from_core(cls, value: SemanticInputCommand) -> SemanticInputParams:
        """Create canonical params from one validated pure command."""
        return cls(events=tuple(SemanticInputEventValue.from_core(event) for event in value.events))


class KeyboardInputParams(ContractModel):
    """One ordered validation-atomic W3C keyboard batch."""

    events: KeyboardInputEventValues

    def to_core(self) -> KeyboardInputCommand:
        """Convert strict keyboard events to the pure focused command."""
        return KeyboardInputCommand(events=tuple(event.to_core() for event in self.events))

    @classmethod
    def from_core(cls, value: KeyboardInputCommand) -> KeyboardInputParams:
        """Create canonical params from one validated pure command."""
        return cls(events=tuple(KeyboardInputEventValue.from_core(event) for event in value.events))


class PointerInputParams(ContractModel):
    """One pointer device's validation-atomic viewport batch."""

    pointer_id: int = Field(ge=0, le=MAX_POINTER_ID)
    pointer_kind: PointerKindValue
    coordinate_space: PointerCoordinateSpaceValue
    events: PointerInputEventValues

    @model_validator(mode="after")
    def validate_coordinate_space(self) -> PointerInputParams:
        """Apply normalized bounds after each event discriminator is decoded."""
        self.to_core()
        return self

    def to_core(self) -> PointerInputCommand:
        """Convert strict pointer events to the pure focused command."""
        return PointerInputCommand(
            pointer_id=self.pointer_id,
            pointer_kind=PointerKind(self.pointer_kind),
            coordinate_space=PointerCoordinateSpace(self.coordinate_space),
            events=tuple(event.to_core() for event in self.events),
        )

    @classmethod
    def from_core(cls, value: PointerInputCommand) -> PointerInputParams:
        """Create canonical params from one validated pure command."""
        return cls(
            pointer_id=value.pointer_id,
            pointer_kind=value.pointer_kind.value,
            coordinate_space=value.coordinate_space.value,
            events=tuple(pointer_event_from_core(event) for event in value.events),
        )


class TextInputParams(ContractModel):
    """One bounded Unicode commit for the focused text surface."""

    text: InputText

    def to_core(self) -> TextInputCommand:
        """Convert strict input text to the pure focused command."""
        return TextInputCommand(text=self.text)

    @classmethod
    def from_core(cls, value: TextInputCommand) -> TextInputParams:
        """Create canonical params from one validated pure command."""
        return cls(text=value.text)


class GamepadInputParams(ContractModel):
    """One gamepad slot's validation-atomic standard-layout batch."""

    device_slot: int = Field(ge=0, le=MAX_GAMEPAD_SLOT)
    events: GamepadInputEventValues

    def to_core(self) -> GamepadInputCommand:
        """Convert strict gamepad events to the pure focused command."""
        return GamepadInputCommand(
            device_slot=self.device_slot,
            events=tuple(event.to_core() for event in self.events),
        )

    @classmethod
    def from_core(cls, value: GamepadInputCommand) -> GamepadInputParams:
        """Create canonical params from one validated pure command."""
        return cls(
            device_slot=value.device_slot,
            events=tuple(gamepad_event_from_core(event) for event in value.events),
        )


class InputAcknowledgementValue(ContractModel):
    """Exact count accepted for one request-correlated complete command."""

    accepted_event_count: int = Field(ge=1, le=MAX_INPUT_EVENTS)

    def to_core(self, *, command: InputCommand) -> InputAcknowledgement:
        """Convert and correlate one acknowledgement with its owning command."""
        value = InputAcknowledgement(accepted_event_count=self.accepted_event_count)
        validate_input_acknowledgement(value, command)
        return value

    @classmethod
    def from_core(
        cls,
        value: InputAcknowledgement,
        *,
        command: InputCommand,
    ) -> InputAcknowledgementValue:
        """Create one DTO only after correlating it with the owning command."""
        validate_input_acknowledgement(value, command)
        return cls(accepted_event_count=value.accepted_event_count)


class SemanticInputRequest(ContractModel):
    """Exact JSON-RPC semantic-input request."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    method: Literal["toqraq.input.semantic"]
    params: SemanticInputParams

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        command: SemanticInputCommand,
    ) -> SemanticInputRequest:
        """Bind one semantic command to a validated request identity."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            method=SEMANTIC_INPUT_METHOD,
            params=SemanticInputParams.from_core(command),
        )


class KeyboardInputRequest(ContractModel):
    """Exact JSON-RPC keyboard-input request."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    method: Literal["toqraq.input.keyboard"]
    params: KeyboardInputParams

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        command: KeyboardInputCommand,
    ) -> KeyboardInputRequest:
        """Bind one keyboard command to a validated request identity."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            method=KEYBOARD_INPUT_METHOD,
            params=KeyboardInputParams.from_core(command),
        )


class PointerInputRequest(ContractModel):
    """Exact JSON-RPC pointer-input request."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    method: Literal["toqraq.input.pointer"]
    params: PointerInputParams

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        command: PointerInputCommand,
    ) -> PointerInputRequest:
        """Bind one pointer command to a validated request identity."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            method=POINTER_INPUT_METHOD,
            params=PointerInputParams.from_core(command),
        )


class TextInputRequest(ContractModel):
    """Exact JSON-RPC text-input request."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    method: Literal["toqraq.input.text"]
    params: TextInputParams

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        command: TextInputCommand,
    ) -> TextInputRequest:
        """Bind one text command to a validated request identity."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            method=TEXT_INPUT_METHOD,
            params=TextInputParams.from_core(command),
        )


class GamepadInputRequest(ContractModel):
    """Exact JSON-RPC gamepad-input request."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    method: Literal["toqraq.input.gamepad"]
    params: GamepadInputParams

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        command: GamepadInputCommand,
    ) -> GamepadInputRequest:
        """Bind one gamepad command to a validated request identity."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            method=GAMEPAD_INPUT_METHOD,
            params=GamepadInputParams.from_core(command),
        )


class InputAcknowledgementResponse(ContractModel):
    """Exact JSON-RPC success response shared by focused input methods."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    result: InputAcknowledgementValue

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        value: InputAcknowledgement,
        command: InputCommand,
    ) -> InputAcknowledgementResponse:
        """Bind one request-correlated acknowledgement to its identity."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            result=InputAcknowledgementValue.from_core(value, command=command),
        )
