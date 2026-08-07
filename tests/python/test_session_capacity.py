"""Public list capacity across active and still-starting Hermes sessions."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest
from toqraq.contracts.sessions import GameStartRequest
from toqraq.core.errors import SessionStateError
from toqraq.core.process_tree import ProcessEnvironment
from toqraq.core.session_capacity import MAX_CONCURRENT_GAME_SESSIONS
from toqraq.core.session_registry import SessionRegistry
from toqraq.services.events import SessionEventStream
from toqraq.services.session_gate import SessionOperationGate
from toqraq.services.session_supervision import SessionSupervision
from toqraq.services.sessions import SessionService

from _session_service_support import CREDENTIAL, HOST, SessionFixture, make_fixture


def _service(fixture: SessionFixture) -> SessionService:
    registry = SessionRegistry()
    return SessionService(
        selection=fixture.selection,
        registry=registry,
        events=SessionEventStream(clock=lambda: 100.0),
        host=HOST,
        connection_factory=fixture.connections,
        launcher=fixture.launcher,
        environment=ProcessEnvironment(variables=()),
        gate=SessionOperationGate(),
        credential_factory=lambda: CREDENTIAL,
        clock=lambda: 200.0,
    )


def _request(root: Path) -> GameStartRequest:
    return GameStartRequest(project_dir=str(root))


def test_public_session_list_never_exceeds_capacity_during_pending_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        monkeypatch.setattr(
            SessionSupervision,
            "start",
            lambda _self, _session, _locator: None,
        )
        fixture = make_fixture(tmp_path)
        service = _service(fixture)
        active_ids = tuple(f"active-{index}" for index in range(MAX_CONCURRENT_GAME_SESSIONS - 1))
        for session_id in active_ids:
            await service.start(session_id, _request(tmp_path))
        entered = threading.Event()
        release = threading.Event()
        fixture.provisioner.entered = entered
        fixture.provisioner.release = release
        pending = asyncio.create_task(service.start("pending", _request(tmp_path)))
        assert await asyncio.to_thread(entered.wait, 1)

        with pytest.raises(SessionStateError) as captured:
            await service.start("overflow", _request(tmp_path))
        assert captured.value.details == {
            "reason": "session_capacity_exhausted",
            "retryable": True,
        }

        release.set()
        await pending
        assert len(service.list().root) == MAX_CONCURRENT_GAME_SESSIONS
        await service.stop(active_ids[0])
        await service.start("overflow", _request(tmp_path))
        assert len(service.list().root) == MAX_CONCURRENT_GAME_SESSIONS
        await service.close()

    asyncio.run(scenario())
