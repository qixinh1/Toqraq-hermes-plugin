"""Managed component inventory and asynchronous job HTTP presenter."""

from __future__ import annotations

from fastapi.routing import APIRouter

from ..contracts.components import (
    ComponentActiveJobsResult,
    ComponentJobResult,
    ComponentJobStartRequest,
    ComponentListResult,
)
from ..contracts.identifiers import ComponentOperationId
from ..services.container import Container
from .boundary import ToqraqRoute


def router_for(container: Container) -> APIRouter:
    """Build component routes over the process-owned job service."""
    router = APIRouter(route_class=ToqraqRoute)

    @router.get("/components", response_model=ComponentListResult)
    async def list_components() -> ComponentListResult:
        """List every certified release and its current managed readiness."""
        return await container.component_jobs.list_components()

    @router.post("/component-jobs", response_model=ComponentJobResult)
    async def start_job(body: ComponentJobStartRequest) -> ComponentJobResult:
        """Start or join one exact component mutation."""
        return await container.component_jobs.start_job(body.release_id, body.action)

    @router.get(
        "/component-jobs/active",
        response_model=ComponentActiveJobsResult,
    )
    async def list_active_jobs() -> ComponentActiveJobsResult:
        """Read bounded active job snapshots without changing their ownership."""
        return container.component_jobs.list_active_jobs()

    @router.get(
        "/component-jobs/{operation_id}",
        response_model=ComponentJobResult,
    )
    async def get_job(operation_id: ComponentOperationId) -> ComponentJobResult:
        """Read one retained authoritative job snapshot."""
        return container.component_jobs.get_job(operation_id)

    @router.post(
        "/component-jobs/{operation_id}/cancel",
        response_model=ComponentJobResult,
    )
    async def cancel_job(operation_id: ComponentOperationId) -> ComponentJobResult:
        """Request cooperative cancellation for one retained job."""
        return container.component_jobs.cancel_job(operation_id)

    return router
