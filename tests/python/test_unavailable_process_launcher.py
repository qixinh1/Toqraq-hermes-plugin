"""Fail-closed unsupported-host process adapter tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from toqraq.core.errors import UnsupportedPlatformError
from toqraq.core.process_tree import (
    ProcessBootstrap,
    ProcessEnvironment,
    ProcessLaunch,
)
from toqraq.platforms.unavailable import UnavailableProcessTreeLauncher


def test_unavailable_launcher_never_acquires_a_process(tmp_path: Path) -> None:
    launcher = UnavailableProcessTreeLauncher()
    command = ProcessLaunch(
        executable=tmp_path / "engine",
        arguments=(),
        working_directory=tmp_path / "project",
        environment=ProcessEnvironment(variables=()),
        bootstrap=ProcessBootstrap(payload=b"{}"),
    )

    with pytest.raises(UnsupportedPlatformError) as caught:
        launcher.launch(command)

    assert caught.value.details == {"reason": "process_launcher_unavailable"}
    launcher.close()
    launcher.close()
