"""Pure lexical validation shared by engine and runtime path values."""

from __future__ import annotations

import os
from pathlib import Path


def require_absolute_normalized_path(value: Path, label: str) -> Path:
    """Return one lexical absolute normalized path without filesystem access."""
    if not isinstance(value, Path) or value != Path(os.path.abspath(value)):
        raise ValueError(f"{label} must be absolute and normalized")
    return value
