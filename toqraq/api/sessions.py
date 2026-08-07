"""Session lifecycle HTTP presenter."""

from __future__ import annotations

from fastapi.routing import APIRouter

from ..contracts.identifiers import HermesSessionId
from ..contracts.sessions import (
    OwnedGameStartRequest,
    SessionListResult,
    SessionResult,
    SessionStopRequest,
    SetPausedRequest,
    StepFramesRequest,
)
from ..core.bridge import BridgeOwnerKey
from ..services.container import Container
from .boundary import ToqraqRoute


def router_for(container: Container) -> APIRouter:
    """Build session routes bound to one service graph."""
    router = APIRouter(route_class=ToqraqRoute)

    @router.post("/sessions", response_model=SessionResult)
    async def start(body: OwnedGameStartRequest) -> SessionResult:
        """Start the game owned by a Hermes session."""
        return await container.session_service.start(body.hermes_session, body.to_command())

    @router.get("/sessions", response_model=SessionListResult)
    async def list_sessions() -> SessionListResult:
        """List all owned games."""
        return container.session_service.list()

    @router.get("/sessions/{session_id}", response_model=SessionResult | None)
    async def get_session(session_id: HermesSessionId) -> SessionResult | None:
        """Get the game owned by one Hermes session, if present."""
        return container.session_service.find(session_id)

    @router.post("/sessions/{session_id}/pause", response_model=SessionResult)
    async def pause(
        session_id: HermesSessionId,
        body: SetPausedRequest,
    ) -> SessionResult:
        """Suspend or resume a game."""
        return await container.simulation_service.set_paused(session_id, body)

    @router.post("/sessions/{session_id}/step", response_model=SessionResult)
    async def step(
        session_id: HermesSessionId,
        body: StepFramesRequest,
    ) -> SessionResult:
        """Advance an exact frame count while the game remains paused."""
        return await container.simulation_service.step(session_id, body)

    @router.delete("/sessions/{session_id}", response_model=SessionResult)
    async def stop(
        session_id: HermesSessionId,
        body: SessionStopRequest,
    ) -> SessionResult:
        """Stop only the exact game run observed by Desktop."""
        return await container.session_service.stop(
            session_id,
            expected_owner=BridgeOwnerKey(
                session_id=session_id,
                run_revision=body.run_revision,
            ),
        )

    return router
