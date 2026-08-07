"""Pure simulation, input, and cancellation control invariants."""

from __future__ import annotations

import math

import pytest
from toqraq.core.bridge import BridgeRequestReference
from toqraq.core.input_control import (
    MAX_GAMEPAD_SLOT,
    MAX_INPUT_EVENTS,
    MAX_POINTER_ID,
    MAX_TEXT_INPUT_BYTES,
    GamepadInputCommand,
    InputAcknowledgement,
    InputController,
    KeyboardInputCommand,
    PointerInputCommand,
    SemanticInputCommand,
    TextInputCommand,
    input_command_event_count,
    validate_input_acknowledgement,
)
from toqraq.core.keyboard_standard import MAX_LOGICAL_KEY_BYTES
from toqraq.core.observation import ObservationRevision
from toqraq.core.player_input import (
    MAX_POINTER_COORDINATE,
    MAX_POINTER_WHEEL_DELTA,
    MAX_SEMANTIC_ACTION_BYTES,
    GamepadAxis,
    GamepadAxisEvent,
    GamepadButton,
    GamepadButtonEvent,
    KeyboardInputEvent,
    KeyboardLocation,
    KeyboardModifier,
    PointerButton,
    PointerButtonEvent,
    PointerCoordinateSpace,
    PointerKind,
    PointerMoveEvent,
    PointerWheelEvent,
    PointerWheelUnit,
    SemanticInputEvent,
)
from toqraq.core.request_cancellation import (
    CancellationAcknowledgement,
    CancellationDisposition,
    CancelRequestCommand,
)
from toqraq.core.simulation_control import (
    MAX_SIMULATION_STEP_FRAMES,
    SetPausedAcknowledgement,
    SetPausedCommand,
    SimulationController,
    StepFramesAcknowledgement,
    StepFramesCommand,
)


def _revision(value: str) -> ObservationRevision:
    return ObservationRevision(value=value)


def _semantic(*, pressed: bool = True) -> SemanticInputEvent:
    return SemanticInputEvent(
        action="player.jump",
        pressed=pressed,
        strength=1.0 if pressed else 0.0,
    )


def _keyboard() -> KeyboardInputEvent:
    return KeyboardInputEvent(
        physical_code="KeyW",
        logical_key="w",
        location=KeyboardLocation.STANDARD,
        modifiers=(KeyboardModifier.SHIFT,),
        pressed=True,
        repeated=False,
    )


def test_bridge_request_reference_uses_exact_envelope_identity_syntax() -> None:
    assert BridgeRequestReference(value="input:player-1").value == "input:player-1"
    assert BridgeRequestReference(value="r" * 128).value == "r" * 128

    for invalid in ("", "_starts-with-symbol", "contains space", "x" * 129):
        with pytest.raises(ValueError, match="request ID"):
            BridgeRequestReference(value=invalid)


def test_simulation_values_make_pause_idempotence_and_step_bounds_explicit() -> None:
    command = SetPausedCommand(paused=True)
    acknowledgement = SetPausedAcknowledgement(
        paused=True,
        changed=False,
        simulation_revision=_revision("simulation:4"),
        frame_revision=_revision("frame:9"),
    )

    assert command.paused is True
    assert acknowledgement.changed is False
    assert StepFramesCommand(frame_count=MAX_SIMULATION_STEP_FRAMES).frame_count == 120
    assert StepFramesAcknowledgement(
        frame_count=2,
        paused=True,
        simulation_revision=_revision("simulation:5"),
        frame_revision=_revision("frame:11"),
    ).paused

    for invalid in (False, 0, MAX_SIMULATION_STEP_FRAMES + 1):
        with pytest.raises(ValueError, match="frame count"):
            StepFramesCommand(frame_count=invalid)
    with pytest.raises(ValueError, match="remain paused"):
        StepFramesAcknowledgement(
            frame_count=1,
            paused=False,
            simulation_revision=_revision("simulation:5"),
            frame_revision=_revision("frame:10"),
        )


def test_semantic_events_bound_utf8_and_canonicalize_press_strength() -> None:
    assert (
        SemanticInputEvent(
            action="a" * MAX_SEMANTIC_ACTION_BYTES,
            pressed=True,
            strength=1.0,
        ).action
        == "a" * MAX_SEMANTIC_ACTION_BYTES
    )
    assert (
        SemanticInputEvent(
            action="界" * (MAX_SEMANTIC_ACTION_BYTES // 3),
            pressed=True,
            strength=0.5,
        ).strength
        == 0.5
    )

    with pytest.raises(ValueError, match="byte bound"):
        SemanticInputEvent(
            action="界" * (MAX_SEMANTIC_ACTION_BYTES // 3 + 1),
            pressed=True,
            strength=1.0,
        )
    with pytest.raises(ValueError, match="byte bound"):
        SemanticInputEvent(
            action="a" * (MAX_SEMANTIC_ACTION_BYTES + 1),
            pressed=True,
            strength=1.0,
        )
    for pressed, strength in ((False, 0.1), (True, 0.0)):
        with pytest.raises(ValueError, match="press state"):
            SemanticInputEvent(action="jump", pressed=pressed, strength=strength)


def test_keyboard_events_require_normalized_identity_and_consistent_state() -> None:
    boundary = KeyboardInputEvent(
        physical_code="IntlRo",
        logical_key="é",
        location=KeyboardLocation.STANDARD,
        modifiers=(),
        pressed=True,
        repeated=False,
    )
    assert boundary.physical_code == "IntlRo"
    assert boundary.logical_key == "é"
    assert _keyboard().modifiers == (KeyboardModifier.SHIFT,)
    assert (
        KeyboardInputEvent(
            physical_code=None,
            logical_key=" ",
            location=KeyboardLocation.STANDARD,
            modifiers=(),
            pressed=True,
            repeated=False,
        ).logical_key
        == " "
    )

    with pytest.raises(ValueError, match="requires a physical or logical key"):
        KeyboardInputEvent(
            physical_code=None,
            logical_key=None,
            location=KeyboardLocation.STANDARD,
            modifiers=(),
            pressed=True,
            repeated=False,
        )
    with pytest.raises(ValueError, match="physical key"):
        KeyboardInputEvent(
            physical_code="Key-W",
            logical_key=None,
            location=KeyboardLocation.STANDARD,
            modifiers=(),
            pressed=True,
            repeated=False,
        )
    with pytest.raises(ValueError, match="physical key"):
        KeyboardInputEvent(
            physical_code="MediaPlayPause",
            logical_key=None,
            location=KeyboardLocation.STANDARD,
            modifiers=(),
            pressed=True,
            repeated=False,
        )
    with pytest.raises(ValueError, match="byte bound"):
        KeyboardInputEvent(
            physical_code=None,
            logical_key="a" * (MAX_LOGICAL_KEY_BYTES + 1),
            location=KeyboardLocation.STANDARD,
            modifiers=(),
            pressed=True,
            repeated=False,
        )
    with pytest.raises(ValueError, match="NFC"):
        KeyboardInputEvent(
            physical_code=None,
            logical_key="e\u0301",
            location=KeyboardLocation.STANDARD,
            modifiers=(),
            pressed=True,
            repeated=False,
        )
    with pytest.raises(ValueError, match="W3C key string"):
        KeyboardInputEvent(
            physical_code=None,
            logical_key="madeUpNamedKey",
            location=KeyboardLocation.STANDARD,
            modifiers=(),
            pressed=True,
            repeated=False,
        )
    with pytest.raises(ValueError, match="modifiers"):
        KeyboardInputEvent(
            physical_code="KeyW",
            logical_key="w",
            location=KeyboardLocation.STANDARD,
            modifiers=(KeyboardModifier.ALT, KeyboardModifier.ALT),
            pressed=True,
            repeated=False,
        )
    with pytest.raises(ValueError, match="release cannot be repeated"):
        KeyboardInputEvent(
            physical_code="KeyW",
            logical_key="w",
            location=KeyboardLocation.STANDARD,
            modifiers=(),
            pressed=False,
            repeated=True,
        )


def test_pointer_values_enforce_global_and_coordinate_space_bounds() -> None:
    pixel_event = PointerMoveEvent(
        x=MAX_POINTER_COORDINATE,
        y=0.0,
        delta_x=-MAX_POINTER_COORDINATE,
        delta_y=MAX_POINTER_COORDINATE,
    )
    assert PointerInputCommand(
        pointer_id=MAX_POINTER_ID,
        pointer_kind=PointerKind.MOUSE,
        coordinate_space=PointerCoordinateSpace.VIEWPORT_PIXELS,
        events=(pixel_event,),
    ).events == (pixel_event,)

    with pytest.raises(ValueError, match="normalized pointer x"):
        PointerInputCommand(
            pointer_id=0,
            pointer_kind=PointerKind.TOUCH,
            coordinate_space=PointerCoordinateSpace.VIEWPORT_NORMALIZED,
            events=(PointerMoveEvent(x=1.01, y=0.5, delta_x=0.0, delta_y=0.0),),
        )
    with pytest.raises(ValueError, match="pointer x"):
        PointerMoveEvent(
            x=MAX_POINTER_COORDINATE + 1.0,
            y=0.0,
            delta_x=0.0,
            delta_y=0.0,
        )
    with pytest.raises(ValueError, match="pointer ID"):
        PointerInputCommand(
            pointer_id=MAX_POINTER_ID + 1,
            pointer_kind=PointerKind.MOUSE,
            coordinate_space=PointerCoordinateSpace.VIEWPORT_PIXELS,
            events=(pixel_event,),
        )


def test_pointer_button_and_wheel_events_are_typed_and_non_empty() -> None:
    button = PointerButtonEvent(
        x=1.0,
        y=2.0,
        button=PointerButton.PRIMARY,
        pressed=True,
    )
    wheel = PointerWheelEvent(
        x=1.0,
        y=2.0,
        delta_x=0.0,
        delta_y=MAX_POINTER_WHEEL_DELTA,
        unit=PointerWheelUnit.LINES,
    )
    assert button.button is PointerButton.PRIMARY
    assert wheel.unit is PointerWheelUnit.LINES

    with pytest.raises(ValueError, match="wheel delta is empty"):
        PointerWheelEvent(
            x=0.0,
            y=0.0,
            delta_x=0.0,
            delta_y=0.0,
            unit=PointerWheelUnit.PIXELS,
        )
    with pytest.raises(ValueError, match="wheel delta"):
        PointerWheelEvent(
            x=0.0,
            y=0.0,
            delta_x=0.0,
            delta_y=math.inf,
            unit=PointerWheelUnit.PIXELS,
        )


def test_text_and_input_batches_have_validation_atomic_bounds() -> None:
    assert len(TextInputCommand(text="a" * MAX_TEXT_INPUT_BYTES).text) == MAX_TEXT_INPUT_BYTES
    assert len(SemanticInputCommand(events=(_semantic(),) * MAX_INPUT_EVENTS).events) == 128
    assert len(KeyboardInputCommand(events=(_keyboard(),)).events) == 1

    with pytest.raises(ValueError, match="byte bound"):
        TextInputCommand(text="a" * (MAX_TEXT_INPUT_BYTES + 1))
    with pytest.raises(ValueError, match="null"):
        TextInputCommand(text="unsafe\0text")
    for events in ((), (_semantic(),) * (MAX_INPUT_EVENTS + 1)):
        with pytest.raises(ValueError, match="event batch"):
            SemanticInputCommand(events=events)


def test_gamepad_values_bound_slot_controls_and_normalized_values() -> None:
    events = (
        GamepadButtonEvent(button=GamepadButton.SOUTH, pressed=True, value=1.0),
        GamepadAxisEvent(axis=GamepadAxis.LEFT_X, value=-1.0),
    )
    assert GamepadInputCommand(device_slot=MAX_GAMEPAD_SLOT, events=events).events == events

    with pytest.raises(ValueError, match="gamepad slot"):
        GamepadInputCommand(device_slot=MAX_GAMEPAD_SLOT + 1, events=events)
    with pytest.raises(ValueError, match="press state"):
        GamepadButtonEvent(button=GamepadButton.SOUTH, pressed=False, value=0.2)
    with pytest.raises(ValueError, match="axis value"):
        GamepadAxisEvent(axis=GamepadAxis.LEFT_X, value=1.01)


def test_acknowledgement_and_ports_remain_focused_typed_boundaries() -> None:
    acknowledgement = InputAcknowledgement(accepted_event_count=1)

    class Controls:
        async def semantic(self, command: SemanticInputCommand) -> InputAcknowledgement:
            return acknowledgement

        async def keyboard(self, command: KeyboardInputCommand) -> InputAcknowledgement:
            return acknowledgement

        async def pointer(self, command: PointerInputCommand) -> InputAcknowledgement:
            return acknowledgement

        async def text(self, command: TextInputCommand) -> InputAcknowledgement:
            return acknowledgement

        async def gamepad(self, command: GamepadInputCommand) -> InputAcknowledgement:
            return acknowledgement

    class Simulation:
        async def set_paused(self, command: SetPausedCommand) -> SetPausedAcknowledgement:
            return SetPausedAcknowledgement(
                paused=command.paused,
                changed=False,
                simulation_revision=_revision("simulation:10"),
                frame_revision=_revision("frame:20"),
            )

        async def step(self, command: StepFramesCommand) -> StepFramesAcknowledgement:
            return StepFramesAcknowledgement(
                frame_count=command.frame_count,
                paused=True,
                simulation_revision=_revision("simulation:11"),
                frame_revision=_revision("frame:21"),
            )

    assert isinstance(Controls(), InputController)
    assert isinstance(Simulation(), SimulationController)
    assert (
        InputAcknowledgement(accepted_event_count=MAX_INPUT_EVENTS).accepted_event_count
        == MAX_INPUT_EVENTS
    )
    assert input_command_event_count(TextInputCommand(text="x")) == 1
    validate_input_acknowledgement(acknowledgement, KeyboardInputCommand(events=(_keyboard(),)))
    with pytest.raises(ValueError, match="does not match"):
        validate_input_acknowledgement(
            acknowledgement,
            SemanticInputCommand(events=(_semantic(), _semantic(pressed=False))),
        )
    for invalid in (0, MAX_INPUT_EVENTS + 1):
        with pytest.raises(ValueError, match="accepted input event count"):
            InputAcknowledgement(accepted_event_count=invalid)


def test_cancellation_command_owns_target_and_result_has_closed_disposition() -> None:
    target = BridgeRequestReference(value="frame:pending-1")
    command = CancelRequestCommand(target=target)
    acknowledgement = CancellationAcknowledgement(
        disposition=CancellationDisposition.ALREADY_TERMINAL,
    )

    assert command.target is target
    assert acknowledgement.disposition is CancellationDisposition.ALREADY_TERMINAL
