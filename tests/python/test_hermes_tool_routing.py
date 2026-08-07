"""One-to-one Hermes tool routing over caller-owned service commands."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import cast

from fastapi import APIRouter
from fastapi.routing import APIRoute
from pydantic import BaseModel
from toqraq.api import build_router
from toqraq.contracts.base import ContractModel, EmptyRequest
from toqraq.contracts.bridge_diagnostics import DiagnosticsReadParams, DiagnosticsReadResult
from toqraq.contracts.bridge_frame import FrameCaptureParams
from toqraq.contracts.bridge_hierarchy import HierarchyReadParams, HierarchyReadResult
from toqraq.contracts.bridge_input import (
    GamepadInputParams,
    InputAcknowledgementValue,
    KeyboardInputParams,
    PointerInputParams,
    SemanticInputParams,
    TextInputParams,
)
from toqraq.contracts.bridge_metrics import MetricsReadParams, MetricsReadResult
from toqraq.contracts.bridge_objects import ObjectReadParams, ObjectReadResult
from toqraq.contracts.frame_capture import FrameCaptureResult
from toqraq.contracts.process_output import ProcessOutputResult
from toqraq.contracts.project_inventory import (
    ProjectInventoryRequest,
    ProjectInventoryResult,
)
from toqraq.contracts.sessions import (
    GameStartRequest,
    OwnedGameStartRequest,
    SessionResult,
    SessionStopRequest,
    SetPausedRequest,
    StepFramesRequest,
)
from toqraq.contracts.setup import SetupRequest, SetupResult
from toqraq.core.bridge import BridgeOwnerKey
from toqraq.hermes.tools import build_tools
from toqraq.services.container import Container

from _bridge_feature_values import (
    diagnostics_values,
    frame_values,
    hierarchy_values,
    input_commands,
    metrics_values,
    object_values,
)

OWNER_ID = "hermes-tool-owner"


@dataclass
class RecordingService:
    """Record the focused method, host owner, and decoded contract."""

    result_model: type[BaseModel]
    calls: list[tuple[str, str | None, object | None]] = field(default_factory=list)

    async def check(self, request: ContractModel) -> BaseModel:
        return self._record("check", None, request)

    async def start(self, owner: str, request: ContractModel) -> BaseModel:
        return self._record("start", owner, request)

    async def stop(
        self,
        owner: str,
        *,
        expected_owner: BridgeOwnerKey | None = None,
    ) -> BaseModel:
        return self._record("stop", owner, expected_owner)

    async def set_paused(self, owner: str, request: ContractModel) -> BaseModel:
        return self._record("set_paused", owner, request)

    async def step(self, owner: str, request: ContractModel) -> BaseModel:
        return self._record("step", owner, request)

    async def read(
        self,
        owner: str,
        request: ContractModel | None = None,
    ) -> BaseModel:
        return self._record("read", owner, request)

    async def capture(self, owner: str, request: ContractModel) -> BaseModel:
        return self._record("capture", owner, request)

    async def semantic(self, owner: str, request: ContractModel) -> BaseModel:
        return self._record("semantic", owner, request)

    async def keyboard(self, owner: str, request: ContractModel) -> BaseModel:
        return self._record("keyboard", owner, request)

    async def pointer(self, owner: str, request: ContractModel) -> BaseModel:
        return self._record("pointer", owner, request)

    async def text(self, owner: str, request: ContractModel) -> BaseModel:
        return self._record("text", owner, request)

    async def gamepad(self, owner: str, request: ContractModel) -> BaseModel:
        return self._record("gamepad", owner, request)

    def _record(
        self,
        method: str,
        owner: str | None,
        request: object | None,
    ) -> BaseModel:
        self.calls.append((method, owner, request))
        return self.result_model.model_construct()


class RecordingContainer:
    """Expose one independent recorder for every application service boundary."""

    def __init__(self) -> None:
        self.setup_service = RecordingService(SetupResult)
        self.project_inventory_service = RecordingService(ProjectInventoryResult)
        self.session_service = RecordingService(SessionResult)
        self.simulation_service = RecordingService(SessionResult)
        self.hierarchy_service = RecordingService(HierarchyReadResult)
        self.object_inspection_service = RecordingService(ObjectReadResult)
        self.diagnostics_service = RecordingService(DiagnosticsReadResult)
        self.process_output_service = RecordingService(ProcessOutputResult)
        self.metrics_service = RecordingService(MetricsReadResult)
        self.frame_capture_service = RecordingService(FrameCaptureResult)
        self.input_service = RecordingService(InputAcknowledgementValue)


def _invoke(
    container: RecordingContainer,
    name: str,
    request: ContractModel,
    *,
    owner: bool = True,
) -> None:
    """Run one generated-schema handler and require its recording result."""
    handler = next(
        tool.handler for tool in build_tools(cast(Container, container)) if tool.name == name
    )
    kwargs = {"task_id": OWNER_ID} if owner else {}
    payload = request.model_dump(mode="json", by_alias=True)
    assert json.loads(asyncio.run(handler(payload, **kwargs))) == {}


def _route_endpoints(
    container: RecordingContainer,
) -> dict[tuple[str, str], Callable[..., Awaitable[object]]]:
    """Flatten the mounted API and retain each raw presenter endpoint."""
    endpoints: dict[tuple[str, str], Callable[..., Awaitable[object]]] = {}

    def collect(router: APIRouter) -> None:
        for route in router.routes:
            if isinstance(route, APIRoute):
                method = next(iter(route.methods))
                endpoints[(method, route.path)] = cast(
                    Callable[..., Awaitable[object]], route.endpoint
                )
                continue
            nested = getattr(route, "original_router", None)
            if isinstance(nested, APIRouter):
                collect(nested)

    collect(build_router(cast(Container, container)))
    return endpoints


def _invoke_route(
    container: RecordingContainer,
    method: str,
    path: str,
    **arguments: object,
) -> None:
    """Call one raw presenter after FastAPI-equivalent contract construction."""
    endpoint = _route_endpoints(container)[(method, path)]
    assert isinstance(asyncio.run(endpoint(**arguments)), BaseModel)


def test_setup_and_lifecycle_tools_route_to_focused_services() -> None:
    container = RecordingContainer()
    _invoke(container, "toqraq_project_setup", SetupRequest(), owner=False)
    _invoke(container, "toqraq_game_start", GameStartRequest(project_dir="D:/game"))
    _invoke(container, "toqraq_game_stop", EmptyRequest())
    _invoke(container, "toqraq_game_pause", EmptyRequest())
    _invoke(container, "toqraq_game_resume", EmptyRequest())
    _invoke(container, "toqraq_game_step", StepFramesRequest(frame_count=2))

    assert container.setup_service.calls == [("check", None, SetupRequest())]
    assert container.session_service.calls == [
        ("start", OWNER_ID, GameStartRequest(project_dir="D:/game")),
        ("stop", OWNER_ID, None),
    ]
    assert container.simulation_service.calls == [
        ("set_paused", OWNER_ID, SetPausedRequest(paused=True)),
        ("set_paused", OWNER_ID, SetPausedRequest(paused=False)),
        ("step", OWNER_ID, StepFramesRequest(frame_count=2)),
    ]


def test_project_inventory_tool_routes_only_to_the_owner_bound_service() -> None:
    container = RecordingContainer()
    request = ProjectInventoryRequest(scope="scenes", limit=1)

    _invoke(container, "toqraq_project_read_inventory", request)

    assert container.project_inventory_service.calls == [("read", OWNER_ID, request)]


def test_setup_and_lifecycle_http_route_to_the_same_service_commands() -> None:
    container = RecordingContainer()
    _invoke_route(container, "POST", "/setup", body=SetupRequest())
    _invoke_route(
        container,
        "POST",
        "/sessions",
        body=OwnedGameStartRequest(
            hermes_session=OWNER_ID,
            project_dir="D:/game",
        ),
    )
    _invoke_route(
        container,
        "DELETE",
        "/sessions/{session_id}",
        session_id=OWNER_ID,
        body=SessionStopRequest(run_revision=7),
    )
    _invoke_route(
        container,
        "POST",
        "/sessions/{session_id}/pause",
        session_id=OWNER_ID,
        body=SetPausedRequest(paused=True),
    )
    _invoke_route(
        container,
        "POST",
        "/sessions/{session_id}/pause",
        session_id=OWNER_ID,
        body=SetPausedRequest(paused=False),
    )
    _invoke_route(
        container,
        "POST",
        "/sessions/{session_id}/step",
        session_id=OWNER_ID,
        body=StepFramesRequest(frame_count=2),
    )

    assert container.setup_service.calls == [("check", None, SetupRequest())]
    start_call, stop_call = container.session_service.calls
    assert start_call == ("start", OWNER_ID, GameStartRequest(project_dir="D:/game"))
    assert type(start_call[2]) is GameStartRequest
    assert stop_call == (
        "stop",
        OWNER_ID,
        BridgeOwnerKey(session_id=OWNER_ID, run_revision=7),
    )
    assert container.simulation_service.calls == [
        ("set_paused", OWNER_ID, SetPausedRequest(paused=True)),
        ("set_paused", OWNER_ID, SetPausedRequest(paused=False)),
        ("step", OWNER_ID, StepFramesRequest(frame_count=2)),
    ]


def test_perception_tools_decode_and_route_independently() -> None:
    container = RecordingContainer()
    hierarchy = HierarchyReadParams.from_core(hierarchy_values()[0])
    objects = ObjectReadParams.from_core(object_values()[0])
    diagnostics = DiagnosticsReadParams.from_core(diagnostics_values()[0])
    metrics = MetricsReadParams.from_core(metrics_values()[0])
    frame = FrameCaptureParams.from_core(frame_values()[0])

    _invoke(container, "toqraq_game_read_hierarchy", hierarchy)
    _invoke(container, "toqraq_game_read_objects", objects)
    _invoke(container, "toqraq_game_read_diagnostics", diagnostics)
    _invoke(container, "toqraq_game_read_process_output", EmptyRequest())
    _invoke(container, "toqraq_game_read_metrics", metrics)
    _invoke(container, "toqraq_game_capture_frame", frame)

    assert container.hierarchy_service.calls == [("read", OWNER_ID, hierarchy)]
    assert container.object_inspection_service.calls == [("read", OWNER_ID, objects)]
    assert container.diagnostics_service.calls == [("read", OWNER_ID, diagnostics)]
    assert container.process_output_service.calls == [("read", OWNER_ID, None)]
    assert container.metrics_service.calls == [("read", OWNER_ID, metrics)]
    assert container.frame_capture_service.calls == [("capture", OWNER_ID, frame)]


def test_perception_http_routes_to_the_same_focused_service_commands() -> None:
    container = RecordingContainer()
    hierarchy = HierarchyReadParams.from_core(hierarchy_values()[0])
    objects = ObjectReadParams.from_core(object_values()[0])
    diagnostics = DiagnosticsReadParams.from_core(diagnostics_values()[0])
    metrics = MetricsReadParams.from_core(metrics_values()[0])
    frame = FrameCaptureParams.from_core(frame_values()[0])
    requests = (
        ("POST", "/sessions/{session_id}/hierarchy", "body", hierarchy),
        ("POST", "/sessions/{session_id}/objects", "body", objects),
        ("POST", "/sessions/{session_id}/diagnostics", "body", diagnostics),
        ("GET", "/sessions/{session_id}/process-output", "", None),
        ("POST", "/sessions/{session_id}/metrics", "body", metrics),
        ("POST", "/sessions/{session_id}/frame", "body", frame),
    )
    for method, path, body_name, body in requests:
        arguments: dict[str, object] = {"session_id": OWNER_ID}
        if body_name:
            arguments[body_name] = body
        _invoke_route(container, method, path, **arguments)

    assert container.hierarchy_service.calls == [("read", OWNER_ID, hierarchy)]
    assert container.object_inspection_service.calls == [("read", OWNER_ID, objects)]
    assert container.diagnostics_service.calls == [("read", OWNER_ID, diagnostics)]
    assert container.process_output_service.calls == [("read", OWNER_ID, None)]
    assert container.metrics_service.calls == [("read", OWNER_ID, metrics)]
    assert container.frame_capture_service.calls == [("capture", OWNER_ID, frame)]


def test_input_tools_preserve_all_five_typed_surfaces() -> None:
    container = RecordingContainer()
    semantic, keyboard, pointer, text, gamepad = input_commands()
    requests = (
        ("toqraq_game_input_semantic", SemanticInputParams.from_core(semantic)),
        ("toqraq_game_input_keyboard", KeyboardInputParams.from_core(keyboard)),
        ("toqraq_game_input_pointer", PointerInputParams.from_core(pointer)),
        ("toqraq_game_input_text", TextInputParams.from_core(text)),
        ("toqraq_game_input_gamepad", GamepadInputParams.from_core(gamepad)),
    )
    for name, request in requests:
        _invoke(container, name, request)

    assert container.input_service.calls == [
        ("semantic", OWNER_ID, requests[0][1]),
        ("keyboard", OWNER_ID, requests[1][1]),
        ("pointer", OWNER_ID, requests[2][1]),
        ("text", OWNER_ID, requests[3][1]),
        ("gamepad", OWNER_ID, requests[4][1]),
    ]


def test_input_http_routes_to_the_same_focused_service_commands() -> None:
    container = RecordingContainer()
    semantic, keyboard, pointer, text, gamepad = input_commands()
    requests = (
        ("semantic", SemanticInputParams.from_core(semantic)),
        ("keyboard", KeyboardInputParams.from_core(keyboard)),
        ("pointer", PointerInputParams.from_core(pointer)),
        ("text", TextInputParams.from_core(text)),
        ("gamepad", GamepadInputParams.from_core(gamepad)),
    )
    for family, request in requests:
        _invoke_route(
            container,
            "POST",
            f"/sessions/{{session_id}}/input/{family}",
            session_id=OWNER_ID,
            body=request,
        )

    assert container.input_service.calls == [
        ("semantic", OWNER_ID, requests[0][1]),
        ("keyboard", OWNER_ID, requests[1][1]),
        ("pointer", OWNER_ID, requests[2][1]),
        ("text", OWNER_ID, requests[3][1]),
        ("gamepad", OWNER_ID, requests[4][1]),
    ]
