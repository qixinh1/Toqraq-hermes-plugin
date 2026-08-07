"""Focused live-game perception HTTP presenters."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.routing import APIRouter

from ..contracts.bridge_diagnostics import DiagnosticsReadParams, DiagnosticsReadResult
from ..contracts.bridge_frame import FrameCaptureParams
from ..contracts.bridge_hierarchy import HierarchyReadParams, HierarchyReadResult
from ..contracts.bridge_metrics import MetricsReadParams, MetricsReadResult
from ..contracts.bridge_objects import ObjectReadParams, ObjectReadResult
from ..contracts.frame_capture import FrameCaptureResult
from ..contracts.identifiers import HermesSessionId
from ..contracts.process_output import ProcessOutputResult
from .boundary import ToqraqRoute

if TYPE_CHECKING:
    from ..services.container import Container


def router_for(container: Container) -> APIRouter:
    """Bind live-game observations to their focused services."""
    router = APIRouter(route_class=ToqraqRoute)

    @router.get(
        "/sessions/{session_id}/process-output",
        response_model=ProcessOutputResult,
    )
    async def process_output(session_id: HermesSessionId) -> ProcessOutputResult:
        """Read the latest bounded stdout/stderr tail from the owned process."""
        return await container.process_output_service.read(session_id)

    @router.post(
        "/sessions/{session_id}/hierarchy",
        response_model=HierarchyReadResult,
    )
    async def hierarchy(
        session_id: HermesSessionId,
        body: HierarchyReadParams,
    ) -> HierarchyReadResult:
        """Read one revision-consistent flat hierarchy page."""
        return await container.hierarchy_service.read(session_id, body)

    @router.post(
        "/sessions/{session_id}/objects",
        response_model=ObjectReadResult,
    )
    async def objects(
        session_id: HermesSessionId,
        body: ObjectReadParams,
    ) -> ObjectReadResult:
        """Read selected field groups for exact runtime object references."""
        return await container.object_inspection_service.read(session_id, body)

    @router.post(
        "/sessions/{session_id}/diagnostics",
        response_model=DiagnosticsReadResult,
    )
    async def diagnostics(
        session_id: HermesSessionId,
        body: DiagnosticsReadParams,
    ) -> DiagnosticsReadResult:
        """Read one bounded page from the native diagnostic stream."""
        return await container.diagnostics_service.read(session_id, body)

    @router.post(
        "/sessions/{session_id}/metrics",
        response_model=MetricsReadResult,
    )
    async def metrics(
        session_id: HermesSessionId,
        body: MetricsReadParams,
    ) -> MetricsReadResult:
        """Read explicitly selected runtime performance metrics."""
        return await container.metrics_service.read(session_id, body)

    @router.post(
        "/sessions/{session_id}/frame",
        response_model=FrameCaptureResult,
    )
    async def frame(
        session_id: HermesSessionId,
        body: FrameCaptureParams,
    ) -> FrameCaptureResult:
        """Capture one completely verified bounded PNG frame."""
        return await container.frame_capture_service.capture(session_id, body)

    return router
