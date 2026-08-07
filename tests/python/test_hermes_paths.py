"""Managed root ownership and environment validation tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from toqraq.hermes.paths import component_store_dir, hermes_home


def test_explicit_hermes_home_is_absolute_normalized_and_owns_component_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = tmp_path / "nested" / ".." / "profile"
    monkeypatch.setenv("HERMES_HOME", str(selected))

    expected = Path(os.path.abspath(selected))
    assert hermes_home() == expected
    assert component_store_dir() == expected / "toqraq"


def test_relative_hermes_home_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_HOME", "relative/profile")

    with pytest.raises(ValueError, match="absolute"):
        hermes_home()
