"""Five focused engine-neutral live player-input use cases."""

from __future__ import annotations

from ..contracts.bridge_input import (
    GamepadInputParams,
    InputAcknowledgementValue,
    KeyboardInputParams,
    PointerInputParams,
    SemanticInputParams,
    TextInputParams,
)
from ..contracts.identifiers import HermesSessionId
from ..core.capability_ids import CONTROL_INPUT_CAPABILITY_ID
from ..core.session_registry import SessionRegistry
from .session_feature_access import (
    control_access,
    validate_feature_dependencies,
    verified_feature_result,
)
from .session_gate import SessionOperationGate


class InputService:
    """Apply validation-atomic semantic, keyboard, pointer, text, and gamepad input."""

    __slots__ = ("_gate", "_registry")

    def __init__(self, registry: SessionRegistry, gate: SessionOperationGate) -> None:
        """Share the exact registry and operation gate with session lifecycle."""
        validate_feature_dependencies(registry, gate)
        self._registry = registry
        self._gate = gate

    async def semantic(
        self,
        session_id: HermesSessionId,
        request: SemanticInputParams,
    ) -> InputAcknowledgementValue:
        """Apply one complete ordered project-action batch."""
        command = request.to_core()
        async with control_access(
            self._registry,
            self._gate,
            session_id,
            CONTROL_INPUT_CAPABILITY_ID,
        ) as access:
            acknowledgement = await access.resources.invoke_owned(
                access.ports.input.semantic(command)
            )
            return verified_feature_result(
                CONTROL_INPUT_CAPABILITY_ID,
                lambda: InputAcknowledgementValue.from_core(
                    acknowledgement,
                    command=command,
                ),
            )

    async def keyboard(
        self,
        session_id: HermesSessionId,
        request: KeyboardInputParams,
    ) -> InputAcknowledgementValue:
        """Apply one complete ordered W3C keyboard batch."""
        command = request.to_core()
        async with control_access(
            self._registry,
            self._gate,
            session_id,
            CONTROL_INPUT_CAPABILITY_ID,
        ) as access:
            acknowledgement = await access.resources.invoke_owned(
                access.ports.input.keyboard(command)
            )
            return verified_feature_result(
                CONTROL_INPUT_CAPABILITY_ID,
                lambda: InputAcknowledgementValue.from_core(
                    acknowledgement,
                    command=command,
                ),
            )

    async def pointer(
        self,
        session_id: HermesSessionId,
        request: PointerInputParams,
    ) -> InputAcknowledgementValue:
        """Apply one pointer device batch in its explicit coordinate space."""
        command = request.to_core()
        async with control_access(
            self._registry,
            self._gate,
            session_id,
            CONTROL_INPUT_CAPABILITY_ID,
        ) as access:
            acknowledgement = await access.resources.invoke_owned(
                access.ports.input.pointer(command)
            )
            return verified_feature_result(
                CONTROL_INPUT_CAPABILITY_ID,
                lambda: InputAcknowledgementValue.from_core(
                    acknowledgement,
                    command=command,
                ),
            )

    async def text(
        self,
        session_id: HermesSessionId,
        request: TextInputParams,
    ) -> InputAcknowledgementValue:
        """Commit one bounded Unicode text event to the focused game surface."""
        command = request.to_core()
        async with control_access(
            self._registry,
            self._gate,
            session_id,
            CONTROL_INPUT_CAPABILITY_ID,
        ) as access:
            acknowledgement = await access.resources.invoke_owned(access.ports.input.text(command))
            return verified_feature_result(
                CONTROL_INPUT_CAPABILITY_ID,
                lambda: InputAcknowledgementValue.from_core(
                    acknowledgement,
                    command=command,
                ),
            )

    async def gamepad(
        self,
        session_id: HermesSessionId,
        request: GamepadInputParams,
    ) -> InputAcknowledgementValue:
        """Apply one complete standard-layout gamepad batch."""
        command = request.to_core()
        async with control_access(
            self._registry,
            self._gate,
            session_id,
            CONTROL_INPUT_CAPABILITY_ID,
        ) as access:
            acknowledgement = await access.resources.invoke_owned(
                access.ports.input.gamepad(command)
            )
            return verified_feature_result(
                CONTROL_INPUT_CAPABILITY_ID,
                lambda: InputAcknowledgementValue.from_core(
                    acknowledgement,
                    command=command,
                ),
            )
