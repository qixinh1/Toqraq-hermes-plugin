"""HTTP boundary contract tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from toqraq.api import build_router
from toqraq.api.boundary import status_for
from toqraq.contracts.base import EmptyRequest
from toqraq.core.errors import ErrorCategory
from toqraq.hermes.tools import build_tools
from toqraq.services.container import build_container


def request(
    method: str,
    path: str,
    payload: Any = None,
    *,
    container: Any = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Send one request to an isolated in-process API application."""
    app = FastAPI()
    app.include_router(build_router(container or build_container()))

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=payload, headers=headers)

    return asyncio.run(send())


def _http_operations(router: APIRouter) -> list[APIRoute]:
    """Flatten every included REST operation from the plugin router."""
    result: list[APIRoute] = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            result.append(route)
            continue
        nested = getattr(route, "original_router", None)
        if isinstance(nested, APIRouter):
            result.extend(_http_operations(nested))
    return result


class TestErrors:
    """Domain and request errors keep distinct HTTP semantics."""

    def test_missing_session_mutation_is_structured_404(self) -> None:
        response = request("POST", "/sessions/missing/pause", {"paused": True})
        assert response.status_code == 404
        error = response.json()["error"]
        assert error == {
            "code": "session.not_found",
            "category": "not_found",
            "parameters": {"session_id": "missing"},
            "details": {"reason": "not_owned"},
            "trace_id": error["trace_id"],
        }
        assert str(UUID(error["trace_id"])) == error["trace_id"]

    def test_recognized_project_without_admitted_runtime_is_structured_424(self) -> None:
        project = (Path(__file__).parents[1] / "fixtures" / "godot_project").resolve()
        response = request(
            "POST",
            "/sessions",
            {"hermes_session": "missing", "project_dir": str(project)},
        )
        assert response.status_code == 424
        assert response.json()["error"]["code"] == "engine.unavailable"

    def test_unknown_component_release_is_structured_404(self) -> None:
        response = request(
            "POST",
            "/component-jobs",
            {"release_id": "f" * 64, "action": "prepare"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "component.release_not_found"

    def test_component_operation_path_requires_canonical_uuid4(self) -> None:
        response = request("GET", "/component-jobs/not-an-operation")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "request.invalid"

    def test_unknown_component_operation_is_structured_404(self) -> None:
        operation_id = "8f489b96-c438-4d13-a54d-9e3f1020f531"
        response = request("POST", f"/component-jobs/{operation_id}/cancel")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "component.job_not_found"

    def test_invalid_rect_uses_shared_request_error(self) -> None:
        response = request(
            "POST",
            "/preview/native/rect",
            {
                "session_id": "missing",
                "attachment_id": "pane-1",
                "pane_rect": {"x": 0, "y": 0, "width": 0, "height": 10},
            },
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "request.invalid"

    def test_attach_accepts_one_physical_pane_rectangle(self) -> None:
        response = request(
            "POST",
            "/preview/native/attach",
            {
                "session_id": "missing",
                "attachment_id": "pane-1",
                "pane_rect": {"x": 10, "y": 10, "width": 100, "height": 50},
            },
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "session.not_found"

    def test_attach_rejects_client_fitted_geometry_and_host_point(self) -> None:
        response = request(
            "POST",
            "/preview/native/attach",
            {
                "session_id": "missing",
                "attachment_id": "pane-1",
                "host_point": {"x": 20, "y": 30},
                "rect": {"x": 10, "y": 10, "width": 100, "height": 50},
            },
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "request.invalid"

    def test_unknown_request_fields_are_rejected(self) -> None:
        response = request(
            "POST",
            "/preview/native/visible",
            {
                "session_id": "missing",
                "attachment_id": "pane-1",
                "visible": True,
                "native_window": 123,
            },
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "request.invalid"

    def test_start_requires_hermes_owner(self) -> None:
        response = request("POST", "/sessions", {"project_dir": "D:/demo"})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "request.invalid"

    def test_stop_requires_one_positive_observed_run_revision(self) -> None:
        for payload in (None, {}, {"run_revision": 0}, {"run_revision": True}):
            response = request("DELETE", "/sessions/missing", payload)
            assert response.status_code == 400
            assert response.json()["error"]["code"] == "request.invalid"

        missing = request("DELETE", "/sessions/missing", {"run_revision": 1})
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "session.not_found"

    def test_setup_rejects_unknown_fields(self) -> None:
        response = request("POST", "/setup", {"project": "D:/demo"})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "request.invalid"

    def test_workspace_context_rejects_an_invalid_task_owner(self) -> None:
        response = request(
            "PUT",
            "/workspace-context/task%0Aother",
            {"project_dir": "D:/demo"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "request.invalid"


class TestReads:
    """Authoritative session reads remain ordinary JSON."""

    def test_missing_owned_game_is_null(self) -> None:
        response = request("GET", "/sessions/missing")
        assert response.status_code == 200
        assert response.json() is None

    def test_workspace_context_binds_ready_setup_and_missing_path_clears_it(
        self,
    ) -> None:
        container = build_container()
        project = (Path(__file__).parents[1] / "fixtures" / "godot_project").resolve()

        bound = request(
            "PUT",
            "/workspace-context/task-1",
            {"project_dir": str(project)},
            container=container,
        )

        assert bound.status_code == 200
        assert bound.json()["action"] == "runtime_unavailable"
        snapshot = container.workspace_context_service.find("task-1")
        assert snapshot is not None
        assert snapshot.project_path == str(project)
        assert snapshot.engine_id == "godot"

        cleared = request(
            "PUT",
            "/workspace-context/task-1",
            {},
            container=container,
        )
        assert cleared.status_code == 200
        assert cleared.json() is None
        assert container.workspace_context_service.find("task-1") is None

    def test_empty_session_list(self) -> None:
        response = request("GET", "/sessions")
        assert response.status_code == 200
        assert response.json() == []

    def test_missing_process_output_owner_is_structured_404(self) -> None:
        response = request("GET", "/sessions/missing/process-output")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "session.not_found"

    def test_component_catalog_is_an_authoritative_bounded_result(self) -> None:
        response = request("GET", "/components")
        assert response.status_code == 200
        assert response.json() == {"releases": []}

    def test_active_component_jobs_use_the_static_bounded_route(self) -> None:
        response = request("GET", "/component-jobs/active")
        assert response.status_code == 200
        assert response.json() == {"jobs": []}

    def test_setup_requires_the_active_workspace_before_format_recognition(self) -> None:
        response = request("POST", "/setup", {})
        assert response.status_code == 200
        payload = response.json()
        assert payload["project"] == {
            "path": None,
            "state": "missing",
            "viewport_size": None,
            "probed_engine_ids": [],
        }
        assert payload["engine"] is None
        assert payload["engine_choices"] == []
        assert isinstance(payload["host"]["platform"], str)
        assert payload["action"] == "select_project"

    def test_setup_recognizes_godot_without_claiming_an_admitted_runtime(self) -> None:
        project = (Path(__file__).parents[1] / "fixtures" / "godot_project").resolve()
        response = request(
            "POST",
            "/setup",
            {"project_dir": str(project), "engine": "godot", "version": "4.7.1"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["project"] == {
            "path": str(project),
            "state": "ready",
            "viewport_size": {"width": 960, "height": 540},
            "probed_engine_ids": ["godot"],
        }
        assert payload["engine"] == {
            "id": "godot",
            "runtime": None,
            "available_versions": [],
            "required_component_release_ids": [],
            "runtime_install_required": False,
        }
        assert payload["action"] == "runtime_unavailable"


def test_category_status_mapping_is_complete() -> None:
    assert {category: status_for(category) for category in ErrorCategory} == {
        ErrorCategory.INVALID: 400,
        ErrorCategory.UNAUTHENTICATED: 401,
        ErrorCategory.FORBIDDEN: 403,
        ErrorCategory.NOT_FOUND: 404,
        ErrorCategory.CONFLICT: 409,
        ErrorCategory.UNAVAILABLE: 424,
        ErrorCategory.TIMEOUT: 504,
        ErrorCategory.UPSTREAM: 502,
        ErrorCategory.INTERNAL: 500,
    }


def test_http_and_tool_share_success_and_validation_contracts() -> None:
    container = build_container()
    tools = {tool.name: tool.handler for tool in build_tools(container)}

    response = request("POST", "/setup", {}, container=container)
    tool_success = json.loads(asyncio.run(tools["toqraq_project_setup"]({})))
    assert response.status_code == 200
    assert response.json() == tool_success

    trace_id = "8f489b96-c438-4d13-a54d-9e3f1020f531"
    invalid = {"engine": 42}
    response = request(
        "POST",
        "/setup",
        invalid,
        container=container,
        headers={"x-trace-id": trace_id},
    )
    tool_failure = json.loads(
        asyncio.run(tools["toqraq_project_setup"](invalid, trace_id=trace_id))
    )
    assert response.status_code == 400
    assert response.json() == tool_failure
    asyncio.run(container.close())


def test_http_and_tool_reject_the_same_wrong_service_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = build_container()

    async def wrong_result(_service, _request):
        return EmptyRequest()

    monkeypatch.setattr(type(container.setup_service), "check", wrong_result)
    trace_id = "8f489b96-c438-4d13-a54d-9e3f1020f531"
    response = request(
        "POST",
        "/setup",
        {},
        container=container,
        headers={"x-trace-id": trace_id},
    )
    setup_tool = next(
        tool.handler for tool in build_tools(container) if tool.name == "toqraq_project_setup"
    )
    tool_payload = json.loads(asyncio.run(setup_tool({}, trace_id=trace_id)))

    assert response.status_code == 500
    assert response.json() == tool_payload
    assert response.json()["error"]["code"] == "internal.unexpected"


def test_every_http_operation_declares_its_contract_response_model() -> None:
    plugin_routes = _http_operations(build_router(build_container()))
    assert {(next(iter(route.methods)), route.path) for route in plugin_routes} == {
        ("POST", "/setup"),
        ("PUT", "/workspace-context/{session_id}"),
        ("GET", "/sessions"),
        ("POST", "/sessions"),
        ("GET", "/sessions/{session_id}"),
        ("DELETE", "/sessions/{session_id}"),
        ("POST", "/sessions/{session_id}/pause"),
        ("POST", "/sessions/{session_id}/step"),
        ("POST", "/preview/native/attach"),
        ("POST", "/preview/native/rect"),
        ("POST", "/preview/native/visible"),
        ("POST", "/preview/native/detach"),
        ("POST", "/sessions/{session_id}/hierarchy"),
        ("POST", "/sessions/{session_id}/objects"),
        ("POST", "/sessions/{session_id}/diagnostics"),
        ("GET", "/sessions/{session_id}/process-output"),
        ("POST", "/sessions/{session_id}/metrics"),
        ("POST", "/sessions/{session_id}/frame"),
        ("POST", "/sessions/{session_id}/input/semantic"),
        ("POST", "/sessions/{session_id}/input/keyboard"),
        ("POST", "/sessions/{session_id}/input/pointer"),
        ("POST", "/sessions/{session_id}/input/text"),
        ("POST", "/sessions/{session_id}/input/gamepad"),
        ("GET", "/components"),
        ("POST", "/component-jobs"),
        ("GET", "/component-jobs/active"),
        ("GET", "/component-jobs/{operation_id}"),
        ("POST", "/component-jobs/{operation_id}/cancel"),
    }
    assert all(route.response_model is not None for route in plugin_routes)


def test_http_mirrored_and_tool_only_surfaces_are_explicit() -> None:
    tool_routes = {
        "toqraq_project_setup": ("POST", "/setup"),
        "toqraq_game_start": ("POST", "/sessions"),
        "toqraq_game_stop": ("DELETE", "/sessions/{session_id}"),
        "toqraq_game_pause": ("POST", "/sessions/{session_id}/pause"),
        "toqraq_game_resume": ("POST", "/sessions/{session_id}/pause"),
        "toqraq_game_step": ("POST", "/sessions/{session_id}/step"),
        "toqraq_game_read_hierarchy": ("POST", "/sessions/{session_id}/hierarchy"),
        "toqraq_game_read_objects": ("POST", "/sessions/{session_id}/objects"),
        "toqraq_game_read_diagnostics": ("POST", "/sessions/{session_id}/diagnostics"),
        "toqraq_game_read_process_output": ("GET", "/sessions/{session_id}/process-output"),
        "toqraq_game_read_metrics": ("POST", "/sessions/{session_id}/metrics"),
        "toqraq_game_capture_frame": ("POST", "/sessions/{session_id}/frame"),
        "toqraq_game_input_semantic": ("POST", "/sessions/{session_id}/input/semantic"),
        "toqraq_game_input_keyboard": ("POST", "/sessions/{session_id}/input/keyboard"),
        "toqraq_game_input_pointer": ("POST", "/sessions/{session_id}/input/pointer"),
        "toqraq_game_input_text": ("POST", "/sessions/{session_id}/input/text"),
        "toqraq_game_input_gamepad": ("POST", "/sessions/{session_id}/input/gamepad"),
    }
    rest_only = {
        ("PUT", "/workspace-context/{session_id}"),
        ("GET", "/sessions"),
        ("GET", "/sessions/{session_id}"),
        ("POST", "/preview/native/attach"),
        ("POST", "/preview/native/rect"),
        ("POST", "/preview/native/visible"),
        ("POST", "/preview/native/detach"),
        ("GET", "/components"),
        ("POST", "/component-jobs"),
        ("GET", "/component-jobs/active"),
        ("GET", "/component-jobs/{operation_id}"),
        ("POST", "/component-jobs/{operation_id}/cancel"),
    }
    container = build_container()
    routes = {
        (next(iter(route.methods)), route.path): route
        for route in _http_operations(build_router(container))
    }
    tools = {tool.name: tool for tool in build_tools(container)}
    tool_only = {"toqraq_project_read_inventory"}

    assert set(tool_routes) | tool_only == set(tools)
    for tool_name, route_key in tool_routes.items():
        assert routes[route_key].response_model is tools[tool_name].result_model
    assert set(routes) - set(tool_routes.values()) == rest_only
