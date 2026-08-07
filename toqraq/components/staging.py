"""Confined idempotent cleanup for component staging content."""

from __future__ import annotations

import logging
import os
import shutil
import stat
from pathlib import Path

from .paths import is_link_or_reparse

logger = logging.getLogger(__name__)


def discard_component_staging(
    path: Path,
    staging_root: Path,
    identity_key: str,
) -> bool:
    """Remove one identity-owned staging child without escaping its root."""
    try:
        absolute = Path(os.path.abspath(path))
        expected_parent = staging_root.resolve(strict=True)
        if absolute.parent.resolve(strict=True) != expected_parent:
            raise OSError("component cleanup target is outside staging")
        if not absolute.name.startswith(identity_key + "."):
            raise OSError("component cleanup target has another identity")
        try:
            info = os.lstat(absolute)
        except FileNotFoundError:
            return True
        if is_link_or_reparse(info) or not stat.S_ISDIR(info.st_mode):
            absolute.unlink()
        else:
            shutil.rmtree(absolute)
        return True
    except OSError as exc:
        logger.warning(
            "component cleanup deferred identity_key=%s exception_type=%s",
            identity_key,
            type(exc).__name__,
        )
        return False
