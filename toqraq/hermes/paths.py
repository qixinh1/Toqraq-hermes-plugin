"""Filesystem locations for Toqraq-managed state."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def hermes_home() -> Path:
    r"""Return the Hermes home directory.

    Returns:
        ``HERMES_HOME`` when set, otherwise the platform default
        (``%LOCALAPPDATA%\hermes`` on Windows, ``~/.hermes`` elsewhere).
    """
    env = os.environ.get("HERMES_HOME")
    if env:
        selected = Path(env)
        if not selected.is_absolute():
            raise ValueError("HERMES_HOME must be an absolute path")
        return Path(os.path.abspath(selected))
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(os.path.abspath(Path(local) / "hermes"))
    return Path(os.path.abspath(Path.home() / ".hermes"))


def component_store_dir() -> Path:
    """Return the isolated root for all Toqraq-managed components."""
    return hermes_home() / "toqraq"
