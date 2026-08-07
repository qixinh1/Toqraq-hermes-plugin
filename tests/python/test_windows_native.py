"""Contracts for the standard-library Win32 binding."""

from __future__ import annotations

import ctypes
import sys

import pytest
from toqraq.core.errors import PlatformOperationError

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows adapter only")


def test_dpi_awareness_is_attempted_once(monkeypatch) -> None:
    from toqraq.platforms.windows import dpi

    calls: list[None] = []
    monkeypatch.setattr(dpi, "_attempted", False)
    monkeypatch.setattr(dpi.native, "enable_dpi_awareness", lambda: calls.append(None))

    dpi.ensure_dpi_awareness()
    dpi.ensure_dpi_awareness()

    assert calls == [None]


def test_dpi_awareness_accepts_the_policy_owned_by_hermes(monkeypatch) -> None:
    from toqraq.platforms.windows import native

    def already_set(_context) -> int:
        ctypes.set_last_error(native._ERROR_ACCESS_DENIED)
        return 0

    monkeypatch.setattr(native, "_set_process_dpi_awareness_context", already_set)

    native.enable_dpi_awareness()


def test_dpi_awareness_reports_current_api_failure(monkeypatch) -> None:
    from toqraq.platforms.windows import native

    def fail(_context) -> int:
        ctypes.set_last_error(87)
        return 0

    monkeypatch.setattr(native, "_set_process_dpi_awareness_context", fail)

    with pytest.raises(PlatformOperationError) as caught:
        native.enable_dpi_awareness()
    assert caught.value.parameters["operation"] == "SetProcessDpiAwarenessContext"
    assert caught.value.details == {"reason": "windows_api_failed", "native_error": 87}


def test_enumeration_treats_visitor_stop_as_success(monkeypatch) -> None:
    """EnumWindows returns zero both for failure and an intentional stop."""
    from toqraq.platforms.windows import native

    def stop_after_first(callback, parameter) -> int:
        assert parameter == 0
        assert callback(101, parameter) == 0
        return 0

    monkeypatch.setattr(native, "_enum_windows", stop_after_first)

    native.enumerate_windows(lambda handle: handle != 101)


def test_enumeration_propagates_callback_failure(monkeypatch) -> None:
    """ctypes callbacks cannot swallow failures raised by Python visitors."""
    from toqraq.platforms.windows import native

    class VisitorError(RuntimeError):
        pass

    def invoke(callback, parameter) -> int:
        assert callback(101, parameter) == 0
        return 0

    def fail(_handle: int) -> bool:
        raise VisitorError("visitor failed")

    monkeypatch.setattr(native, "_enum_windows", invoke)

    with pytest.raises(VisitorError, match="visitor failed"):
        native.enumerate_windows(fail)


def test_enumeration_reports_native_failure(monkeypatch) -> None:
    from toqraq.platforms.windows import native

    def fail(_callback, _parameter) -> int:
        ctypes.set_last_error(5)
        return 0

    monkeypatch.setattr(native, "_enum_windows", fail)

    with pytest.raises(PlatformOperationError) as caught:
        native.enumerate_windows(lambda _handle: True)
    assert caught.value.parameters["operation"] == "EnumWindows"
    assert caught.value.details["native_error"] == 5


def test_zero_window_long_is_not_mistaken_for_failure(monkeypatch) -> None:
    from toqraq.platforms.windows import native

    def return_zero(_handle, _index) -> int:
        return 0

    monkeypatch.setattr(native, "_get_window_long", return_zero)

    assert native.get_window_long(101, native.GWL_EXSTYLE) == 0


def test_window_long_failure_preserves_windows_error(monkeypatch) -> None:
    from toqraq.platforms.windows import native

    def fail(_handle, _index) -> int:
        ctypes.set_last_error(1400)
        return 0

    monkeypatch.setattr(native, "_get_window_long", fail)

    with pytest.raises(PlatformOperationError) as caught:
        native.get_window_long(101, native.GWL_STYLE)
    assert caught.value.parameters["operation"] == "GetWindowLongW"
    assert caught.value.details["native_error"] == 1400


def test_failed_region_assignment_reclaims_caller_owned_region(monkeypatch) -> None:
    """Windows owns an HRGN only after SetWindowRgn succeeds."""
    from toqraq.platforms.windows import native

    deleted: list[int] = []

    def fail(_window, _region, _redraw) -> int:
        ctypes.set_last_error(1400)
        return 0

    monkeypatch.setattr(native, "_set_window_region", fail)
    monkeypatch.setattr(native, "_delete_object", lambda region: deleted.append(region) or 1)

    with pytest.raises(PlatformOperationError) as caught:
        native.set_window_region(101, 202)
    assert caught.value.parameters["operation"] == "SetWindowRgn"
    assert caught.value.details["native_error"] == 1400

    assert deleted == [202]


def test_successful_region_assignment_transfers_ownership(monkeypatch) -> None:
    from toqraq.platforms.windows import native

    deleted: list[int] = []
    monkeypatch.setattr(native, "_set_window_region", lambda *_args: 1)
    monkeypatch.setattr(native, "_delete_object", lambda region: deleted.append(region) or 1)

    native.set_window_region(101, 202)

    assert deleted == []
