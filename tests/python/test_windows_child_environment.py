"""Closed Windows managed-engine environment projection tests."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
from toqraq.core.errors import PlatformOperationError
from toqraq.platforms.windows.child_environment import (
    WINDOWS_APP_DATA_ENVIRONMENT,
    WINDOWS_SYSTEM_ROOT_ENVIRONMENT,
    windows_managed_child_environment,
)
from toqraq.services import container as container_module


class _ObservedEnvironment(Mapping[str, object]):
    """Expose which host values a projection actually reads."""

    def __init__(self, values: dict[str, object]) -> None:
        self._values = values
        self.read_names: list[str] = []

    def __getitem__(self, key: str) -> object:
        self.read_names.append(key)
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def test_projection_has_only_exact_allowlist_and_managed_appdata(tmp_path: Path) -> None:
    """A reviewed projection neither creates nor copies unrelated parent state."""
    managed_root = tmp_path / "hermes-home" / "toqraq"
    system_root = tmp_path / "windows"

    environment = windows_managed_child_environment(
        managed_root,
        {
            "SystemRoot": str(system_root),
            "PATH": "C:\\unrelated",
            "MODEL_API_KEY": "secret",
        },
    )

    assert tuple((item.name, item.value) for item in environment.variables) == (
        (WINDOWS_SYSTEM_ROOT_ENVIRONMENT, str(system_root)),
        (WINDOWS_APP_DATA_ENVIRONMENT, str(managed_root / "appdata")),
    )
    assert not (managed_root / "appdata").exists()


@pytest.mark.parametrize(
    "parent_environment",
    [
        {},
        {"SYSTEMROOT": "relative"},
        {"SYSTEMROOT": "", "SystemRoot": "C:\\Windows"},
    ],
)
def test_missing_or_invalid_system_root_is_a_typed_failure(
    tmp_path: Path,
    parent_environment: dict[str, object],
) -> None:
    """A launch never guesses a system directory from malformed host state."""
    with pytest.raises(PlatformOperationError) as captured:
        windows_managed_child_environment(tmp_path / "toqraq", parent_environment)

    expected_reason = "system_root_missing" if not parent_environment else "system_root_invalid"
    assert captured.value.parameters == {"operation": "construct_child_environment"}
    assert captured.value.details == {"reason": expected_reason}


def test_managed_root_must_be_an_absolute_normalized_path() -> None:
    """The private application-data location cannot resolve from a working directory."""
    with pytest.raises(ValueError, match="managed root must be absolute and normalized"):
        windows_managed_child_environment(Path("relative"), {"SYSTEMROOT": "C:\\Windows"})


def test_default_projection_does_not_leak_parent_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The platform reads SystemRoot but does not inherit the source mapping."""
    monkeypatch.setenv("SYSTEMROOT", str(tmp_path / "windows"))
    monkeypatch.setenv("TOQRAQ_PARENT_SENTINEL", "must-not-reach-child")

    environment = windows_managed_child_environment(tmp_path / "toqraq")

    assert {item.name for item in environment.variables} == {
        WINDOWS_SYSTEM_ROOT_ENVIRONMENT,
        WINDOWS_APP_DATA_ENVIRONMENT,
    }


def test_projection_reads_only_the_system_root_value(tmp_path: Path) -> None:
    """Sensitive parent values are neither copied nor read while building the projection."""
    source = _ObservedEnvironment(
        {
            "SYSTEMROOT": str(tmp_path / "windows"),
            "MODEL_API_KEY": object(),
        }
    )

    windows_managed_child_environment(tmp_path / "toqraq", source)

    assert source.read_names == ["SYSTEMROOT"]


def test_non_windows_composition_stays_empty_and_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Unsupported hosts do not construct or expose a Windows child environment."""
    monkeypatch.setattr(container_module.sys, "platform", "linux")

    _host, _launcher, display, environment = container_module._host_process_services(tmp_path)

    assert display is None
    assert environment.variables == ()
