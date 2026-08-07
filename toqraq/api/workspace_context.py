"""Hermes task workspace synchronization HTTP presenter."""

from __future__ import annotations

from fastapi.routing import APIRouter

from ..contracts.identifiers import HermesSessionId
from ..contracts.setup import SetupRequest, SetupResult
from ..services.container import Container
from .boundary import ToqraqRoute


def router_for(container: Container) -> APIRouter:
    """Build the task-owned workspace context route."""
    router = APIRouter(route_class=ToqraqRoute)

    @router.put("/workspace-context/{session_id}", response_model=SetupResult | None)
    async def update(
        session_id: HermesSessionId,
        body: SetupRequest,
    ) -> SetupResult | None:
        """Synchronize one active workspace without changing the project."""
        return await container.workspace_context_service.update(session_id, body)

    return router
