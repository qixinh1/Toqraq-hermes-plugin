"""Session-owned native preview display use-case tests."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest
from toqraq.core.errors import (
    CapabilityUnavailableError,
    EmbedError,
    UnsupportedPlatformError,
)
from toqraq.core.geometry import Point, Rect, Size
from toqraq.core.preview import NativeWindowReference, NativeWindowSurface
from toqraq.core.session import EngineSession
from toqraq.core.session_registry import SessionRegistry
from toqraq.services.display import NativeDisplayService
from toqraq.services.session_gate import SessionOperationGate

from _session_domain_support import make_session

_SESSION_ID = "display-session"
_ATTACHMENT_ID = "renderer-pane-1"
_CHILD = NativeWindowReference(value=123)
_HOST = NativeWindowReference(value=456)
_PANE = Rect(100, 50, 800, 600)
_HOST_POINT = Point(500, 350)
_DESTINATION = Rect(100, 125, 800, 450)


class _Display:
    """Record exact synchronous platform calls and controllable failures."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.attach_failure: Exception | None = None
        self.restore_failures = 0
        self.attach_started: threading.Event | None = None
        self.attach_release: threading.Event | None = None

    def locate_host(
        self,
        point: Point,
        *,
        excluded_process_id: int,
    ) -> NativeWindowReference:
        self.calls.append(("locate", point, excluded_process_id))
        return _HOST

    def attach(
        self,
        child: NativeWindowReference,
        host: NativeWindowReference,
    ) -> None:
        self.calls.append(("attach", child, host))
        if self.attach_started is not None:
            self.attach_started.set()
        if self.attach_release is not None and not self.attach_release.wait(2):
            raise TimeoutError("attach release timed out")
        if self.attach_failure is not None:
            raise self.attach_failure

    def restore(self, child: NativeWindowReference) -> None:
        self.calls.append(("restore", child))
        if self.restore_failures > 0:
            self.restore_failures -= 1
            raise OSError("restore failed")

    def follow(
        self,
        child: NativeWindowReference,
        rect: Rect,
        host: NativeWindowReference,
    ) -> None:
        self.calls.append(("follow", child, rect, host))

    def set_visible(self, child: NativeWindowReference, visible: bool) -> None:
        self.calls.append(("visible", child, visible))


def _service_fixture(
    root: Path,
    display: _Display | None,
    *,
    publish_preview: bool = True,
    viewport_size: Size | None = None,
) -> tuple[NativeDisplayService, EngineSession]:
    registry = SessionRegistry()
    owner = registry.issue_owner(_SESSION_ID)
    session, _process, _connection, _ports, _lease = make_session(root, owner)
    assert registry.compare_and_swap(None, session)
    if publish_preview:
        session.publish_preview(
            NativeWindowSurface(
                window=_CHILD,
                viewport_size=viewport_size or Size(width=960, height=540),
            )
        )
    return NativeDisplayService(registry, SessionOperationGate(), display), session


def test_attach_locates_mutates_follows_and_transfers_cleanup_owner(tmp_path: Path) -> None:
    async def run() -> None:
        display = _Display()
        service, session = _service_fixture(tmp_path, display)

        result = await service.attach(_SESSION_ID, _ATTACHMENT_ID, _PANE)

        assert result.id == _SESSION_ID
        assert session.resources.preview_attachment is not None
        assert display.calls == [
            ("locate", _HOST_POINT, 4_242),
            ("attach", _CHILD, _HOST),
            ("follow", _CHILD, _DESTINATION, _HOST),
        ]
        await session.close()
        assert display.calls[-1] == ("restore", _CHILD)

    asyncio.run(run())


def test_attach_and_resize_fit_the_authoritative_portrait_viewport(tmp_path: Path) -> None:
    async def run() -> None:
        display = _Display()
        service, session = _service_fixture(
            tmp_path,
            display,
            viewport_size=Size(width=1_080, height=1_920),
        )
        odd_pane = Rect(100, 50, 801, 601)

        await service.attach(_SESSION_ID, _ATTACHMENT_ID, odd_pane)
        assert display.calls[-1] == ("follow", _CHILD, Rect(331, 50, 338, 601), _HOST)

        resized_pane = Rect(20, 30, 601, 801)
        await service.follow(_SESSION_ID, _ATTACHMENT_ID, resized_pane)
        assert display.calls[-1] == ("follow", _CHILD, Rect(95, 30, 451, 801), _HOST)
        await session.close()

    asyncio.run(run())


def test_same_owner_only_follows_and_exact_owner_controls_attachment(tmp_path: Path) -> None:
    async def run() -> None:
        display = _Display()
        service, session = _service_fixture(tmp_path, display)
        await service.attach(_SESSION_ID, _ATTACHMENT_ID, _PANE)
        changed_pane = Rect(110, 130, 640, 640)
        changed_destination = Rect(110, 270, 640, 360)

        await service.attach(_SESSION_ID, _ATTACHMENT_ID, changed_pane)
        await service.follow(_SESSION_ID, "stale-pane", Rect(1, 1, 1, 1))
        await service.set_visible(_SESSION_ID, "stale-pane", False)
        await service.detach(_SESSION_ID, "stale-pane")

        assert [call[0] for call in display.calls] == [
            "locate",
            "attach",
            "follow",
            "follow",
        ]
        assert display.calls[-1] == ("follow", _CHILD, changed_destination, _HOST)
        assert session.resources.preview_attachment is not None
        await service.set_visible(_SESSION_ID, _ATTACHMENT_ID, False)
        await service.detach(_SESSION_ID, _ATTACHMENT_ID)
        assert display.calls[-2:] == [
            ("visible", _CHILD, False),
            ("restore", _CHILD),
        ]
        assert session.resources.preview_attachment is None
        await session.close()

    asyncio.run(run())


def test_new_owner_restores_old_mutation_before_attaching(tmp_path: Path) -> None:
    async def run() -> None:
        display = _Display()
        service, session = _service_fixture(tmp_path, display)
        await service.attach(_SESSION_ID, _ATTACHMENT_ID, _PANE)

        await service.attach(_SESSION_ID, "renderer-pane-2", _PANE)

        assert [call[0] for call in display.calls] == [
            "locate",
            "attach",
            "follow",
            "restore",
            "locate",
            "attach",
            "follow",
        ]
        await session.close()

    asyncio.run(run())


def test_partial_attach_with_failed_rollback_remains_session_owned(tmp_path: Path) -> None:
    async def run() -> None:
        display = _Display()
        display.attach_failure = OSError("partial attach")
        display.restore_failures = 1
        service, session = _service_fixture(tmp_path, display)

        with pytest.raises(EmbedError) as captured:
            await service.attach(_SESSION_ID, _ATTACHMENT_ID, _PANE)

        assert captured.value.details["rollback_pending"] is True
        assert session.resources.preview_attachment is not None
        display.attach_failure = None
        await service.detach(_SESSION_ID, _ATTACHMENT_ID)
        assert session.resources.preview_attachment is None
        assert [call[0] for call in display.calls].count("restore") == 2
        await session.close()

    asyncio.run(run())


def test_attach_cancellation_waits_for_native_settlement_then_restores(tmp_path: Path) -> None:
    async def run() -> None:
        display = _Display()
        display.attach_started = threading.Event()
        display.attach_release = threading.Event()
        service, session = _service_fixture(tmp_path, display)
        operation = asyncio.create_task(service.attach(_SESSION_ID, _ATTACHMENT_ID, _PANE))
        assert await asyncio.to_thread(display.attach_started.wait, 2)

        operation.cancel()
        display.attach_release.set()
        with pytest.raises(asyncio.CancelledError):
            await operation

        assert display.calls[-1] == ("restore", _CHILD)
        assert session.resources.preview_attachment is None
        await session.close()

    asyncio.run(run())


def test_unavailable_platform_and_unready_preview_fail_without_mutation(tmp_path: Path) -> None:
    async def run() -> None:
        unavailable, session = _service_fixture(tmp_path, None)
        with pytest.raises(UnsupportedPlatformError):
            await unavailable.attach(_SESSION_ID, _ATTACHMENT_ID, _PANE)
        await session.close()

        display = _Display()
        unready, session = _service_fixture(tmp_path, display, publish_preview=False)
        with pytest.raises(CapabilityUnavailableError):
            await unready.attach(_SESSION_ID, _ATTACHMENT_ID, _PANE)
        assert display.calls == []
        await session.close()

    asyncio.run(run())


def test_late_renderer_effects_are_idempotent_after_session_disappears(tmp_path: Path) -> None:
    async def run() -> None:
        display = _Display()
        service, session = _service_fixture(tmp_path, display)

        assert (await service.follow("missing-session", _ATTACHMENT_ID, _PANE)).ok
        assert (await service.set_visible("missing-session", _ATTACHMENT_ID, True)).ok
        assert (await service.detach("missing-session", _ATTACHMENT_ID)).ok
        assert display.calls == []
        await session.close()

    asyncio.run(run())
