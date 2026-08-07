"""Closed Windows environment projection for Toqraq-managed engine processes."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from ...core.absolute_path import require_absolute_normalized_path
from ...core.errors import PlatformOperationError
from ...core.process_tree import ProcessEnvironment, ProcessEnvironmentVariable

WINDOWS_SYSTEM_ROOT_ENVIRONMENT = "SYSTEMROOT"
WINDOWS_APP_DATA_ENVIRONMENT = "APPDATA"
_TOQRAQ_APP_DATA_DIRECTORY = "appdata"
_ENVIRONMENT_OPERATION = "construct_child_environment"


def windows_managed_child_environment(
    managed_root: Path,
    parent_environment: Mapping[str, object] | None = None,
) -> ProcessEnvironment:
    """Project the sole approved Windows settings into one managed child."""
    root = require_absolute_normalized_path(managed_root, "managed root")
    source: Mapping[str, object] = os.environ if parent_environment is None else parent_environment
    system_root = _system_root(source)
    app_data = require_absolute_normalized_path(
        root / _TOQRAQ_APP_DATA_DIRECTORY,
        "managed app data directory",
    )
    return ProcessEnvironment(
        variables=(
            ProcessEnvironmentVariable(
                name=WINDOWS_SYSTEM_ROOT_ENVIRONMENT,
                value=system_root,
            ),
            ProcessEnvironmentVariable(
                name=WINDOWS_APP_DATA_ENVIRONMENT,
                value=str(app_data),
            ),
        )
    )


def _system_root(source: Mapping[str, object]) -> str:
    """Read and validate the one Windows system directory without retaining its source."""
    names = tuple(
        name for name in source if name.casefold() == WINDOWS_SYSTEM_ROOT_ENVIRONMENT.casefold()
    )
    if not names:
        raise PlatformOperationError(
            parameters={"operation": _ENVIRONMENT_OPERATION},
            details={"reason": "system_root_missing"},
        )
    values = tuple(source[name] for name in names)
    if len(values) != 1 or not isinstance(values[0], str):
        raise _invalid_system_root()
    value = values[0]
    if not value or "\0" in value:
        raise _invalid_system_root()
    try:
        return str(require_absolute_normalized_path(Path(value), "system root"))
    except ValueError as error:
        raise PlatformOperationError(
            parameters={"operation": _ENVIRONMENT_OPERATION},
            details={"reason": "system_root_invalid"},
            cause=error,
        ) from error


def _invalid_system_root() -> PlatformOperationError:
    """Return the bounded failure that keeps malformed host settings private."""
    return PlatformOperationError(
        parameters={"operation": _ENVIRONMENT_OPERATION},
        details={"reason": "system_root_invalid"},
    )
