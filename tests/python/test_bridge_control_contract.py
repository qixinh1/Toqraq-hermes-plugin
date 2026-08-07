"""Strict bridge simulation, input, and cancellation DTO contract tests."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError
from toqraq.contracts.bridge_input import (
    GAMEPAD_INPUT_METHOD,
    KEYBOARD_INPUT_METHOD,
    POINTER_INPUT_METHOD,
    SEMANTIC_INPUT_METHOD,
    TEXT_INPUT_METHOD,
    GamepadInputRequest,
    InputAcknowledgementResponse,
    KeyboardInputRequest,
    PointerInputRequest,
    SemanticInputRequest,
    TextInputRequest,
)
from toqraq.contracts.bridge_simulation import (
    SIMULATION_SET_PAUSED_METHOD,
    SIMULATION_STEP_METHOD,
    SimulationSetPausedRequest,
    SimulationSetPausedResponse,
    SimulationStepRequest,
    SimulationStepResponse,
)
from toqraq.core.input_control import (
    MAX_GAMEPAD_SLOT,
    MAX_INPUT_EVENTS,
    MAX_POINTER_ID,
    MAX_TEXT_INPUT_BYTES,
    GamepadInputCommand,
    InputAcknowledgement,
    KeyboardInputCommand,
    PointerInputCommand,
    SemanticInputCommand,
    TextInputCommand,
)
from toqraq.core.observation import ObservationRevision
from toqraq.core.player_input import (
    MAX_POINTER_WHEEL_DELTA,
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
from toqraq.core.simulation_control import (
    MAX_SIMULATION_STEP_FRAMES,
    SetPausedAcknowledgement,
    SetPausedCommand,
    StepFramesAcknowledgement,
    StepFramesCommand,
)


def _revision(value: str) -> ObservationRevision:
    return ObservationRevision(value=value)


def _input_acknowledgement(count: int) -> InputAcknowledgement:
    return InputAcknowledgement(accepted_event_count=count)


def _semantic_command() -> SemanticInputCommand:
    return SemanticInputCommand(
        events=(
            SemanticInputEvent(action="player.jump", pressed=True, strength=1.0),
            SemanticInputEvent(action="player.jump", pressed=False, strength=0.0),
        )
    )


def _keyboard_command() -> KeyboardInputCommand:
    return KeyboardInputCommand(
        events=(
            KeyboardInputEvent(
                physical_code="KeyW",
                logical_key="w",
                location=KeyboardLocation.STANDARD,
                modifiers=(KeyboardModifier.SHIFT,),
                pressed=True,
                repeated=False,
            ),
        )
    )


def _pointer_command() -> PointerInputCommand:
    return PointerInputCommand(
        pointer_id=2,
        pointer_kind=PointerKind.PEN,
        coordinate_space=PointerCoordinateSpace.VIEWPORT_NORMALIZED,
        events=(
            PointerMoveEvent(x=0.25, y=0.75, delta_x=0.1, delta_y=-0.1),
            PointerButtonEvent(
                x=0.25,
                y=0.75,
                button=PointerButton.PRIMARY,
                pressed=True,
            ),
            PointerWheelEvent(
                x=0.25,
                y=0.75,
                delta_x=0.0,
                delta_y=-2.0,
                unit=PointerWheelUnit.LINES,
            ),
        ),
    )


def _gamepad_command() -> GamepadInputCommand:
    return GamepadInputCommand(
        device_slot=1,
        events=(
            GamepadButtonEvent(
                button=GamepadButton.SOUTH,
                pressed=True,
                value=0.8,
            ),
            GamepadAxisEvent(axis=GamepadAxis.LEFT_X, value=-0.5),
        ),
    )


def test_simulation_requests_and_acknowledgements_round_trip_exact_revisions() -> None:
    pause_command = SetPausedCommand(paused=True)
    pause_value = SetPausedAcknowledgement(
        paused=True,
        changed=False,
        simulation_revision=_revision("simulation:12"),
        frame_revision=_revision("frame:40"),
    )
    pause_request = SimulationSetPausedRequest.from_core(
        request_id="host-1",
        command=pause_command,
    )
    pause_response = SimulationSetPausedResponse.from_core(
        request_id=pause_request.id,
        value=pause_value,
        command=pause_command,
    )

    assert pause_request.method == SIMULATION_SET_PAUSED_METHOD
    assert pause_request.params.to_core() == pause_command
    assert pause_response.result.to_core(command=pause_command) == pause_value
    assert pause_response.model_dump(mode="json")["result"] == {
        "paused": True,
        "changed": False,
        "simulation_revision": "simulation:12",
        "frame_revision": "frame:40",
    }

    step_command = StepFramesCommand(frame_count=MAX_SIMULATION_STEP_FRAMES)
    step_value = StepFramesAcknowledgement(
        frame_count=MAX_SIMULATION_STEP_FRAMES,
        paused=True,
        simulation_revision=_revision("simulation:13"),
        frame_revision=_revision("frame:160"),
    )
    step_request = SimulationStepRequest.from_core(
        request_id="host-2",
        command=step_command,
    )
    step_response = SimulationStepResponse.from_core(
        request_id=step_request.id,
        value=step_value,
        command=step_command,
    )

    assert step_request.method == SIMULATION_STEP_METHOD
    assert step_request.params.to_core() == step_command
    assert step_response.result.to_core(command=step_command) == step_value
    assert "kind" not in step_response.model_dump(mode="json")["result"]


def test_simulation_contract_rejects_toggle_partial_and_resumed_shapes() -> None:
    request = SimulationSetPausedRequest.from_core(
        request_id="host-1",
        command=SetPausedCommand(paused=True),
    ).model_dump(mode="json")
    invalid = deepcopy(request)
    invalid["params"] = {"toggle": True}
    with pytest.raises(ValidationError):
        SimulationSetPausedRequest.model_validate(invalid)

    pause_command = SetPausedCommand(paused=True)
    pause_value = SetPausedAcknowledgement(
        paused=True,
        changed=True,
        simulation_revision=_revision("simulation:13"),
        frame_revision=_revision("frame:41"),
    )
    pause_response = SimulationSetPausedResponse.from_core(
        request_id="host-1",
        value=pause_value,
        command=pause_command,
    )
    with pytest.raises(ValueError, match="does not match its command"):
        pause_response.result.to_core(command=SetPausedCommand(paused=False))
    with pytest.raises(ValueError, match="does not match its command"):
        SimulationSetPausedResponse.from_core(
            request_id="host-1",
            value=pause_value,
            command=SetPausedCommand(paused=False),
        )

    step = SimulationStepRequest.from_core(
        request_id="host-2",
        command=StepFramesCommand(frame_count=1),
    ).model_dump(mode="json")
    invalid = deepcopy(step)
    invalid["params"]["frame_count"] = MAX_SIMULATION_STEP_FRAMES + 1
    with pytest.raises(ValidationError):
        SimulationStepRequest.model_validate(invalid)

    response = SimulationStepResponse.from_core(
        request_id="host-2",
        value=StepFramesAcknowledgement(
            frame_count=1,
            paused=True,
            simulation_revision=_revision("simulation:13"),
            frame_revision=_revision("frame:41"),
        ),
        command=StepFramesCommand(frame_count=1),
    ).model_dump(mode="json")
    invalid = deepcopy(response)
    invalid["result"]["paused"] = False
    with pytest.raises(ValidationError):
        SimulationStepResponse.model_validate(invalid)
    invalid = deepcopy(response)
    invalid["result"]["advanced_frames"] = 0
    with pytest.raises(ValidationError, match="Extra inputs"):
        SimulationStepResponse.model_validate(invalid)
    invalid = deepcopy(response)
    invalid["result"]["kind"] = "simulation_step"
    with pytest.raises(ValidationError, match="Extra inputs"):
        SimulationStepResponse.model_validate(invalid)
    with pytest.raises(ValueError, match="does not match its command"):
        SimulationStepResponse.from_core(
            request_id="host-2",
            value=StepFramesAcknowledgement(
                frame_count=1,
                paused=True,
                simulation_revision=_revision("simulation:13"),
                frame_revision=_revision("frame:41"),
            ),
            command=StepFramesCommand(frame_count=2),
        )


def test_semantic_and_keyboard_requests_round_trip_without_generic_events() -> None:
    semantic = SemanticInputRequest.from_core(
        request_id="host-3",
        command=_semantic_command(),
    )
    keyboard = KeyboardInputRequest.from_core(
        request_id="host-4",
        command=_keyboard_command(),
    )

    assert semantic.method == SEMANTIC_INPUT_METHOD
    assert keyboard.method == KEYBOARD_INPUT_METHOD
    assert semantic.params.to_core() == _semantic_command()
    assert keyboard.params.to_core() == _keyboard_command()
    assert semantic.model_dump(mode="json")["params"]["events"][0] == {
        "action": "player.jump",
        "pressed": True,
        "strength": 1.0,
    }
    assert keyboard.model_dump(mode="json")["params"]["events"][0] == {
        "physical_code": "KeyW",
        "logical_key": "w",
        "location": "standard",
        "modifiers": ["shift"],
        "pressed": True,
        "repeated": False,
    }


def test_pointer_text_and_gamepad_requests_round_trip_typed_values() -> None:
    pointer = PointerInputRequest.from_core(
        request_id="host-5",
        command=_pointer_command(),
    )
    text = TextInputRequest.from_core(
        request_id="host-6",
        command=TextInputCommand(text="玩家\nready"),
    )
    gamepad = GamepadInputRequest.from_core(
        request_id="host-7",
        command=_gamepad_command(),
    )

    assert pointer.method == POINTER_INPUT_METHOD
    assert text.method == TEXT_INPUT_METHOD
    assert gamepad.method == GAMEPAD_INPUT_METHOD
    assert pointer.params.to_core() == _pointer_command()
    assert text.params.to_core() == TextInputCommand(text="玩家\nready")
    assert gamepad.params.to_core() == _gamepad_command()
    assert [event["kind"] for event in pointer.model_dump(mode="json")["params"]["events"]] == [
        "motion",
        "button",
        "wheel",
    ]
    assert [event["kind"] for event in gamepad.model_dump(mode="json")["params"]["events"]] == [
        "button",
        "axis",
    ]


def test_input_acknowledgement_is_correlated_without_synthetic_revisions() -> None:
    command = _pointer_command()
    value = _input_acknowledgement(3)
    response = InputAcknowledgementResponse.from_core(
        request_id="host-5",
        value=value,
        command=command,
    )

    assert response.result.to_core(command=command) == value
    assert response.model_dump(mode="json")["result"] == {
        "accepted_event_count": 3,
    }
    with pytest.raises(ValueError, match="does not match"):
        response.result.to_core(command=_keyboard_command())
    with pytest.raises(ValueError, match="does not match"):
        InputAcknowledgementResponse.from_core(
            request_id="host-5",
            value=_input_acknowledgement(2),
            command=command,
        )


def test_input_contract_rejects_bad_batches_keys_text_devices_and_coordinates() -> None:
    semantic = SemanticInputRequest.from_core(
        request_id="host-3",
        command=_semantic_command(),
    ).model_dump(mode="json")
    invalid = deepcopy(semantic)
    invalid["params"]["events"] = invalid["params"]["events"][:1] * (MAX_INPUT_EVENTS + 1)
    with pytest.raises(ValidationError):
        SemanticInputRequest.model_validate(invalid)

    keyboard = KeyboardInputRequest.from_core(
        request_id="host-4",
        command=_keyboard_command(),
    ).model_dump(mode="json")
    invalid = deepcopy(keyboard)
    invalid["params"]["events"][0]["physical_code"] = None
    invalid["params"]["events"][0]["logical_key"] = None
    with pytest.raises(ValidationError, match="requires a physical or logical key"):
        KeyboardInputRequest.model_validate(invalid)
    invalid = deepcopy(keyboard)
    invalid["params"]["events"][0]["modifiers"] = ["alt", "alt"]
    with pytest.raises(ValidationError, match="must be unique"):
        KeyboardInputRequest.model_validate(invalid)
    invalid = deepcopy(keyboard)
    invalid["params"]["events"][0]["physical_code"] = "MediaPlayPause"
    with pytest.raises(ValidationError, match="common W3C baseline"):
        KeyboardInputRequest.model_validate(invalid)
    invalid = deepcopy(keyboard)
    invalid["params"]["events"][0]["physical_code"] = None
    invalid["params"]["events"][0]["logical_key"] = "madeUpNamedKey"
    with pytest.raises(ValidationError, match="W3C key string"):
        KeyboardInputRequest.model_validate(invalid)

    pointer = PointerInputRequest.from_core(
        request_id="host-5",
        command=_pointer_command(),
    ).model_dump(mode="json")
    invalid = deepcopy(pointer)
    invalid["params"]["pointer_id"] = MAX_POINTER_ID + 1
    with pytest.raises(ValidationError):
        PointerInputRequest.model_validate(invalid)
    invalid = deepcopy(pointer)
    invalid["params"]["events"][0]["x"] = 1.01
    with pytest.raises(ValidationError, match="normalized pointer x"):
        PointerInputRequest.model_validate(invalid)
    invalid = deepcopy(pointer)
    invalid["params"]["events"][2]["delta_y"] = MAX_POINTER_WHEEL_DELTA + 1.0
    with pytest.raises(ValidationError):
        PointerInputRequest.model_validate(invalid)

    text = TextInputRequest.from_core(
        request_id="host-6",
        command=TextInputCommand(text="safe"),
    ).model_dump(mode="json")
    invalid = deepcopy(text)
    invalid["params"]["text"] = "a" * (MAX_TEXT_INPUT_BYTES + 1)
    with pytest.raises(ValidationError):
        TextInputRequest.model_validate(invalid)
    invalid = deepcopy(text)
    invalid["params"]["text"] = "source\0text"
    with pytest.raises(ValidationError, match="null"):
        TextInputRequest.model_validate(invalid)

    gamepad = GamepadInputRequest.from_core(
        request_id="host-7",
        command=_gamepad_command(),
    ).model_dump(mode="json")
    invalid = deepcopy(gamepad)
    invalid["params"]["device_slot"] = MAX_GAMEPAD_SLOT + 1
    with pytest.raises(ValidationError):
        GamepadInputRequest.model_validate(invalid)
    invalid = deepcopy(gamepad)
    invalid["params"]["events"][0]["callback"] = "native.execute"
    with pytest.raises(ValidationError, match="Extra inputs"):
        GamepadInputRequest.model_validate(invalid)
