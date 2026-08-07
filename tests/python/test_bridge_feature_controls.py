"""Real-socket conformance for focused common Bridge simulation and input ports."""

from __future__ import annotations

import asyncio

from toqraq.bridge.bridge_features.aggregate import create_bridge_feature_ports
from toqraq.contracts.bridge_input import (
    GamepadInputRequest,
    InputAcknowledgementResponse,
    KeyboardInputRequest,
    PointerInputRequest,
    SemanticInputRequest,
    TextInputRequest,
)
from toqraq.contracts.bridge_simulation import (
    SimulationSetPausedRequest,
    SimulationSetPausedResponse,
    SimulationStepRequest,
    SimulationStepResponse,
)
from toqraq.core.input_control import InputAcknowledgement
from toqraq.core.simulation_control import (
    SetPausedAcknowledgement,
    SetPausedCommand,
    StepFramesAcknowledgement,
    StepFramesCommand,
)

from _bridge_feature_values import input_commands, revision
from _bridge_rpc_support import open_rpc_harness, receive_json


def test_simulation_adapter_correlates_pause_state_and_step_count() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness()
        features = create_bridge_feature_ports(harness.authenticated)

        pause_command = SetPausedCommand(paused=True)
        pause_value = SetPausedAcknowledgement(
            paused=True,
            changed=True,
            simulation_revision=revision("simulation:1"),
            frame_revision=revision("frame:1"),
        )
        pause_call = asyncio.create_task(features.simulation.set_paused(pause_command))
        wire = await receive_json(harness.peer)
        pause_request = SimulationSetPausedRequest.model_validate(wire)
        assert pause_request.params.to_core() == pause_command
        await harness.peer.send(
            SimulationSetPausedResponse.from_core(
                request_id=pause_request.id,
                value=pause_value,
                command=pause_command,
            ).model_dump_json()
        )
        assert await pause_call == pause_value

        step_command = StepFramesCommand(frame_count=2)
        step_value = StepFramesAcknowledgement(
            frame_count=2,
            paused=True,
            simulation_revision=revision("simulation:3"),
            frame_revision=revision("frame:3"),
        )
        step_call = asyncio.create_task(features.simulation.step(step_command))
        wire = await receive_json(harness.peer)
        step_request = SimulationStepRequest.model_validate(wire)
        assert step_request.params.to_core() == step_command
        await harness.peer.send(
            SimulationStepResponse.from_core(
                request_id=step_request.id,
                value=step_value,
                command=step_command,
            ).model_dump_json()
        )
        assert await step_call == step_value

        await harness.close()

    asyncio.run(scenario())


def test_input_adapter_keeps_all_five_methods_exact_and_separate() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness()
        features = create_bridge_feature_ports(harness.authenticated)
        semantic, keyboard, pointer, text, gamepad = input_commands()
        acknowledgement = InputAcknowledgement(accepted_event_count=1)

        semantic_call = asyncio.create_task(features.input.semantic(semantic))
        wire = await receive_json(harness.peer)
        semantic_request = SemanticInputRequest.model_validate(wire)
        assert semantic_request.params.to_core() == semantic
        await harness.peer.send(
            InputAcknowledgementResponse.from_core(
                request_id=semantic_request.id,
                value=acknowledgement,
                command=semantic,
            ).model_dump_json()
        )
        assert await semantic_call == acknowledgement

        keyboard_call = asyncio.create_task(features.input.keyboard(keyboard))
        wire = await receive_json(harness.peer)
        keyboard_request = KeyboardInputRequest.model_validate(wire)
        assert keyboard_request.params.to_core() == keyboard
        await harness.peer.send(
            InputAcknowledgementResponse.from_core(
                request_id=keyboard_request.id,
                value=acknowledgement,
                command=keyboard,
            ).model_dump_json()
        )
        assert await keyboard_call == acknowledgement

        pointer_call = asyncio.create_task(features.input.pointer(pointer))
        wire = await receive_json(harness.peer)
        pointer_request = PointerInputRequest.model_validate(wire)
        assert pointer_request.params.to_core() == pointer
        await harness.peer.send(
            InputAcknowledgementResponse.from_core(
                request_id=pointer_request.id,
                value=acknowledgement,
                command=pointer,
            ).model_dump_json()
        )
        assert await pointer_call == acknowledgement

        text_call = asyncio.create_task(features.input.text(text))
        wire = await receive_json(harness.peer)
        text_request = TextInputRequest.model_validate(wire)
        assert text_request.params.to_core() == text
        await harness.peer.send(
            InputAcknowledgementResponse.from_core(
                request_id=text_request.id,
                value=acknowledgement,
                command=text,
            ).model_dump_json()
        )
        assert await text_call == acknowledgement

        gamepad_call = asyncio.create_task(features.input.gamepad(gamepad))
        wire = await receive_json(harness.peer)
        gamepad_request = GamepadInputRequest.model_validate(wire)
        assert gamepad_request.params.to_core() == gamepad
        await harness.peer.send(
            InputAcknowledgementResponse.from_core(
                request_id=gamepad_request.id,
                value=acknowledgement,
                command=gamepad,
            ).model_dump_json()
        )
        assert await gamepad_call == acknowledgement

        await harness.close()

    asyncio.run(scenario())
