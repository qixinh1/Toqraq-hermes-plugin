"""Bounded unambiguous JSON-object reads for component metadata files."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any


def read_bounded_json_object(path: Path, *, maximum_bytes: int) -> bytes:
    """Read one regular file and reject ambiguous or non-standard JSON."""
    if isinstance(maximum_bytes, bool) or not isinstance(maximum_bytes, int) or maximum_bytes <= 0:
        raise ValueError("JSON byte limit must be a positive integer")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > maximum_bytes:
            raise ValueError("JSON source is not a bounded regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read(maximum_bytes + 1)
        if len(content) > maximum_bytes:
            raise ValueError("JSON source is too large")
    finally:
        os.close(descriptor)
    value: Any = json.loads(
        content.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_reject_json_constant,
    )
    if not isinstance(value, dict):
        raise TypeError("JSON root must be an object")
    return content


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a JSON object while rejecting duplicate keys."""
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("JSON object contains a duplicate key")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> None:
    """Reject non-standard JSON numeric constants."""
    raise ValueError(f"non-standard JSON constant is forbidden: {value}")
