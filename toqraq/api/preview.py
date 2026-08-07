"""Native preview HTTP presenter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.routing import APIRouter

from ..contracts.preview import (
    NativePreviewAttachRequest,
    NativePreviewDetachRequest,
    NativePreviewPaneRequest,
    NativePreviewVisibleRequest,
    PreviewOperationResult,
)
from ..contracts.sessions import SessionResult
from .boundary import ToqraqRoute

if TYPE_CHECKING:
    from ..services.container import Container


def router_for(container: Container) -> APIRouter:
    """Bind native presentation requests to the shared display use case."""
    router = APIRouter(route_class=ToqraqRoute)

    @router.post("/preview/native/attach", response_model=SessionResult)
    async def attach(body: NativePreviewAttachRequest) -> SessionResult:
        """Attach the session-owned native surface to one Desktop pane."""
        return await container.display_service.attach(
            body.session_id,
            body.attachment_id,
            body.pane_rect.to_core(),
        )

    @router.post("/preview/native/rect", response_model=PreviewOperationResult)
    async def follow(body: NativePreviewPaneRequest) -> PreviewOperationResult:
        """Follow one physical pane using the session's authoritative viewport."""
        return await container.display_service.follow(
            body.session_id,
            body.attachment_id,
            body.pane_rect.to_core(),
        )

    @router.post("/preview/native/visible", response_model=PreviewOperationResult)
    async def visible(body: NativePreviewVisibleRequest) -> PreviewOperationResult:
        """Show or hide the exact renderer-owned native preview."""
        return await container.display_service.set_visible(
            body.session_id,
            body.attachment_id,
            body.visible,
        )

    @router.post("/preview/native/detach", response_model=PreviewOperationResult)
    async def detach(body: NativePreviewDetachRequest) -> PreviewOperationResult:
        """Restore the exact renderer-owned native preview."""
        return await container.display_service.detach(
            body.session_id,
            body.attachment_id,
        )

    return router
