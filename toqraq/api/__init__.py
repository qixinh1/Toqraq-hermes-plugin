"""FastAPI routers for the Toqraq backend namespace."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.routing import APIRouter

if TYPE_CHECKING:
    from ..services.container import Container


def build_router(container: Container) -> APIRouter:
    """Aggregate all resource routers under one namespace router.

    Args:
        container: The assembled service graph.

    Returns:
        Router mounting every Toqraq endpoint.
    """
    from . import (
        components,
        events,
        input,
        perception,
        preview,
        sessions,
        setup,
        workspace_context,
    )

    router = APIRouter()
    router.include_router(setup.router_for(container), tags=["setup"])
    router.include_router(workspace_context.router_for(container), tags=["setup"])
    router.include_router(sessions.router_for(container), tags=["sessions"])
    router.include_router(events.router_for(container), tags=["sessions"])
    router.include_router(preview.router_for(container), tags=["preview"])
    router.include_router(perception.router_for(container), tags=["perception"])
    router.include_router(input.router_for(container), tags=["input"])
    router.include_router(components.router_for(container), tags=["components"])
    return router
