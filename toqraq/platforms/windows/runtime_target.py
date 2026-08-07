"""Canonical runtime-target identity for the Windows composition root."""

from __future__ import annotations

import sysconfig
from types import MappingProxyType

from ...core.errors import UnsupportedPlatformError
from ...core.runtime import HostRuntimeTarget

WINDOWS_RUNTIME_PLATFORM = "windows"
_ARCHITECTURES = MappingProxyType(
    {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "win-amd64": "x86_64",
        "arm64": "arm64",
        "aarch64": "arm64",
        "win-arm64": "arm64",
    }
)


def windows_runtime_target(machine: str | None = None) -> HostRuntimeTarget:
    """Return the exact catalog identity for one supported Windows host."""
    # GUI-launched Windows processes may omit PROCESSOR_ARCHITECTURE, which
    # makes platform.machine() return an empty string. The interpreter's build
    # tag is independent of that inherited environment and matches the runtime
    # that will load Toqraq's native adapters.
    reported = sysconfig.get_platform() if machine is None else machine
    if not isinstance(reported, str):
        raise ValueError("Windows machine identity is invalid")
    architecture = _ARCHITECTURES.get(reported.casefold())
    if architecture is None:
        raise UnsupportedPlatformError(
            parameters={"platform": WINDOWS_RUNTIME_PLATFORM},
            details={"reason": "architecture_unsupported"},
        )
    return HostRuntimeTarget(
        platform=WINDOWS_RUNTIME_PLATFORM,
        architecture=architecture,
    )
