"""Shared HTTP and Hermes envelope for incomplete start rollback."""

from __future__ import annotations

import asyncio
import json
from typing import cast

import httpx
from fastapi import FastAPI
from toqraq.api import build_router
from toqraq.contracts.sessions import GameStartRequest, SessionResult
from toqraq.core.errors import SessionCleanupError
from toqraq.hermes.tools import build_tools
from toqraq.services.container import Container

TRACE_ID = "8f489b96-c438-4d13-a54d-9e3f1020f531"
SECRET_CAUSE = "private launch and cleanup detail"


class FailingSessionService:
    """Raise the stable error that a retained failed start exposes."""

    async def start(self, owner: str, _request: GameStartRequest) -> SessionResult:
        raise SessionCleanupError(
            parameters={"session_id": owner, "run_revision": 4},
            details={"reason": "start_rollback_incomplete", "retryable": True},
            cause=ExceptionGroup("start and rollback failed", [RuntimeError(SECRET_CAUSE)]),
        )


class StartErrorContainer:
    """Provide only the service exercised by the lazy presenter closures."""

    session_service = FailingSessionService()


def test_incomplete_start_rollback_has_one_http_and_hermes_error_envelope() -> None:
    container = cast(Container, StartErrorContainer())
    app = FastAPI()
    app.include_router(build_router(container))

    async def invoke_http() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/sessions",
                headers={"x-trace-id": TRACE_ID},
                json={"hermes_session": "owner", "project_dir": "D:/game"},
            )

    response = asyncio.run(invoke_http())
    handler = next(
        tool.handler for tool in build_tools(container) if tool.name == "toqraq_game_start"
    )
    tool_payload = json.loads(
        asyncio.run(
            handler(
                {"project_dir": "D:/game"},
                task_id="owner",
                trace_id=TRACE_ID,
            )
        )
    )

    assert response.status_code == 502
    assert response.json() == tool_payload
    assert response.json() == {
        "error": {
            "code": "session.cleanup_failed",
            "category": "upstream",
            "parameters": {"session_id": "owner", "run_revision": 4},
            "details": {"reason": "start_rollback_incomplete", "retryable": True},
            "trace_id": TRACE_ID,
        }
    }
    assert SECRET_CAUSE not in response.text
