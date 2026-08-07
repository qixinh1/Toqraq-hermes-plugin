"""Plugin composition-root shutdown ownership tests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast

import pytest
from toqraq.services import container as container_module
from toqraq.services.container import Container, dispose_container


class _Owner:
    """Record one mutable owner gate and controllable asynchronous drain."""

    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        started: asyncio.Event | None = None,
        release: asyncio.Event | None = None,
        failure: Exception | None = None,
    ) -> None:
        self._name = name
        self._events = events
        self._started = started
        self._release = release
        self._failure = failure

    def begin_close(self) -> None:
        self._events.append(f"gate:{self._name}")

    async def close(self) -> None:
        self._events.append(f"close:{self._name}:start")
        if self._started is not None:
            self._started.set()
        if self._release is not None:
            await self._release.wait()
        if self._failure is not None:
            raise self._failure
        self._events.append(f"close:{self._name}:end")

    def allow_close(self) -> None:
        """Make a retained test owner succeed on its next cleanup attempt."""
        self._failure = None


def _container(sessions: _Owner, components: _Owner) -> Container:
    absent = cast(Any, object())
    return Container(
        events=absent,
        session_service=cast(Any, sessions),
        simulation_service=absent,
        display_service=absent,
        hierarchy_service=absent,
        object_inspection_service=absent,
        diagnostics_service=absent,
        process_output_service=absent,
        metrics_service=absent,
        frame_capture_service=absent,
        input_service=absent,
        component_jobs=cast(Any, components),
        setup_service=absent,
        workspace_context_service=cast(Any, SimpleNamespace(close=lambda: None)),
    )


def test_container_seals_both_owners_before_either_drain_starts() -> None:
    async def run() -> None:
        events: list[str] = []
        sessions = _Owner("sessions", events)
        components = _Owner("components", events)

        await _container(sessions, components).close()

        assert events[:2] == ["gate:sessions", "gate:components"]
        assert set(events[2:]) == {
            "close:sessions:start",
            "close:components:start",
            "close:sessions:end",
            "close:components:end",
        }

    asyncio.run(run())


def test_container_attempts_both_independent_drains_when_one_fails() -> None:
    async def run() -> None:
        events: list[str] = []
        sessions = _Owner("sessions", events, failure=OSError("session cleanup failed"))
        components = _Owner("components", events)

        with pytest.raises(BaseExceptionGroup) as captured:
            await _container(sessions, components).close()

        assert len(captured.value.exceptions) == 1
        assert "close:sessions:start" in events
        assert "close:components:end" in events

    asyncio.run(run())


def test_cancelling_disposer_waits_for_both_drains_to_settle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> None:
        events: list[str] = []
        release = asyncio.Event()
        sessions_started = asyncio.Event()
        components_started = asyncio.Event()
        container = _container(
            _Owner("sessions", events, started=sessions_started, release=release),
            _Owner("components", events, started=components_started, release=release),
        )
        monkeypatch.setattr(container_module, "_instance", container)
        disposing = asyncio.create_task(dispose_container(container))
        await sessions_started.wait()
        await components_started.wait()

        disposing.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await disposing

        assert "close:sessions:end" in events
        assert "close:components:end" in events
        assert container_module.get_container() is container

    asyncio.run(run())


def test_failed_instance_disposal_retains_owner_until_successful_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> None:
        events: list[str] = []
        sessions = _Owner(
            "sessions",
            events,
            failure=OSError("session cleanup failed"),
        )
        first = _container(sessions, _Owner("components", events))
        replacement = _container(_Owner("next-sessions", []), _Owner("next-components", []))
        monkeypatch.setattr(container_module, "_instance", first)
        monkeypatch.setattr(container_module, "build_container", lambda: replacement)

        with pytest.raises(BaseExceptionGroup):
            await dispose_container(first)

        assert container_module.get_container() is first
        sessions.allow_close()
        await dispose_container(first)

        assert container_module.get_container() is replacement

    asyncio.run(run())


def test_stale_disposer_cannot_clear_a_newer_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> None:
        release = asyncio.Event()
        started = asyncio.Event()
        first = _container(
            _Owner("sessions", [], started=started, release=release),
            _Owner("components", []),
        )
        replacement = _container(_Owner("next-sessions", []), _Owner("next-components", []))
        monkeypatch.setattr(container_module, "_instance", first)

        disposing = asyncio.create_task(dispose_container(first))
        await started.wait()
        container_module._instance = replacement
        release.set()
        await disposing

        assert container_module.get_container() is replacement

    asyncio.run(run())
