"""Five focused engine-neutral input service tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError
from toqraq.contracts.bridge_input import (
    GamepadInputParams,
    KeyboardInputParams,
    PointerInputParams,
    SemanticInputParams,
    TextInputParams,
)
from toqraq.core.capability_ids import CONTROL_INPUT_CAPABILITY_ID
from toqraq.core.errors import CapabilityUnavailableError, ProtocolError
from toqraq.services.input import InputService

from _bridge_feature_values import input_commands
from _live_feature_support import make_live_feature_fixture


def test_input_service_preserves_all_five_typed_command_surfaces(tmp_path: Path) -> None:
    async def run() -> None:
        fixture = make_live_feature_fixture(tmp_path)
        semantic, keyboard, pointer, text, gamepad = input_commands()
        service = InputService(fixture.registry, fixture.gate)
        try:
            results = (
                await service.semantic(
                    "hermes-session",
                    SemanticInputParams.from_core(semantic),
                ),
                await service.keyboard(
                    "hermes-session",
                    KeyboardInputParams.from_core(keyboard),
                ),
                await service.pointer(
                    "hermes-session",
                    PointerInputParams.from_core(pointer),
                ),
                await service.text(
                    "hermes-session",
                    TextInputParams.from_core(text),
                ),
                await service.gamepad(
                    "hermes-session",
                    GamepadInputParams.from_core(gamepad),
                ),
            )

            assert tuple(result.accepted_event_count for result in results) == (1, 1, 1, 1, 1)
            assert fixture.input.commands == [semantic, keyboard, pointer, text, gamepad]
            keyboard_json = KeyboardInputParams.from_core(keyboard).model_dump(mode="json")
            assert keyboard_json["events"][0]["physical_code"] == "KeyW"
            assert keyboard_json["events"][0]["logical_key"] == "w"
            assert "keycode" not in keyboard_json["events"][0]
        finally:
            await fixture.close()

    asyncio.run(run())


def test_keyboard_contract_requires_w3c_identity() -> None:
    with pytest.raises(ValidationError):
        KeyboardInputParams.model_validate({"events": [{"keycode": 65, "pressed": True}]})


def test_input_requires_control_readiness(tmp_path: Path) -> None:
    async def run() -> None:
        fixture = make_live_feature_fixture(tmp_path, publish_features=False)
        semantic, *_rest = input_commands()
        try:
            with pytest.raises(CapabilityUnavailableError) as captured:
                await InputService(fixture.registry, fixture.gate).semantic(
                    "hermes-session",
                    SemanticInputParams.from_core(semantic),
                )
            assert captured.value.parameters == {"capability_id": CONTROL_INPUT_CAPABILITY_ID}
            assert captured.value.details == {
                "reason": "control_not_ready",
                "state": "connecting",
            }
        finally:
            await fixture.close()

    asyncio.run(run())


def test_partial_input_acknowledgement_is_a_protocol_error(tmp_path: Path) -> None:
    async def run() -> None:
        fixture = make_live_feature_fixture(tmp_path)
        semantic, *_rest = input_commands()
        fixture.input.accepted_event_count = 2
        try:
            with pytest.raises(ProtocolError) as captured:
                await InputService(fixture.registry, fixture.gate).semantic(
                    "hermes-session",
                    SemanticInputParams.from_core(semantic),
                )
            assert captured.value.parameters == {"operation": CONTROL_INPUT_CAPABILITY_ID}
            assert captured.value.details == {"reason": "result_contract_invalid"}
        finally:
            await fixture.close()

    asyncio.run(run())
