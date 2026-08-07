"""Hermes tool validation, serialization, ownership, and failure tests."""

from __future__ import annotations

import asyncio
import json

import pytest
from toqraq.contracts.base import EmptyRequest
from toqraq.contracts.setup import SetupResult
from toqraq.hermes.tools import build_tools
from toqraq.services.container import build_container

_TRACE_ID = "8f489b96-c438-4d13-a54d-9e3f1020f531"


def _handler(name: str):
    """Return one handler bound to an isolated production graph."""
    return next(tool.handler for tool in build_tools(build_container()) if tool.name == name)


def test_tool_serializes_the_shared_setup_result() -> None:
    payload = json.loads(asyncio.run(_handler("toqraq_project_setup")({})))
    assert set(payload) == {"host", "engine", "project", "engine_choices", "action"}
    assert set(payload["host"]) == {"platform", "native_display"}
    assert payload["engine"] is None
    assert payload["project"] == {
        "path": None,
        "state": "missing",
        "viewport_size": None,
        "probed_engine_ids": [],
    }
    assert payload["engine_choices"] == []
    assert payload["action"] == "select_project"


def test_tool_validation_uses_shared_request_error_and_trace() -> None:
    payload = json.loads(
        asyncio.run(
            _handler("toqraq_project_setup")(
                {"engine": 42, "unexpected": "value"},
                trace_id=_TRACE_ID,
            )
        )
    )
    assert payload["error"] == {
        "code": "request.invalid",
        "category": "invalid",
        "parameters": {"issue_count": 2},
        "details": {
            "issues": [
                {"location": "engine", "type": "string_type"},
                {"location": "unexpected", "type": "extra_forbidden"},
            ],
            "truncated": False,
        },
        "trace_id": _TRACE_ID,
    }


def test_game_tool_requires_the_calling_hermes_owner() -> None:
    payload = json.loads(asyncio.run(_handler("toqraq_game_stop")({}, trace_id=_TRACE_ID)))
    assert payload["error"]["code"] == "request.invalid"
    assert payload["error"]["details"]["issues"] == [{"location": "task_id", "type": "missing"}]


def test_project_inventory_requires_owner_and_a_bound_project() -> None:
    handler = _handler("toqraq_project_read_inventory")

    missing_owner = json.loads(asyncio.run(handler({}, trace_id=_TRACE_ID)))
    unbound = json.loads(asyncio.run(handler({}, task_id="unbound-task", trace_id=_TRACE_ID)))

    assert missing_owner["error"]["code"] == "request.invalid"
    assert unbound["error"]["code"] == "project.not_bound"


def test_game_tool_rejects_an_invalid_host_owner() -> None:
    payload = json.loads(
        asyncio.run(
            _handler("toqraq_game_stop")(
                {},
                task_id="   ",
                trace_id=_TRACE_ID,
            )
        )
    )
    assert payload["error"]["code"] == "request.invalid"
    assert payload["error"]["details"]["issues"] == [
        {"location": "task_id", "type": "string_too_short"}
    ]


def test_tool_does_not_serialize_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    container = build_container()

    async def cancel(_service, _request):
        raise asyncio.CancelledError

    monkeypatch.setattr(type(container.setup_service), "check", cancel)
    handler = next(
        tool.handler for tool in build_tools(container) if tool.name == "toqraq_project_setup"
    )
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(handler({}))


def test_service_validation_failure_is_an_internal_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = build_container()

    async def invalid_result(_service, _request):
        return SetupResult.model_validate({})

    monkeypatch.setattr(type(container.setup_service), "check", invalid_result)
    handler = next(
        tool.handler for tool in build_tools(container) if tool.name == "toqraq_project_setup"
    )
    payload = json.loads(asyncio.run(handler({}, trace_id=_TRACE_ID)))

    assert payload["error"]["code"] == "internal.unexpected"
    assert payload["error"]["category"] == "internal"
    assert payload["error"]["trace_id"] == _TRACE_ID


def test_wrong_service_result_model_is_never_serialized_as_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = build_container()

    async def wrong_result(_service, _request):
        return EmptyRequest()

    monkeypatch.setattr(type(container.setup_service), "check", wrong_result)
    handler = next(
        tool.handler for tool in build_tools(container) if tool.name == "toqraq_project_setup"
    )

    payload = json.loads(asyncio.run(handler({}, trace_id=_TRACE_ID)))

    assert payload["error"]["code"] == "internal.unexpected"
    assert payload["error"]["category"] == "internal"
    assert payload["error"]["trace_id"] == _TRACE_ID
