"""First-run readiness HTTP presenter."""

from __future__ import annotations

from fastapi.routing import APIRouter

from ..contracts.setup import SetupRequest, SetupResult
from ..services.container import Container
from .boundary import ToqraqRoute


def router_for(container: Container) -> APIRouter:
    """Build setup routes bound to one service graph."""
    router = APIRouter(route_class=ToqraqRoute)

    @router.post("/setup", response_model=SetupResult)
    async def check(body: SetupRequest) -> SetupResult:
        """Inspect host, runtime, and project without changing them."""
        return await container.setup_service.check(body)

    return router
