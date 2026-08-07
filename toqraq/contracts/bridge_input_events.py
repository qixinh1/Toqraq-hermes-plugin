"""Strict scalar and event DTOs for engine-neutral bridge input."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    StringConstraints,
    model_validator,
)

from ..core.keyboard_standard import (
    MAX_LOGICAL_KEY_BYTES,
    W3C_REQUIRED_PHYSICAL_KEY_CODES,
    validate_logical_key,
    validate_physical_key_code,
)
from ..core.observation import validate_observation_label
from ..core.player_input import (
    MAX_POINTER_COORDINATE,
    MAX_POINTER_WHEEL_DELTA,
    MAX_SEMANTIC_ACTION_BYTES,
    GamepadAxis,
    GamepadAxisEvent,
    GamepadButton,
    GamepadButtonEvent,
    GamepadInputEvent,
    KeyboardInputEvent,
    KeyboardLocation,
    KeyboardModifier,
    PointerButton,
    PointerButtonEvent,
    PointerInputEvent,
    PointerMoveEvent,
    PointerWheelEvent,
    PointerWheelUnit,
    SemanticInputEvent,
)
from .base import ContractModel, freeze_sequence


def _validate_action(value: str) -> str:
    """Apply the exact semantic-action UTF-8 and whitespace rules."""
    validate_observation_label(value, maximum_bytes=MAX_SEMANTIC_ACTION_BYTES)
    if not value.strip():
        raise ValueError("semantic action is empty")
    return value


def _validate_logical_key(value: str) -> str:
    """Apply W3C named-key or NFC Unicode key-string semantics."""
    return validate_logical_key(value)


SemanticAction = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_SEMANTIC_ACTION_BYTES),
    AfterValidator(_validate_action),
]
PhysicalKeyCode = Annotated[
    str,
    Field(json_schema_extra={"enum": sorted(W3C_REQUIRED_PHYSICAL_KEY_CODES)}),
    AfterValidator(validate_physical_key_code),
]
LogicalKey = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_LOGICAL_KEY_BYTES),
    AfterValidator(_validate_logical_key),
]
NormalizedPositiveValue = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
NormalizedSignedValue = Annotated[float, Field(ge=-1.0, le=1.0, allow_inf_nan=False)]
PointerCoordinate = Annotated[
    float,
    Field(ge=0.0, le=MAX_POINTER_COORDINATE, allow_inf_nan=False),
]
PointerMotion = Annotated[
    float,
    Field(
        ge=-MAX_POINTER_COORDINATE,
        le=MAX_POINTER_COORDINATE,
        allow_inf_nan=False,
    ),
]
PointerWheelDelta = Annotated[
    float,
    Field(
        ge=-MAX_POINTER_WHEEL_DELTA,
        le=MAX_POINTER_WHEEL_DELTA,
        allow_inf_nan=False,
    ),
]
KeyboardLocationValue: TypeAlias = Literal["standard", "left", "right", "numpad"]
KeyboardModifierValue: TypeAlias = Literal["shift", "control", "alt", "meta"]
PointerButtonName: TypeAlias = Literal[
    "primary",
    "secondary",
    "middle",
    "back",
    "forward",
]
PointerWheelUnitValue: TypeAlias = Literal["pixels", "lines", "pages"]
GamepadButtonName: TypeAlias = Literal[
    "south",
    "east",
    "west",
    "north",
    "left_bumper",
    "right_bumper",
    "left_trigger",
    "right_trigger",
    "select",
    "start",
    "left_stick",
    "right_stick",
    "dpad_up",
    "dpad_down",
    "dpad_left",
    "dpad_right",
    "home",
    "touchpad",
]
GamepadAxisName: TypeAlias = Literal["left_x", "left_y", "right_x", "right_y"]


def _validate_modifier_values(
    values: tuple[KeyboardModifierValue, ...],
) -> tuple[KeyboardModifierValue, ...]:
    """Reject duplicates rather than silently changing key-state meaning."""
    if len(set(values)) != len(values):
        raise ValueError("keyboard modifiers must be unique")
    return values


KeyboardModifierValues: TypeAlias = Annotated[
    tuple[KeyboardModifierValue, ...],
    BeforeValidator(freeze_sequence),
    Field(max_length=len(KeyboardModifier)),
    AfterValidator(_validate_modifier_values),
]


class SemanticInputEventValue(ContractModel):
    """One strict project action transition."""

    action: SemanticAction
    pressed: bool
    strength: NormalizedPositiveValue

    @model_validator(mode="after")
    def validate_state(self) -> SemanticInputEventValue:
        """Require the normalized strength to encode the same press state."""
        self.to_core()
        return self

    def to_core(self) -> SemanticInputEvent:
        """Convert one strict semantic event to its pure value."""
        return SemanticInputEvent(
            action=self.action,
            pressed=self.pressed,
            strength=self.strength,
        )

    @classmethod
    def from_core(cls, value: SemanticInputEvent) -> SemanticInputEventValue:
        """Create one exact DTO from a validated semantic event."""
        return cls(action=value.action, pressed=value.pressed, strength=value.strength)


class KeyboardInputEventValue(ContractModel):
    """One strict normalized physical or logical keyboard transition."""

    physical_code: PhysicalKeyCode | None
    logical_key: LogicalKey | None
    location: KeyboardLocationValue
    modifiers: KeyboardModifierValues
    pressed: bool
    repeated: bool

    @model_validator(mode="after")
    def validate_state(self) -> KeyboardInputEventValue:
        """Require an identified key and a canonical repeat state."""
        self.to_core()
        return self

    def to_core(self) -> KeyboardInputEvent:
        """Convert one strict keyboard event to its pure value."""
        return KeyboardInputEvent(
            physical_code=self.physical_code,
            logical_key=self.logical_key,
            location=KeyboardLocation(self.location),
            modifiers=tuple(KeyboardModifier(value) for value in self.modifiers),
            pressed=self.pressed,
            repeated=self.repeated,
        )

    @classmethod
    def from_core(cls, value: KeyboardInputEvent) -> KeyboardInputEventValue:
        """Create one exact DTO from a validated keyboard event."""
        return cls(
            physical_code=value.physical_code,
            logical_key=value.logical_key,
            location=value.location.value,
            modifiers=tuple(modifier.value for modifier in value.modifiers),
            pressed=value.pressed,
            repeated=value.repeated,
        )


class PointerMoveEventValue(ContractModel):
    """One strict viewport motion event."""

    kind: Literal["motion"]
    x: PointerCoordinate
    y: PointerCoordinate
    delta_x: PointerMotion
    delta_y: PointerMotion

    def to_core(self) -> PointerMoveEvent:
        """Convert one strict motion event to its pure value."""
        return PointerMoveEvent(x=self.x, y=self.y, delta_x=self.delta_x, delta_y=self.delta_y)


class PointerButtonEventValue(ContractModel):
    """One strict logical pointer-button event."""

    kind: Literal["button"]
    x: PointerCoordinate
    y: PointerCoordinate
    button: PointerButtonName
    pressed: bool

    def to_core(self) -> PointerButtonEvent:
        """Convert one strict button event to its pure value."""
        return PointerButtonEvent(
            x=self.x,
            y=self.y,
            button=PointerButton(self.button),
            pressed=self.pressed,
        )


class PointerWheelEventValue(ContractModel):
    """One strict non-zero pointer-wheel event."""

    kind: Literal["wheel"]
    x: PointerCoordinate
    y: PointerCoordinate
    delta_x: PointerWheelDelta
    delta_y: PointerWheelDelta
    unit: PointerWheelUnitValue

    @model_validator(mode="after")
    def validate_delta(self) -> PointerWheelEventValue:
        """Reject an event with no wheel movement."""
        self.to_core()
        return self

    def to_core(self) -> PointerWheelEvent:
        """Convert one strict wheel event to its pure value."""
        return PointerWheelEvent(
            x=self.x,
            y=self.y,
            delta_x=self.delta_x,
            delta_y=self.delta_y,
            unit=PointerWheelUnit(self.unit),
        )


PointerInputEventValue: TypeAlias = Annotated[
    PointerMoveEventValue | PointerButtonEventValue | PointerWheelEventValue,
    Field(discriminator="kind"),
]


class GamepadButtonEventValue(ContractModel):
    """One strict standard-layout gamepad-button event."""

    kind: Literal["button"]
    button: GamepadButtonName
    pressed: bool
    value: NormalizedPositiveValue

    @model_validator(mode="after")
    def validate_state(self) -> GamepadButtonEventValue:
        """Require analog value and press state to agree."""
        self.to_core()
        return self

    def to_core(self) -> GamepadButtonEvent:
        """Convert one strict button event to its pure value."""
        return GamepadButtonEvent(
            button=GamepadButton(self.button),
            pressed=self.pressed,
            value=self.value,
        )


class GamepadAxisEventValue(ContractModel):
    """One strict standard-layout gamepad-axis event."""

    kind: Literal["axis"]
    axis: GamepadAxisName
    value: NormalizedSignedValue

    def to_core(self) -> GamepadAxisEvent:
        """Convert one strict axis event to its pure value."""
        return GamepadAxisEvent(axis=GamepadAxis(self.axis), value=self.value)


GamepadInputEventValue: TypeAlias = Annotated[
    GamepadButtonEventValue | GamepadAxisEventValue,
    Field(discriminator="kind"),
]


def pointer_event_from_core(value: PointerInputEvent) -> PointerInputEventValue:
    """Create one exact discriminated pointer DTO without reflection."""
    if isinstance(value, PointerMoveEvent):
        return PointerMoveEventValue(
            kind="motion",
            x=value.x,
            y=value.y,
            delta_x=value.delta_x,
            delta_y=value.delta_y,
        )
    if isinstance(value, PointerButtonEvent):
        return PointerButtonEventValue(
            kind="button",
            x=value.x,
            y=value.y,
            button=value.button.value,
            pressed=value.pressed,
        )
    return PointerWheelEventValue(
        kind="wheel",
        x=value.x,
        y=value.y,
        delta_x=value.delta_x,
        delta_y=value.delta_y,
        unit=value.unit.value,
    )


def gamepad_event_from_core(value: GamepadInputEvent) -> GamepadInputEventValue:
    """Create one exact discriminated gamepad DTO without reflection."""
    if isinstance(value, GamepadButtonEvent):
        return GamepadButtonEventValue(
            kind="button",
            button=value.button.value,
            pressed=value.pressed,
            value=value.value,
        )
    return GamepadAxisEventValue(kind="axis", axis=value.axis.value, value=value.value)
