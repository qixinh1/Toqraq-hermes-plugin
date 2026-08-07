"""Windows host identity tests for exact runtime-catalog filtering."""

from __future__ import annotations

import pytest
import toqraq.platforms.windows.runtime_target as runtime_target_module
from toqraq.core.errors import UnsupportedPlatformError
from toqraq.core.runtime import HostRuntimeTarget
from toqraq.platforms.windows.runtime_target import windows_runtime_target


@pytest.mark.parametrize("reported", ["AMD64", "amd64", "x86_64"])
def test_x86_64_aliases_have_one_catalog_identity(reported: str) -> None:
    """Windows and Python aliases cannot create separate runtime choices."""
    assert windows_runtime_target(reported) == HostRuntimeTarget(
        platform="windows",
        architecture="x86_64",
    )


@pytest.mark.parametrize("reported", ["ARM64", "arm64", "aarch64"])
def test_arm64_aliases_have_one_catalog_identity(reported: str) -> None:
    """Native ARM64 hosts select only certified ARM64 releases."""
    assert windows_runtime_target(reported) == HostRuntimeTarget(
        platform="windows",
        architecture="arm64",
    )


def test_unknown_windows_architecture_is_a_typed_unsupported_host() -> None:
    """An unknown architecture never falls back to an x86 runtime."""
    with pytest.raises(UnsupportedPlatformError) as captured:
        windows_runtime_target("x86")
    assert captured.value.parameters == {"platform": "windows"}
    assert captured.value.details == {"reason": "architecture_unsupported"}


@pytest.mark.parametrize(
    ("runtime_tag", "architecture"),
    [("win-amd64", "x86_64"), ("win-arm64", "arm64")],
)
def test_default_identity_uses_the_interpreter_tag_without_processor_environment(
    monkeypatch: pytest.MonkeyPatch,
    runtime_tag: str,
    architecture: str,
) -> None:
    """Desktop startup does not depend on an optional inherited Windows variable."""
    monkeypatch.delenv("PROCESSOR_ARCHITECTURE", raising=False)
    monkeypatch.delenv("PROCESSOR_ARCHITEW6432", raising=False)
    monkeypatch.setattr(runtime_target_module.sysconfig, "get_platform", lambda: runtime_tag)

    assert windows_runtime_target() == HostRuntimeTarget(
        platform="windows",
        architecture=architecture,
    )
