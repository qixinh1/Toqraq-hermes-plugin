"""Godot player-window discovery tests over the focused platform port."""

from __future__ import annotations

import asyncio
from pathlib import Path
from threading import Event

import pytest
from toqraq.core.engine_contribution import ProjectDescription
from toqraq.core.errors import (
    GameWindowNotFoundError,
    PlatformOperationError,
    RequestCancelledError,
)
from toqraq.core.geometry import Size
from toqraq.core.native_preview import NativeWindowCandidate
from toqraq.core.preview import NativeWindowReference
from toqraq.core.process_tree import ProcessOutputSnapshot
from toqraq.core.runtime import (
    PreparedRuntime,
    RuntimeEntryPoint,
    RuntimeEntryPointBinding,
    RuntimeIdentity,
    RuntimeRelease,
)
from toqraq.engines.godot.preview_locator import (
    GodotPreviewLocator,
    GodotPreviewLocatorPolicy,
)

_COMPONENT_ID = "1" * 64


class _Resource:
    async def close(self) -> None:
        return None


class _ProcessTree:
    root_pid = 42

    def __init__(self, exit_code: int | None = None) -> None:
        self.exit_code = exit_code

    def poll(self) -> int | None:
        return self.exit_code

    def wait(self, timeout: float) -> int:
        del timeout
        if self.exit_code is None:
            raise TimeoutError
        return self.exit_code

    def output(self) -> ProcessOutputSnapshot:
        return ProcessOutputSnapshot(
            chunks=(),
            next_sequence=1,
            truncated=False,
            failed_streams=frozenset(),
        )

    def close(self, *, graceful_timeout: float, forced_timeout: float) -> None:
        del graceful_timeout, forced_timeout
        self.exit_code = 0


class _Discovery:
    def __init__(
        self,
        responses: list[tuple[NativeWindowCandidate, ...]] | None = None,
        failure: Exception | None = None,
    ) -> None:
        self.responses = responses or [()]
        self.failure = failure
        self.calls: list[int] = []

    def for_process(self, process_id: int) -> tuple[NativeWindowCandidate, ...]:
        self.calls.append(process_id)
        if self.failure is not None:
            raise self.failure
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]


class _ManualTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.delays: list[float] = []

    def clock(self) -> float:
        return self.now

    async def delay(self, seconds: float) -> None:
        self.delays.append(seconds)
        self.now += seconds


def _project(root: Path, engine_id: str = "godot") -> ProjectDescription:
    return ProjectDescription(
        engine_id=engine_id,
        project_root=root,
        marker_path=root / "project.godot",
        confidence=100,
        display_size_hint=Size(width=640, height=360),
    )


def _runtime(root: Path) -> PreparedRuntime:
    release = RuntimeRelease(
        identity=RuntimeIdentity(
            engine_id="godot",
            version="4.7.1-stable",
            build_id="toqraq.windows.x86_64.release",
            distribution_id="toqraq",
            platform="windows",
            architecture="x86_64",
        ),
        component_release_ids=(_COMPONENT_ID,),
        entry_point_bindings=(
            RuntimeEntryPointBinding(
                name="editor",
                component_release_id=_COMPONENT_ID,
                component_entry_point_name="editor",
            ),
        ),
        bridge_id="toqraq.godot.bridge",
        bridge_protocol="1.0",
    )
    return PreparedRuntime(
        release=release,
        entry_points=(RuntimeEntryPoint(name="editor", path=root / "godot.exe"),),
        owned_resources=(_Resource(),),
    )


def _candidate(handle: int, width: int, height: int) -> NativeWindowCandidate:
    return NativeWindowCandidate(
        window=NativeWindowReference(value=handle),
        process_id=42,
        client_size=Size(width=width, height=height),
    )


def _locator(discovery: _Discovery, time: _ManualTime) -> GodotPreviewLocator:
    return GodotPreviewLocator(
        discovery,
        GodotPreviewLocatorPolicy(timeout_seconds=1, poll_seconds=0.1),
        clock=time.clock,
        delay=time.delay,
    )


def test_locator_selects_largest_client_and_uses_its_real_size(tmp_path: Path) -> None:
    """Project hints never replace the authoritative live client geometry."""
    discovery = _Discovery([(_candidate(2, 800, 600), _candidate(1, 1280, 720))])
    time = _ManualTime()
    surface = asyncio.run(
        _locator(discovery, time).locate(
            _project(tmp_path),
            _runtime(tmp_path),
            _ProcessTree(),
            Event(),
        )
    )

    assert surface.window == NativeWindowReference(value=1)
    assert surface.viewport_size == Size(width=1280, height=720)
    assert discovery.calls == [42]
    assert time.delays == []


def test_locator_polls_with_injected_time_until_the_window_exists(tmp_path: Path) -> None:
    """Readiness polling is deterministic and carries no real-clock sleep."""
    discovery = _Discovery([(), (_candidate(1, 960, 540),)])
    time = _ManualTime()
    surface = asyncio.run(
        _locator(discovery, time).locate(
            _project(tmp_path),
            _runtime(tmp_path),
            _ProcessTree(),
            Event(),
        )
    )

    assert surface.viewport_size == Size(width=960, height=540)
    assert discovery.calls == [42, 42]
    assert time.delays == [0.1]


def test_locator_exposes_cancellation_process_exit_and_deadline(tmp_path: Path) -> None:
    """Every terminal wait path returns a focused typed failure."""
    cancellation = Event()
    cancellation.set()
    with pytest.raises(RequestCancelledError):
        asyncio.run(
            _locator(_Discovery(), _ManualTime()).locate(
                _project(tmp_path),
                _runtime(tmp_path),
                _ProcessTree(),
                cancellation,
            )
        )

    with pytest.raises(GameWindowNotFoundError) as exited:
        asyncio.run(
            _locator(_Discovery(), _ManualTime()).locate(
                _project(tmp_path),
                _runtime(tmp_path),
                _ProcessTree(exit_code=7),
                Event(),
            )
        )
    assert exited.value.details == {"reason": "process_exited", "exit_code": 7}

    with pytest.raises(GameWindowNotFoundError) as timed_out:
        asyncio.run(
            _locator(_Discovery(), _ManualTime()).locate(
                _project(tmp_path),
                _runtime(tmp_path),
                _ProcessTree(),
                Event(),
            )
        )
    assert timed_out.value.details == {"reason": "deadline_exceeded", "retryable": True}


def test_locator_translates_unexpected_platform_failure(tmp_path: Path) -> None:
    """Engine code never exports an unstructured native exception."""
    locator = _locator(_Discovery(failure=OSError("private native text")), _ManualTime())
    with pytest.raises(PlatformOperationError) as captured:
        asyncio.run(
            locator.locate(
                _project(tmp_path),
                _runtime(tmp_path),
                _ProcessTree(),
                Event(),
            )
        )
    assert captured.value.details == {"reason": "native_call_failed"}
    assert captured.value.parameters == {"operation": "discover_game_window"}


def test_locator_rejects_cross_engine_project_before_native_access(tmp_path: Path) -> None:
    """A contribution cannot locate a preview for another engine's project."""
    discovery = _Discovery()
    with pytest.raises(ValueError):
        asyncio.run(
            _locator(discovery, _ManualTime()).locate(
                _project(tmp_path, "unity"),
                _runtime(tmp_path),
                _ProcessTree(),
                Event(),
            )
        )
    assert discovery.calls == []
