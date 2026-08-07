"""Cross-platform collection contract for Windows process modules."""

from __future__ import annotations

import ctypes
import importlib
from pathlib import Path

import pytest
from toqraq.platforms.windows import process_windows


def test_window_callback_type_is_bound_only_when_adapter_is_constructed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Linux collection must not require the Windows-only WINFUNCTYPE symbol."""
    monkeypatch.delattr(ctypes, "WINFUNCTYPE", raising=False)

    importlib.reload(process_windows)


def test_process_creation_uses_only_atomic_job_list_assignment() -> None:
    """Process creation assigns the Job Object in its creation attribute list."""
    source_root = Path(__file__).parents[2] / "toqraq" / "platforms" / "windows"
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_root.glob("process*.py"))

    assert "CREATE_SUSPENDED" not in source
    assert "AssignProcessToJobObject" not in source
    assert "ResumeThread" not in source
