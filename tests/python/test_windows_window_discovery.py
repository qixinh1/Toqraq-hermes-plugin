"""Bounded Windows native-preview discovery tests."""

from __future__ import annotations

from collections.abc import Callable

from toqraq.core.errors import PlatformOperationError
from toqraq.platforms.windows import window_discovery


def test_windows_discovery_filters_pid_visibility_and_empty_clients(monkeypatch) -> None:
    """Only usable visible clients owned by the exact PID are returned."""
    handles = (1, 2, 3, 4)

    def enumerate_windows(visitor: Callable[[int], bool]) -> None:
        for handle in handles:
            assert visitor(handle)

    monkeypatch.setattr(window_discovery.native, "enumerate_windows", enumerate_windows)
    monkeypatch.setattr(window_discovery.native, "is_window_visible", lambda handle: handle != 1)
    monkeypatch.setattr(
        window_discovery.native,
        "get_window_process_id",
        lambda handle: 42 if handle != 2 else 99,
    )
    monkeypatch.setattr(
        window_discovery.native,
        "get_client_rect",
        lambda handle: (0, 0, 0, 10) if handle == 3 else (0, 0, 960, 540),
    )

    candidates = window_discovery.WindowsNativeWindowDiscovery().for_process(42)
    assert tuple(candidate.window.value for candidate in candidates) == (4,)
    assert candidates[0].client_size.width == 960


def test_windows_discovery_keeps_only_the_largest_bounded_candidates(monkeypatch) -> None:
    """Enumeration work cannot grow retained window state without a bound."""
    handles = tuple(range(1, 25))

    def enumerate_windows(visitor: Callable[[int], bool]) -> None:
        for handle in handles:
            assert visitor(handle)

    monkeypatch.setattr(window_discovery.native, "enumerate_windows", enumerate_windows)
    monkeypatch.setattr(window_discovery.native, "is_window_visible", lambda _handle: True)
    monkeypatch.setattr(window_discovery.native, "get_window_process_id", lambda _handle: 42)
    monkeypatch.setattr(
        window_discovery.native,
        "get_client_rect",
        lambda handle: (0, 0, handle, 10),
    )

    candidates = window_discovery.WindowsNativeWindowDiscovery().for_process(42)
    assert len(candidates) == 16
    assert tuple(candidate.window.value for candidate in candidates) == tuple(range(24, 8, -1))


def test_windows_discovery_contains_per_window_destruction_races(monkeypatch) -> None:
    """A disappearing foreign window does not invalidate the whole snapshot."""
    monkeypatch.setattr(
        window_discovery.native,
        "enumerate_windows",
        lambda visitor: [visitor(handle) for handle in (1, 2)],
    )
    monkeypatch.setattr(window_discovery.native, "is_window_visible", lambda _handle: True)

    def process_id(handle: int) -> int:
        if handle == 1:
            raise PlatformOperationError(details={"reason": "window_destroyed"})
        return 42

    monkeypatch.setattr(window_discovery.native, "get_window_process_id", process_id)
    monkeypatch.setattr(window_discovery.native, "get_client_rect", lambda _handle: (0, 0, 1, 1))

    candidates = window_discovery.WindowsNativeWindowDiscovery().for_process(42)
    assert tuple(candidate.window.value for candidate in candidates) == (2,)
