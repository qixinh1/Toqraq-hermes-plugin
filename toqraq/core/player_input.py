"""Pure bounded engine-neutral player-input event vocabulary."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from .keyboard_standard import (
    validate_logical_key,
    validate_physical_key_code,
)
from .observation import validate_observation_label

MAX_SEMANTIC_ACTION_BYTES = 256
MAX_POINTER_COORDINATE = 1_000_000.0
MAX_POINTER_WHEEL_DELTA = 10_000.0


class KeyboardLocation(StrEnum):
    """Normalized location of one physical keyboard control."""

    STANDARD = "standard"
    LEFT = "left"
    RIGHT = "right"
    NUMPAD = "numpad"


class KeyboardModifier(StrEnum):
    """Closed modifier facts shared by supported engine bridges."""

    SHIFT = "shift"
    CONTROL = "control"
    ALT = "alt"
    META = "meta"


class PointerKind(StrEnum):
    """Common pointing-device families without engine-native identifiers."""

    MOUSE = "mouse"
    PEN = "pen"
    TOUCH = "touch"


class PointerCoordinateSpace(StrEnum):
    """Explicit interpretation of pointer position and motion values."""

    VIEWPORT_PIXELS = "viewport_pixels"
    VIEWPORT_NORMALIZED = "viewport_normalized"


class PointerButton(StrEnum):
    """Standard logical pointer buttons mapped by each engine adapter."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    MIDDLE = "middle"
    BACK = "back"
    FORWARD = "forward"


class PointerWheelUnit(StrEnum):
    """Unit carried by a finite two-axis wheel delta."""

    PIXELS = "pixels"
    LINES = "lines"
    PAGES = "pages"


class GamepadButton(StrEnum):
    """Standard-layout logical gamepad buttons."""

    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NORTH = "north"
    LEFT_BUMPER = "left_bumper"
    RIGHT_BUMPER = "right_bumper"
    LEFT_TRIGGER = "left_trigger"
    RIGHT_TRIGGER = "right_trigger"
    SELECT = "select"
    START = "start"
    LEFT_STICK = "left_stick"
    RIGHT_STICK = "right_stick"
    DPAD_UP = "dpad_up"
    DPAD_DOWN = "dpad_down"
    DPAD_LEFT = "dpad_left"
    DPAD_RIGHT = "dpad_right"
    HOME = "home"
    TOUCHPAD = "touchpad"


class GamepadAxis(StrEnum):
    """Standard-layout logical gamepad axes."""

    LEFT_X = "left_x"
    LEFT_Y = "left_y"
    RIGHT_X = "right_x"
    RIGHT_Y = "right_y"


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticInputEvent:
    """One project input-map action state transition."""

    action: str
    pressed: bool
    strength: float

    def __post_init__(self) -> None:
        """Require a bounded action and a canonical normalized state."""
        validate_observation_label(
            self.action,
            maximum_bytes=MAX_SEMANTIC_ACTION_BYTES,
        )
        if not self.action.strip():
            raise ValueError("semantic action is empty")
        if type(self.pressed) is not bool:
            raise ValueError("semantic press state is invalid")
        validate_input_float(
            self.strength,
            minimum=0.0,
            maximum=1.0,
            label="semantic strength",
        )
        if self.pressed != (self.strength > 0.0):
            raise ValueError("semantic strength does not match its press state")


@dataclass(frozen=True, slots=True, kw_only=True)
class KeyboardInputEvent:
    """One normalized physical or logical keyboard state transition."""

    physical_code: str | None
    logical_key: str | None
    location: KeyboardLocation
    modifiers: tuple[KeyboardModifier, ...]
    pressed: bool
    repeated: bool

    def __post_init__(self) -> None:
        """Reject unidentified keys, duplicate modifiers, and invalid repeats."""
        if self.physical_code is not None:
            validate_physical_key_code(self.physical_code)
        if self.logical_key is not None:
            validate_logical_key(self.logical_key)
        if self.physical_code is None and self.logical_key is None:
            raise ValueError("keyboard event requires a physical or logical key")
        if not isinstance(self.location, KeyboardLocation):
            raise ValueError("keyboard location is invalid")
        _validate_modifiers(self.modifiers)
        if type(self.pressed) is not bool or type(self.repeated) is not bool:
            raise ValueError("keyboard state is invalid")
        if self.repeated and not self.pressed:
            raise ValueError("keyboard release cannot be repeated")


@dataclass(frozen=True, slots=True, kw_only=True)
class PointerMoveEvent:
    """One absolute viewport position and corresponding motion delta."""

    x: float
    y: float
    delta_x: float
    delta_y: float

    def __post_init__(self) -> None:
        """Apply the protocol-wide finite coordinate ceiling."""
        _validate_position(self.x, self.y)
        _validate_delta(self.delta_x, label="pointer horizontal motion")
        _validate_delta(self.delta_y, label="pointer vertical motion")


@dataclass(frozen=True, slots=True, kw_only=True)
class PointerButtonEvent:
    """One logical pointer-button state at an explicit viewport position."""

    x: float
    y: float
    button: PointerButton
    pressed: bool

    def __post_init__(self) -> None:
        """Require a finite position, known logical button, and Boolean state."""
        _validate_position(self.x, self.y)
        if not isinstance(self.button, PointerButton):
            raise ValueError("pointer button is invalid")
        if type(self.pressed) is not bool:
            raise ValueError("pointer button state is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class PointerWheelEvent:
    """One non-zero bounded two-axis wheel update at a viewport position."""

    x: float
    y: float
    delta_x: float
    delta_y: float
    unit: PointerWheelUnit

    def __post_init__(self) -> None:
        """Reject empty wheel updates and ambiguous or unbounded units."""
        _validate_position(self.x, self.y)
        validate_input_float(
            self.delta_x,
            minimum=-MAX_POINTER_WHEEL_DELTA,
            maximum=MAX_POINTER_WHEEL_DELTA,
            label="pointer horizontal wheel delta",
        )
        validate_input_float(
            self.delta_y,
            minimum=-MAX_POINTER_WHEEL_DELTA,
            maximum=MAX_POINTER_WHEEL_DELTA,
            label="pointer vertical wheel delta",
        )
        if self.delta_x == 0.0 and self.delta_y == 0.0:
            raise ValueError("pointer wheel delta is empty")
        if not isinstance(self.unit, PointerWheelUnit):
            raise ValueError("pointer wheel unit is invalid")


PointerInputEvent: TypeAlias = PointerMoveEvent | PointerButtonEvent | PointerWheelEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class GamepadButtonEvent:
    """One standard-layout gamepad button state and analog value."""

    button: GamepadButton
    pressed: bool
    value: float

    def __post_init__(self) -> None:
        """Require a canonical normalized button state."""
        if not isinstance(self.button, GamepadButton):
            raise ValueError("gamepad button is invalid")
        if type(self.pressed) is not bool:
            raise ValueError("gamepad button state is invalid")
        validate_input_float(
            self.value,
            minimum=0.0,
            maximum=1.0,
            label="gamepad button value",
        )
        if self.pressed != (self.value > 0.0):
            raise ValueError("gamepad button value does not match its press state")


@dataclass(frozen=True, slots=True, kw_only=True)
class GamepadAxisEvent:
    """One normalized standard-layout gamepad axis update."""

    axis: GamepadAxis
    value: float

    def __post_init__(self) -> None:
        """Require a known axis and finite normalized value."""
        if not isinstance(self.axis, GamepadAxis):
            raise ValueError("gamepad axis is invalid")
        validate_input_float(
            self.value,
            minimum=-1.0,
            maximum=1.0,
            label="gamepad axis value",
        )


GamepadInputEvent: TypeAlias = GamepadButtonEvent | GamepadAxisEvent


def validate_pointer_event_space(
    event: PointerInputEvent,
    coordinate_space: PointerCoordinateSpace,
) -> None:
    """Apply coordinate-space-specific position and motion bounds."""
    if coordinate_space is not PointerCoordinateSpace.VIEWPORT_NORMALIZED:
        return
    validate_input_float(event.x, minimum=0.0, maximum=1.0, label="normalized pointer x")
    validate_input_float(event.y, minimum=0.0, maximum=1.0, label="normalized pointer y")
    if isinstance(event, PointerMoveEvent):
        validate_input_float(
            event.delta_x,
            minimum=-1.0,
            maximum=1.0,
            label="normalized pointer horizontal motion",
        )
        validate_input_float(
            event.delta_y,
            minimum=-1.0,
            maximum=1.0,
            label="normalized pointer vertical motion",
        )


def validate_input_float(
    value: float,
    *,
    minimum: float,
    maximum: float,
    label: str,
) -> None:
    """Reject integer/bool substitutes, non-finite values, and range overflow."""
    if type(value) is not float or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{label} is invalid")


def _validate_modifiers(values: tuple[KeyboardModifier, ...]) -> None:
    """Require one immutable unique subset of the closed modifier set."""
    if (
        not isinstance(values, tuple)
        or len(values) > len(KeyboardModifier)
        or any(not isinstance(value, KeyboardModifier) for value in values)
        or len(set(values)) != len(values)
    ):
        raise ValueError("keyboard modifiers are invalid")


def _validate_position(x: float, y: float) -> None:
    """Require finite non-negative coordinates below the protocol ceiling."""
    validate_input_float(x, minimum=0.0, maximum=MAX_POINTER_COORDINATE, label="pointer x")
    validate_input_float(y, minimum=0.0, maximum=MAX_POINTER_COORDINATE, label="pointer y")


def _validate_delta(value: float, *, label: str) -> None:
    """Require one finite signed motion component below the protocol ceiling."""
    validate_input_float(
        value,
        minimum=-MAX_POINTER_COORDINATE,
        maximum=MAX_POINTER_COORDINATE,
        label=label,
    )
