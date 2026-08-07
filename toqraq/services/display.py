"""Session-owned native preview attachment and geometry use cases."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from ..contracts.preview import PreviewOperationResult
from ..contracts.sessions import SessionResult
from ..core.capability_ids import PREVIEW_DISPLAY_CAPABILITY_ID
from ..core.errors import (
    CapabilityUnavailableError,
    EmbedError,
    SessionStateError,
    ToqraqError,
    UnsupportedPlatformError,
)
from ..core.geometry import Rect
from ..core.native_display import NativeDisplay
from ..core.preview import NativeWindowReference, NativeWindowSurface
from ..core.preview_geometry import aspect_fit_rect, pane_host_point
from ..core.session import EngineSession
from ..core.session_readiness import FeatureReadiness
from ..core.session_registry import SessionRegistry
from ..core.session_snapshot import SessionProcessState
from .session_gate import SessionOperationGate

P = ParamSpec("P")
T = TypeVar("T")


class NativeDisplayService:
    """Bind renderer attachment ownership to the same game-run resource graph."""

    __slots__ = ("_display", "_gate", "_registry")

    def __init__(
        self,
        registry: SessionRegistry,
        gate: SessionOperationGate,
        display: NativeDisplay | None,
    ) -> None:
        """Bind authoritative sessions, their mutation gate, and one platform port."""
        if not isinstance(registry, SessionRegistry):
            raise ValueError("native display registry is invalid")
        if not isinstance(gate, SessionOperationGate):
            raise ValueError("native display session gate is invalid")
        if display is not None and not isinstance(display, NativeDisplay):
            raise ValueError("native display platform port is invalid")
        self._registry = registry
        self._gate = gate
        self._display = display

    async def attach(
        self,
        session_id: str,
        attachment_id: str,
        pane_rect: Rect,
    ) -> SessionResult:
        """Attach the already-located native surface and transfer its cleanup owner."""
        lease = await self._gate.acquire(session_id)
        async with lease:
            session = self._registry.get(session_id)
            surface = _require_native_surface(session)
            display = self._require_display()
            destination = aspect_fit_rect(pane_rect, surface.viewport_size)
            current = _native_attachment(session)
            if current is not None and current.owner_id == attachment_id:
                await current.follow(destination)
                return SessionResult.from_snapshot(session.snapshot())
            await session.resources.close_preview_attachment()
            attachment: _NativeAttachment | None = None
            try:
                host = await _native_call(
                    display.locate_host,
                    pane_host_point(pane_rect),
                    excluded_process_id=session.snapshot().root_pid,
                )
                attachment = _NativeAttachment(
                    owner_id=attachment_id,
                    session_id=session_id,
                    display=display,
                    child=surface.window,
                    host=host,
                )
                await _native_call(display.attach, surface.window, host)
                await attachment.follow(destination)
                session.resources.retain_preview_attachment(attachment)
            except (asyncio.CancelledError, Exception) as exc:
                rollback_failure = await _rollback_failed_attach(session, attachment)
                if isinstance(exc, asyncio.CancelledError):
                    raise
                if isinstance(exc, ToqraqError) and rollback_failure is None:
                    raise
                raise EmbedError(
                    parameters={"session_id": session_id},
                    details={
                        "reason": "attach_failed",
                        "retryable": True,
                        "rollback_pending": rollback_failure is not None,
                    },
                    cause=rollback_failure or exc,
                ) from exc
            return SessionResult.from_snapshot(session.snapshot())

    async def follow(
        self,
        session_id: str,
        attachment_id: str,
        pane_rect: Rect,
    ) -> PreviewOperationResult:
        """Fit and apply the latest pane geometry to its exact attachment."""
        lease = await self._gate.acquire(session_id)
        async with lease:
            session = self._registry.find(session_id)
            if session is None or not _session_is_live(session):
                return PreviewOperationResult(ok=True)
            attachment = _native_attachment(session)
            if attachment is not None and attachment.owner_id == attachment_id:
                surface = _require_native_surface(session)
                await attachment.follow(aspect_fit_rect(pane_rect, surface.viewport_size))
            return PreviewOperationResult(ok=True)

    async def set_visible(
        self,
        session_id: str,
        attachment_id: str,
        visible: bool,
    ) -> PreviewOperationResult:
        """Show or hide only the renderer attachment that owns the mutation."""
        lease = await self._gate.acquire(session_id)
        async with lease:
            session = self._registry.find(session_id)
            if session is None or not _session_is_live(session):
                return PreviewOperationResult(ok=True)
            attachment = _native_attachment(session)
            if attachment is not None and attachment.owner_id == attachment_id:
                await attachment.set_visible(visible)
            return PreviewOperationResult(ok=True)

    async def detach(
        self,
        session_id: str,
        attachment_id: str,
    ) -> PreviewOperationResult:
        """Restore only the exact current renderer-owned native mutation."""
        lease = await self._gate.acquire(session_id)
        async with lease:
            session = self._registry.find(session_id)
            if session is None:
                return PreviewOperationResult(ok=True)
            attachment = _native_attachment(session)
            if attachment is not None and attachment.owner_id == attachment_id:
                await session.resources.close_preview_attachment()
            return PreviewOperationResult(ok=True)

    def _require_display(self) -> NativeDisplay:
        """Return the composed native port or one stable unsupported-host failure."""
        if self._display is None:
            raise UnsupportedPlatformError(
                parameters={"feature": "native_preview"},
                details={"reason": "native_display_unavailable"},
            )
        return self._display


class _NativeAttachment:
    """Own one reversible platform mutation after a successful attach transaction."""

    __slots__ = ("_child", "_closed", "_display", "_host", "_session_id", "owner_id")

    def __init__(
        self,
        *,
        owner_id: str,
        session_id: str,
        display: NativeDisplay,
        child: NativeWindowReference,
        host: NativeWindowReference,
    ) -> None:
        """Retain exact renderer, session, child, host, and platform identities."""
        self.owner_id = owner_id
        self._session_id = session_id
        self._display = display
        self._child = child
        self._host = host
        self._closed = False

    async def follow(self, rect: Rect) -> None:
        """Move the live child to one validated pane-owned rectangle."""
        self._require_open()
        try:
            await _native_call(self._display.follow, self._child, rect, self._host)
        except (asyncio.CancelledError, ToqraqError):
            raise
        except Exception as exc:
            raise EmbedError(
                parameters={"session_id": self._session_id},
                details={"reason": "follow_failed", "retryable": True},
                cause=exc,
            ) from exc

    async def set_visible(self, visible: bool) -> None:
        """Apply visibility without changing attachment ownership."""
        self._require_open()
        try:
            await _native_call(self._display.set_visible, self._child, visible)
        except (asyncio.CancelledError, ToqraqError):
            raise
        except Exception as exc:
            raise EmbedError(
                parameters={"session_id": self._session_id},
                details={"reason": "visibility_failed", "retryable": True},
                cause=exc,
            ) from exc

    async def close(self) -> None:
        """Restore the exact native child once, retaining ownership on failure."""
        if self._closed:
            return
        try:
            await _native_call(self._display.restore, self._child)
        except (asyncio.CancelledError, ToqraqError):
            raise
        except Exception as exc:
            raise EmbedError(
                parameters={"session_id": self._session_id},
                details={"reason": "restore_failed", "retryable": True},
                cause=exc,
            ) from exc
        self._closed = True

    def _require_open(self) -> None:
        """Reject geometry updates after restoration completed."""
        if self._closed:
            raise SessionStateError(details={"reason": "preview_attachment_closed"})


def _require_native_surface(session: EngineSession) -> NativeWindowSurface:
    """Return one ready native surface with its advertised display capability."""
    snapshot = session.snapshot()
    if PREVIEW_DISPLAY_CAPABILITY_ID not in snapshot.capability_ids:
        raise CapabilityUnavailableError(
            details={
                "reason": "capability_not_advertised",
                "capability_id": PREVIEW_DISPLAY_CAPABILITY_ID,
            }
        )
    if snapshot.preview.state is not FeatureReadiness.READY:
        raise CapabilityUnavailableError(details={"reason": "preview_not_ready"})
    surface = session.preview_surface
    if not isinstance(surface, NativeWindowSurface):
        raise CapabilityUnavailableError(details={"reason": "native_preview_unavailable"})
    return surface


def _native_attachment(session: EngineSession) -> _NativeAttachment | None:
    """Return the optional session-owned native attachment with exact type."""
    attachment = session.resources.preview_attachment
    if attachment is None:
        return None
    if not isinstance(attachment, _NativeAttachment):
        raise SessionStateError(details={"reason": "preview_attachment_type_invalid"})
    return attachment


def _session_is_live(session: EngineSession) -> bool:
    """Return whether renderer effects may still mutate this exact run."""
    return session.process_state in {
        SessionProcessState.RUNNING,
        SessionProcessState.PAUSED,
    }


async def _rollback_failed_attach(
    session: EngineSession,
    attachment: _NativeAttachment | None,
) -> Exception | None:
    """Restore a failed mutation or retain its exact owner for cleanup retry."""
    if attachment is None:
        return None
    try:
        await attachment.close()
    except asyncio.CancelledError:
        session.resources.retain_preview_attachment(attachment)
        raise
    except Exception as exc:
        session.resources.retain_preview_attachment(attachment)
        return exc
    return None


async def _native_call(function: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """Let one blocking native call settle before propagating cancellation."""
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        with contextlib.suppress(Exception):
            await task
        raise
