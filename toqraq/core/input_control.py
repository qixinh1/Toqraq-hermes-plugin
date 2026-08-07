"""Pure input commands, acknowledgement, and focused control port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeAlias, runtime_checkable

from .observation import validate_observation_text
from .player_input import (
    GamepadAxisEvent,
    GamepadButtonEvent,
    GamepadInputEvent,
    KeyboardInputEvent,
    PointerButtonEvent,
    PointerCoordinateSpace,
    PointerInputEvent,
    PointerKind,
    PointerMoveEvent,
    PointerWheelEvent,
    SemanticInputEvent,
    validate_pointer_event_space,
)

MAX_INPUT_EVENTS = 128
MAX_POINTER_ID = 31
MAX_TEXT_INPUT_BYTES = 4_096
MAX_GAMEPAD_SLOT = 15


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticInputCommand:
    """One validation-atomic ordered batch of project action transitions."""

    events: tuple[SemanticInputEvent, ...]

    def __post_init__(self) -> None:
        """Require a bounded immutable semantic batch."""
        _validate_event_batch(self.events, expected=SemanticInputEvent, label="semantic")


@dataclass(frozen=True, slots=True, kw_only=True)
class KeyboardInputCommand:
    """One validation-atomic ordered batch of W3C keyboard transitions."""

    events: tuple[KeyboardInputEvent, ...]

    def __post_init__(self) -> None:
        """Require a bounded immutable keyboard batch."""
        _validate_event_batch(self.events, expected=KeyboardInputEvent, label="keyboard")


@dataclass(frozen=True, slots=True, kw_only=True)
class PointerInputCommand:
    """One pointer device's validation-atomic batch in one coordinate space."""

    pointer_id: int
    pointer_kind: PointerKind
    coordinate_space: PointerCoordinateSpace
    events: tuple[PointerInputEvent, ...]

    def __post_init__(self) -> None:
        """Validate device identity, event types, and space-specific bounds."""
        _validate_slot(self.pointer_id, maximum=MAX_POINTER_ID, label="pointer ID")
        if not isinstance(self.pointer_kind, PointerKind):
            raise ValueError("pointer kind is invalid")
        if not isinstance(self.coordinate_space, PointerCoordinateSpace):
            raise ValueError("pointer coordinate space is invalid")
        _validate_event_batch(
            self.events,
            expected=(PointerMoveEvent, PointerButtonEvent, PointerWheelEvent),
            label="pointer",
        )
        for event in self.events:
            validate_pointer_event_space(event, self.coordinate_space)


@dataclass(frozen=True, slots=True, kw_only=True)
class TextInputCommand:
    """One bounded Unicode commit for the engine's focused text surface."""

    text: str

    def __post_init__(self) -> None:
        """Reject empty, invalid, null-containing, or oversized text."""
        validate_observation_text(
            self.text,
            maximum_bytes=MAX_TEXT_INPUT_BYTES,
            allow_empty=False,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class GamepadInputCommand:
    """One gamepad slot's validation-atomic batch of standard controls."""

    device_slot: int
    events: tuple[GamepadInputEvent, ...]

    def __post_init__(self) -> None:
        """Validate the bounded slot and immutable typed event batch."""
        _validate_slot(self.device_slot, maximum=MAX_GAMEPAD_SLOT, label="gamepad slot")
        _validate_event_batch(
            self.events,
            expected=(GamepadButtonEvent, GamepadAxisEvent),
            label="gamepad",
        )


InputCommand: TypeAlias = (
    SemanticInputCommand
    | KeyboardInputCommand
    | PointerInputCommand
    | TextInputCommand
    | GamepadInputCommand
)


@dataclass(frozen=True, slots=True, kw_only=True)
class InputAcknowledgement:
    """Count proving that one complete validated command was accepted."""

    accepted_event_count: int

    def __post_init__(self) -> None:
        """Reject counts outside the maximum command batch."""
        if (
            isinstance(self.accepted_event_count, bool)
            or not isinstance(self.accepted_event_count, int)
            or not 1 <= self.accepted_event_count <= MAX_INPUT_EVENTS
        ):
            raise ValueError("accepted input event count is invalid")


def input_command_event_count(command: InputCommand) -> int:
    """Return the event count implied by one validated focused command."""
    if isinstance(command, TextInputCommand):
        return 1
    if isinstance(
        command,
        (
            SemanticInputCommand,
            KeyboardInputCommand,
            PointerInputCommand,
            GamepadInputCommand,
        ),
    ):
        return len(command.events)
    raise TypeError("input command is invalid")


def validate_input_acknowledgement(
    value: InputAcknowledgement,
    command: InputCommand,
) -> None:
    """Require all-or-reject acceptance for the command that owns a reply."""
    if not isinstance(value, InputAcknowledgement):
        raise TypeError("input acknowledgement is invalid")
    if value.accepted_event_count != input_command_event_count(command):
        raise ValueError("accepted input event count does not match its command")


@runtime_checkable
class InputController(Protocol):
    """Engine boundary for five validation-atomic player-input operations."""

    async def semantic(self, command: SemanticInputCommand) -> InputAcknowledgement:
        """Apply one ordered semantic-action batch."""
        ...

    async def keyboard(self, command: KeyboardInputCommand) -> InputAcknowledgement:
        """Apply one ordered normalized-keyboard batch."""
        ...

    async def pointer(self, command: PointerInputCommand) -> InputAcknowledgement:
        """Apply one pointer device batch in its declared coordinate space."""
        ...

    async def text(self, command: TextInputCommand) -> InputAcknowledgement:
        """Commit one text event to the currently focused text surface."""
        ...

    async def gamepad(self, command: GamepadInputCommand) -> InputAcknowledgement:
        """Apply one ordered standard-layout gamepad batch."""
        ...


def _validate_event_batch(
    values: tuple[object, ...],
    *,
    expected: type[object] | tuple[type[object], ...],
    label: str,
) -> None:
    """Apply the shared bounded immutable pre-dispatch validation rule."""
    if (
        not isinstance(values, tuple)
        or not 1 <= len(values) <= MAX_INPUT_EVENTS
        or any(not isinstance(value, expected) for value in values)
    ):
        raise ValueError(f"{label} input event batch is invalid")


def _validate_slot(value: int, *, maximum: int, label: str) -> None:
    """Require a non-Boolean integer device slot inside its hard ceiling."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValueError(f"{label} is invalid")
