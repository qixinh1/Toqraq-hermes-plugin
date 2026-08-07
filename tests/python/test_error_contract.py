"""Cross-boundary application error and trace contract tests."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from uuid import UUID, uuid1

import httpx
import pytest
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel, ConfigDict, ValidationError
from toqraq.api.boundary import ToqraqRoute
from toqraq.contracts.base import EmptyRequest
from toqraq.contracts.errors import ErrorEnvelope, error_envelope
from toqraq.contracts.setup import SetupResult
from toqraq.core.error_values import MAX_ERROR_SAFE_INTEGER, freeze_error_fields
from toqraq.core.errors import (
    APPLICATION_ERROR_TYPES,
    ErrorCategory,
    ProtocolError,
)
from toqraq.core.failure_diagnostics import failure_diagnostic
from toqraq.core.trace import TraceId, current_trace_id, select_trace_id, trace_scope
from toqraq.hermes import tools as plugin_tools

_TRACE_ID = "8f489b96-c438-4d13-a54d-9e3f1020f531"
_SECRET = "top-secret-token"
_UNSAFE_PATH = "C:/private/customer/source.gd"


def _request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    payload: object | None = None,
) -> httpx.Response:
    """Send one request to an in-process application."""

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, headers=headers, json=payload)

    return asyncio.run(send())


def _app_with_route(path: str, endpoint: Callable[..., object], *, method: str = "GET") -> FastAPI:
    """Build an application whose endpoint uses the Toqraq route boundary."""
    router = APIRouter(route_class=ToqraqRoute)
    router.add_api_route(path, endpoint, methods=[method])
    app = FastAPI()
    app.include_router(router)
    return app


def test_every_application_error_has_one_unique_stable_identity() -> None:
    error_codes = tuple(error_type.code for error_type in APPLICATION_ERROR_TYPES)
    assert len(error_codes) == len(set(error_codes))
    assert set(ErrorCategory) == {
        ErrorCategory.INVALID,
        ErrorCategory.UNAUTHENTICATED,
        ErrorCategory.FORBIDDEN,
        ErrorCategory.NOT_FOUND,
        ErrorCategory.CONFLICT,
        ErrorCategory.UNAVAILABLE,
        ErrorCategory.TIMEOUT,
        ErrorCategory.UPSTREAM,
        ErrorCategory.INTERNAL,
    }

    cause = RuntimeError(f"{_SECRET} {_UNSAFE_PATH}")
    trace_id = TraceId(_TRACE_ID)
    for error_type in APPLICATION_ERROR_TYPES:
        error = error_type(
            parameters={"operation": "test"},
            details={"retryable": False},
            cause=cause,
            trace_id=trace_id,
        )
        assert error.args == (error_type.code,)
        assert error.category is error_type.category
        assert error.cause is cause
        assert error.trace_id is trace_id
        public = error_envelope(error).model_dump(mode="json")
        assert set(public["error"]) == {
            "code",
            "category",
            "parameters",
            "details",
            "trace_id",
        }
        serialized = json.dumps(public)
        assert _SECRET not in serialized
        assert _UNSAFE_PATH not in serialized


def test_error_values_are_bounded_immutable_and_cross_language_safe() -> None:
    source = {"count": MAX_ERROR_SAFE_INTEGER, "nested": {"items": [1, True, None]}}
    frozen = freeze_error_fields(source)
    source["count"] = 0
    assert frozen["count"] == MAX_ERROR_SAFE_INTEGER
    with pytest.raises(TypeError):
        frozen["count"] = 1  # type: ignore[index]
    with pytest.raises(ValueError, match="cross-language safe range"):
        freeze_error_fields({"count": MAX_ERROR_SAFE_INTEGER + 1})
    with pytest.raises(ValueError, match="cross-language safe range"):
        freeze_error_fields({"count": -(MAX_ERROR_SAFE_INTEGER + 1)})
    with pytest.raises(ValueError, match="cross-language safe range"):
        freeze_error_fields({"count": float(MAX_ERROR_SAFE_INTEGER + 1)})
    with pytest.raises(ValueError, match="finite"):
        freeze_error_fields({"ratio": float("inf")})
    with pytest.raises(ValueError, match="too long"):
        freeze_error_fields({"value": "x" * 513})
    assert freeze_error_fields({"value": "🎮" * 512})["value"] == "🎮" * 512
    with pytest.raises(ValueError, match="too long"):
        freeze_error_fields({"value": "🎮" * 513})
    assert freeze_error_fields({"value": (((1,),),)})["value"] == (((1,),),)
    with pytest.raises(ValueError, match="nesting"):
        freeze_error_fields({"value": ((((1,),),),)})


def test_trace_id_requires_canonical_uuid4() -> None:
    trace_id = TraceId(_TRACE_ID)
    parsed = UUID(str(trace_id))
    assert parsed.version == 4
    assert parsed.variant == "specified in RFC 4122"

    for rejected in (
        str(uuid1()),
        "00000000-0000-0000-0000-000000000000",
        _TRACE_ID.upper(),
        "not-a-uuid",
    ):
        with pytest.raises(ValueError):
            TraceId(rejected)
        selected = select_trace_id(rejected)
        assert UUID(str(selected)).version == 4
        assert str(selected) != rejected


def test_nested_trace_scope_retains_and_restores_ownership() -> None:
    assert current_trace_id() is None
    with trace_scope(_TRACE_ID) as outer:
        assert current_trace_id() is outer
        with trace_scope() as nested:
            assert nested is outer
        with trace_scope("invalid") as replacement:
            assert replacement is not outer
            assert UUID(str(replacement)).version == 4
        assert current_trace_id() is outer
    assert current_trace_id() is None


def test_failure_diagnostic_never_invokes_foreign_string_hooks() -> None:
    class HostileText:
        calls = 0

        def __str__(self) -> str:
            self.calls += 1
            raise AssertionError("foreign string hook executed")

    class HostileError(RuntimeError):
        def __str__(self) -> str:
            raise AssertionError("exception string hook executed")

    hostile_module = HostileText()
    namespace: dict[str, object] = {
        "__name__": hostile_module,
        "HostileError": HostileError,
    }
    exec("def fail():\n    raise HostileError('hidden')", namespace)
    try:
        namespace["fail"]()  # type: ignore[operator]
    except HostileError as exc:
        diagnostic = failure_diagnostic(exc)
    assert hostile_module.calls == 0
    assert diagnostic.exception_type.startswith("test_error_contract.")
    assert "hidden" not in diagnostic.exception_type
    assert any(location.startswith("unknown:fail:") for location in diagnostic.stack_locations)
    assert len(diagnostic.stack_locations) <= 8


def test_public_models_require_exact_bounded_fields() -> None:
    payload = error_envelope(
        ProtocolError(
            parameters={"field": "request"},
            details={"reason": "invalid"},
            trace_id=TraceId(_TRACE_ID),
        )
    ).model_dump(mode="json")
    assert ErrorEnvelope.model_validate_json(json.dumps(payload)).model_dump(mode="json") == payload

    with pytest.raises(ValidationError):
        ErrorEnvelope.model_validate_json(json.dumps({**payload, "extra": True}))
    with pytest.raises(ValidationError):
        ErrorEnvelope.model_validate_json(
            json.dumps({"error": {**payload["error"], "message": _SECRET}})
        )
    missing_details = dict(payload["error"])
    del missing_details["details"]
    with pytest.raises(ValidationError):
        ErrorEnvelope.model_validate_json(json.dumps({"error": missing_details}))
    unsafe_integer = dict(payload["error"])
    unsafe_integer["details"] = {"sequence": MAX_ERROR_SAFE_INTEGER + 1}
    with pytest.raises(ValidationError):
        ErrorEnvelope.model_validate_json(json.dumps({"error": unsafe_integer}))


def test_public_error_fields_are_recursively_owned_and_immutable() -> None:
    source = {
        "error": {
            "code": "bridge.protocol_invalid",
            "category": "invalid",
            "parameters": {"operation": "stop"},
            "details": {"recovery": {"steps": ["retry"]}},
            "trace_id": _TRACE_ID,
        }
    }
    envelope = ErrorEnvelope.model_validate_json(json.dumps(source))
    source["error"]["details"] = {}

    with pytest.raises(TypeError):
        envelope.error.details["new"] = envelope.error.details["recovery"]  # type: ignore[index]
    recovery = envelope.error.details["recovery"].data
    assert isinstance(recovery, Mapping)
    with pytest.raises(TypeError):
        recovery["steps"] = ()  # type: ignore[index]
    assert envelope.model_dump(mode="json")["error"]["details"] == {
        "recovery": {"steps": ["retry"]}
    }


def test_http_and_tool_present_the_same_error_object() -> None:
    async def http_failure() -> None:
        raise ProtocolError(
            parameters={"field": "request"},
            details={"reason": "invalid_test_request"},
        )

    async def tool_failure(_request: EmptyRequest, _call: plugin_tools.ToolCall) -> SetupResult:
        raise ProtocolError(
            parameters={"field": "request"},
            details={"reason": "invalid_test_request"},
        )

    response = _request(
        _app_with_route("/failure", http_failure),
        "GET",
        "/failure",
        headers={"x-trace-id": _TRACE_ID},
    )
    tool_payload = json.loads(
        asyncio.run(
            plugin_tools._handler(EmptyRequest, SetupResult, tool_failure, owner=False)(
                {}, trace_id=_TRACE_ID
            )
        )
    )
    assert response.status_code == 400
    assert response.json()["error"] == tool_payload["error"]


def test_boundaries_do_not_serialize_cancellation() -> None:
    async def cancelled_http() -> None:
        raise asyncio.CancelledError

    async def cancelled_tool(_request: EmptyRequest, _call: plugin_tools.ToolCall) -> SetupResult:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        _request(_app_with_route("/cancel", cancelled_http), "GET", "/cancel")
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            plugin_tools._handler(EmptyRequest, SetupResult, cancelled_tool, owner=False)({})
        )


def test_unexpected_boundaries_hide_cause_and_log_only_safe_identity(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def http_failure() -> None:
        raise RuntimeError(f"{_SECRET} {_UNSAFE_PATH}")

    async def tool_failure(_request: EmptyRequest, _call: plugin_tools.ToolCall) -> SetupResult:
        raise RuntimeError(f"{_SECRET} {_UNSAFE_PATH}")

    caplog.set_level(logging.ERROR)
    response = _request(
        _app_with_route("/failure", http_failure),
        "GET",
        "/failure",
        headers={"x-trace-id": _TRACE_ID},
    )
    tool_payload = json.loads(
        asyncio.run(
            plugin_tools._handler(EmptyRequest, SetupResult, tool_failure, owner=False)(
                {}, trace_id=_TRACE_ID
            )
        )
    )
    for payload in (response.json(), tool_payload):
        assert payload["error"] == {
            "code": "internal.unexpected",
            "category": "internal",
            "parameters": {},
            "details": {},
            "trace_id": _TRACE_ID,
        }
        serialized = json.dumps(payload)
        assert _SECRET not in serialized
        assert _UNSAFE_PATH not in serialized

    logs = caplog.text
    assert logs.count(f"trace_id={_TRACE_ID}") == 2
    assert "exception_type=" in logs
    assert "stack_locations=" in logs
    assert _SECRET not in logs
    assert _UNSAFE_PATH not in logs
    assert all(record.exc_info is None for record in caplog.records)


def test_validation_error_uses_shared_safe_envelope() -> None:
    class Body(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)

        count: int

    async def endpoint(body: Body) -> dict[str, int]:
        return {"count": body.count}

    response = _request(
        _app_with_route("/validate", endpoint, method="POST"),
        "POST",
        "/validate",
        payload={"count": f"{_SECRET} {_UNSAFE_PATH}", "extra": _SECRET},
    )
    serialized = json.dumps(response.json())
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "request.invalid"
    assert "message" not in serialized
    assert '"msg"' not in serialized
    assert '"input"' not in serialized
    assert _SECRET not in serialized
    assert _UNSAFE_PATH not in serialized


def test_backend_error_codes_have_exact_english_and_chinese_keys() -> None:
    messages_path = Path(__file__).parents[2] / "src" / "renderer" / "i18n" / "messages.ts"
    script = """
import { build } from 'esbuild';
const result = await build({
  bundle: true,
  entryPoints: [process.argv[1]],
  format: 'esm',
  logLevel: 'silent',
  platform: 'node',
  target: 'node22',
  write: false,
});
if (result.outputFiles.length !== 1) throw new Error('unexpected locale bundle output');
const encoded = Buffer.from(result.outputFiles[0].contents).toString('base64');
const { bundles } = await import(`data:text/javascript;base64,${encoded}`);
function leaves(value, prefix = '') {
  return Object.entries(value).flatMap(([key, item]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return item && typeof item === 'object' ? leaves(item, path) : [path];
  });
}
console.log(JSON.stringify({ en: leaves(bundles.en.errors), zh: leaves(bundles.zh.errors) }));
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "--eval", script, str(messages_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    locale_codes = json.loads(completed.stdout)
    expected = sorted(error_type.code for error_type in APPLICATION_ERROR_TYPES)
    assert sorted(locale_codes["en"]) == expected
    assert sorted(locale_codes["zh"]) == expected
