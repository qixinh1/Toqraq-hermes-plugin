"""Failure-atomic contracts for the Windows native embed adapter."""

from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows adapter only")


def test_host_lookup_skips_noninteractive_overlays(monkeypatch) -> None:
    """Screen overlays cannot become the native owner of a game window."""
    from toqraq.platforms.windows import host_window

    def enumerate_windows(visitor) -> None:
        for handle in (10, 20):
            if not visitor(handle):
                return

    monkeypatch.setattr(host_window.native, "enumerate_windows", enumerate_windows)
    monkeypatch.setattr(host_window.native, "is_window_visible", lambda _handle: True)
    monkeypatch.setattr(host_window.native, "get_window_rect", lambda _handle: (0, 0, 100, 100))
    monkeypatch.setattr(host_window.native, "get_window_process_id", lambda _handle: 42)
    monkeypatch.setattr(
        host_window.native,
        "get_window_long",
        lambda handle, _index: host_window._NONINTERACTIVE if handle == 10 else 0,
    )

    assert host_window.locate_host_window((50, 50), excluded_process_id=99) == 20


def test_host_lookup_requires_an_exact_excluded_process(monkeypatch) -> None:
    from toqraq.platforms.windows import host_window

    monkeypatch.setattr(host_window.native, "enumerate_windows", lambda _visitor: None)

    with pytest.raises(ValueError, match="excluded process"):
        host_window.locate_host_window((50, 50), excluded_process_id=0)


def test_native_embed_rolls_back_partial_preparation(monkeypatch) -> None:
    from toqraq.core.preview import NativeWindowReference
    from toqraq.platforms.windows import native_display

    state = object()
    restored: list[tuple[int, object]] = []
    monkeypatch.setattr(native_display.dpi, "ensure_dpi_awareness", lambda: None)
    monkeypatch.setattr(native_display.native, "is_window", lambda _window: True)
    monkeypatch.setattr(native_display.embedder, "snapshot", lambda _window: state)
    monkeypatch.setattr(
        native_display.embedder,
        "embed",
        lambda _child, _host: (_ for _ in ()).throw(RuntimeError("partial mutation")),
    )
    monkeypatch.setattr(
        native_display.embedder,
        "restore",
        lambda child, saved: restored.append((child, saved)),
    )
    windows = native_display.WindowsNativeDisplay()

    with pytest.raises(RuntimeError, match="partial"):
        windows.attach(NativeWindowReference(value=123), NativeWindowReference(value=456))

    assert restored == [(123, state)]
    assert windows._embedded == {}


def test_native_detach_retains_snapshot_when_restore_fails(monkeypatch) -> None:
    from toqraq.core.preview import NativeWindowReference
    from toqraq.platforms.windows import native_display

    state = object()
    monkeypatch.setattr(native_display.dpi, "ensure_dpi_awareness", lambda: None)
    monkeypatch.setattr(native_display.native, "is_window", lambda _window: True)
    monkeypatch.setattr(
        native_display.embedder,
        "restore",
        lambda _child, _state: (_ for _ in ()).throw(RuntimeError("restore failed")),
    )
    windows = native_display.WindowsNativeDisplay()
    windows._embedded[123] = state  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="restore failed"):
        windows.restore(NativeWindowReference(value=123))

    assert windows._embedded[123] is state


def test_native_embed_retains_snapshot_when_rollback_fails(monkeypatch) -> None:
    from toqraq.core.preview import NativeWindowReference
    from toqraq.platforms.windows import native_display

    state = object()
    monkeypatch.setattr(native_display.dpi, "ensure_dpi_awareness", lambda: None)
    monkeypatch.setattr(native_display.native, "is_window", lambda _window: True)
    monkeypatch.setattr(native_display.embedder, "snapshot", lambda _window: state)
    monkeypatch.setattr(
        native_display.embedder,
        "embed",
        lambda _child, _host: (_ for _ in ()).throw(RuntimeError("embed failed")),
    )
    monkeypatch.setattr(
        native_display.embedder,
        "restore",
        lambda _child, _state: (_ for _ in ()).throw(RuntimeError("rollback failed")),
    )
    windows = native_display.WindowsNativeDisplay()

    with pytest.raises(RuntimeError, match="rollback failed"):
        windows.attach(NativeWindowReference(value=123), NativeWindowReference(value=456))

    assert windows._embedded[123] is state


def test_embed_assigns_native_host_owner(monkeypatch) -> None:
    """Preparation delegates z-order and minimization to Windows ownership."""
    from toqraq.platforms.windows import embedder

    owners: list[tuple[int, int]] = []
    monkeypatch.setattr(embedder, "_set_owner", lambda child, host: owners.append((child, host)))
    monkeypatch.setattr(embedder.native, "get_window_long", lambda _child, _index: 0)
    monkeypatch.setattr(embedder.native, "set_window_long", lambda *_args: None)
    monkeypatch.setattr(embedder.native, "set_window_pos", lambda *_args: None)

    embedder.embed(20, 10)

    assert owners == [(20, 10)]


def test_follow_clips_game_window_to_host_client_area(monkeypatch) -> None:
    from toqraq.core.geometry import Rect
    from toqraq.platforms.windows import embedder

    positions: list[tuple[int, int, tuple[int, int, int, int], int]] = []
    regions: list[tuple[int, int, int, int]] = []
    assigned: list[tuple[int, int]] = []
    monkeypatch.setattr(embedder.native, "is_window", lambda _handle: True)
    monkeypatch.setattr(
        embedder.native,
        "set_window_pos",
        lambda *args: positions.append(args),
    )
    monkeypatch.setattr(embedder.native, "client_to_screen", lambda _host, _point: (100, 100))
    monkeypatch.setattr(
        embedder.native,
        "get_client_rect",
        lambda _host: (0, 0, 100, 100),
    )

    def create_region(rect: tuple[int, int, int, int]) -> int:
        regions.append(rect)
        return 303

    monkeypatch.setattr(embedder.native, "create_rect_region", create_region)
    monkeypatch.setattr(
        embedder.native,
        "set_window_region",
        lambda child, region: assigned.append((child, region)),
    )

    embedder.follow(20, Rect(80, 90, 100, 100), host=10)

    assert positions == [(20, 0, (80, 90, 100, 100), embedder._POS_FLAGS)]
    assert regions == [(20, 10, 100, 100)]
    assert assigned == [(20, 303)]
