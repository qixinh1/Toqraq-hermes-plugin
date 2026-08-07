"""REST-only presenter routing over focused service commands."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import APIRouter
from fastapi.routing import APIRoute
from toqraq.api import build_router
from toqraq.contracts.base import EmptyRequest
from toqraq.contracts.components import ComponentJobStartRequest
from toqraq.contracts.geometry import RectValue
from toqraq.contracts.preview import (
    NativePreviewAttachRequest,
    NativePreviewDetachRequest,
    NativePreviewPaneRequest,
    NativePreviewVisibleRequest,
)
from toqraq.contracts.setup import SetupRequest
from toqraq.services.container import Container

_SESSION_ID = "rest-owner"
_ATTACHMENT_ID = "pane-owner"
_OPERATION_ID = "8f489b96-c438-4d13-a54d-9e3f1020f531"
_RELEASE_ID = "f" * 64


class RecordingServices:
    """Implement each REST-only service method as one observable boundary."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def _record(self, name: str, *arguments: object) -> EmptyRequest:
        self.calls.append((name, arguments))
        return EmptyRequest()

    async def update(self, *arguments: object) -> EmptyRequest:
        return self._record("workspace.update", *arguments)

    def list(self) -> EmptyRequest:
        return self._record("sessions.list")

    def find(self, *arguments: object) -> EmptyRequest:
        return self._record("sessions.find", *arguments)

    async def attach(self, *arguments: object) -> EmptyRequest:
        return self._record("display.attach", *arguments)

    async def follow(self, *arguments: object) -> EmptyRequest:
        return self._record("display.follow", *arguments)

    async def set_visible(self, *arguments: object) -> EmptyRequest:
        return self._record("display.set_visible", *arguments)

    async def detach(self, *arguments: object) -> EmptyRequest:
        return self._record("display.detach", *arguments)

    async def list_components(self) -> EmptyRequest:
        return self._record("components.list")

    async def start_job(self, *arguments: object) -> EmptyRequest:
        return self._record("components.start", *arguments)

    def list_active_jobs(self) -> EmptyRequest:
        return self._record("components.active")

    def get_job(self, *arguments: object) -> EmptyRequest:
        return self._record("components.get", *arguments)

    def cancel_job(self, *arguments: object) -> EmptyRequest:
        return self._record("components.cancel", *arguments)


class RecordingContainer:
    """Expose one recorder through every REST-only service attribute."""

    def __init__(self, services: RecordingServices) -> None:
        self.workspace_context_service = services
        self.session_service = services
        self.display_service = services
        self.component_jobs = services


def _endpoints(container: RecordingContainer) -> dict[tuple[str, str], Callable[..., object]]:
    """Flatten mounted REST endpoints while excluding the event WebSocket."""
    endpoints: dict[tuple[str, str], Callable[..., object]] = {}

    def collect(router: APIRouter) -> None:
        for route in router.routes:
            if isinstance(route, APIRoute):
                endpoints[(next(iter(route.methods)), route.path)] = route.endpoint
                continue
            nested = getattr(route, "original_router", None)
            if isinstance(nested, APIRouter):
                collect(nested)

    collect(build_router(cast(Container, container)))
    return endpoints


async def _invoke(
    endpoints: dict[tuple[str, str], Callable[..., object]],
    method: str,
    path: str,
    **arguments: object,
) -> None:
    """Call one asynchronous raw endpoint with already validated values."""
    pending = cast(Awaitable[object], endpoints[(method, path)](**arguments))
    assert await pending == EmptyRequest()


def test_every_rest_only_operation_routes_to_its_focused_service() -> None:
    async def scenario() -> RecordingServices:
        services = RecordingServices()
        endpoints = _endpoints(RecordingContainer(services))
        setup = SetupRequest(project_dir="D:/game")
        rect = RectValue(x=10, y=20, width=640, height=360)
        await _invoke(
            endpoints,
            "PUT",
            "/workspace-context/{session_id}",
            session_id=_SESSION_ID,
            body=setup,
        )
        await _invoke(endpoints, "GET", "/sessions")
        await _invoke(
            endpoints,
            "GET",
            "/sessions/{session_id}",
            session_id=_SESSION_ID,
        )
        await _invoke(
            endpoints,
            "POST",
            "/preview/native/attach",
            body=NativePreviewAttachRequest(
                session_id=_SESSION_ID,
                attachment_id=_ATTACHMENT_ID,
                pane_rect=rect,
            ),
        )
        await _invoke(
            endpoints,
            "POST",
            "/preview/native/rect",
            body=NativePreviewPaneRequest(
                session_id=_SESSION_ID,
                attachment_id=_ATTACHMENT_ID,
                pane_rect=rect,
            ),
        )
        await _invoke(
            endpoints,
            "POST",
            "/preview/native/visible",
            body=NativePreviewVisibleRequest(
                session_id=_SESSION_ID,
                attachment_id=_ATTACHMENT_ID,
                visible=False,
            ),
        )
        await _invoke(
            endpoints,
            "POST",
            "/preview/native/detach",
            body=NativePreviewDetachRequest(
                session_id=_SESSION_ID,
                attachment_id=_ATTACHMENT_ID,
            ),
        )
        await _invoke(endpoints, "GET", "/components")
        await _invoke(
            endpoints,
            "POST",
            "/component-jobs",
            body=ComponentJobStartRequest(release_id=_RELEASE_ID, action="prepare"),
        )
        await _invoke(endpoints, "GET", "/component-jobs/active")
        await _invoke(
            endpoints,
            "GET",
            "/component-jobs/{operation_id}",
            operation_id=_OPERATION_ID,
        )
        await _invoke(
            endpoints,
            "POST",
            "/component-jobs/{operation_id}/cancel",
            operation_id=_OPERATION_ID,
        )
        return services

    services = asyncio.run(scenario())
    assert services.calls == [
        ("workspace.update", (_SESSION_ID, SetupRequest(project_dir="D:/game"))),
        ("sessions.list", ()),
        ("sessions.find", (_SESSION_ID,)),
        (
            "display.attach",
            (_SESSION_ID, _ATTACHMENT_ID, RectValue(x=10, y=20, width=640, height=360).to_core()),
        ),
        (
            "display.follow",
            (_SESSION_ID, _ATTACHMENT_ID, RectValue(x=10, y=20, width=640, height=360).to_core()),
        ),
        ("display.set_visible", (_SESSION_ID, _ATTACHMENT_ID, False)),
        ("display.detach", (_SESSION_ID, _ATTACHMENT_ID)),
        ("components.list", ()),
        (
            "components.start",
            (
                _RELEASE_ID,
                ComponentJobStartRequest(release_id=_RELEASE_ID, action="prepare").action,
            ),
        ),
        ("components.active", ()),
        ("components.get", (_OPERATION_ID,)),
        ("components.cancel", (_OPERATION_ID,)),
    ]
