"""Focused live player-input HTTP presenters."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.routing import APIRouter

from ..contracts.bridge_input import (
    GamepadInputParams,
    InputAcknowledgementValue,
    KeyboardInputParams,
    PointerInputParams,
    SemanticInputParams,
    TextInputParams,
)
from ..contracts.identifiers import HermesSessionId
from .boundary import ToqraqRoute

if TYPE_CHECKING:
    from ..services.container import Container


def router_for(container: Container) -> APIRouter:
    """Bind each input family to its exact validated command boundary."""
    router = APIRouter(route_class=ToqraqRoute)

    @router.post(
        "/sessions/{session_id}/input/semantic",
        response_model=InputAcknowledgementValue,
    )
    async def semantic(
        session_id: HermesSessionId,
        body: SemanticInputParams,
    ) -> InputAcknowledgementValue:
        """Apply one validation-atomic project-action batch."""
        return await container.input_service.semantic(session_id, body)

    @router.post(
        "/sessions/{session_id}/input/keyboard",
        response_model=InputAcknowledgementValue,
    )
    async def keyboard(
        session_id: HermesSessionId,
        body: KeyboardInputParams,
    ) -> InputAcknowledgementValue:
        """Apply one validation-atomic W3C keyboard batch."""
        return await container.input_service.keyboard(session_id, body)

    @router.post(
        "/sessions/{session_id}/input/pointer",
        response_model=InputAcknowledgementValue,
    )
    async def pointer(
        session_id: HermesSessionId,
        body: PointerInputParams,
    ) -> InputAcknowledgementValue:
        """Apply one explicit-coordinate-space pointer batch."""
        return await container.input_service.pointer(session_id, body)

    @router.post(
        "/sessions/{session_id}/input/text",
        response_model=InputAcknowledgementValue,
    )
    async def text(
        session_id: HermesSessionId,
        body: TextInputParams,
    ) -> InputAcknowledgementValue:
        """Commit one bounded Unicode text event."""
        return await container.input_service.text(session_id, body)

    @router.post(
        "/sessions/{session_id}/input/gamepad",
        response_model=InputAcknowledgementValue,
    )
    async def gamepad(
        session_id: HermesSessionId,
        body: GamepadInputParams,
    ) -> InputAcknowledgementValue:
        """Apply one standard-layout gamepad batch."""
        return await container.input_service.gamepad(session_id, body)

    return router
