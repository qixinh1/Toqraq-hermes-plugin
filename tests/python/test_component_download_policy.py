from __future__ import annotations

from dataclasses import replace

import pytest
from toqraq.components.download_models import (
    MAX_DOWNLOAD_CHUNK_BYTES,
    ComponentDownloadPolicy,
)

_VALID_POLICY = ComponentDownloadPolicy(
    io_timeout_seconds=1,
    idle_timeout_seconds=2,
    total_timeout_seconds=5,
    chunk_bytes=3,
    checkpoint_bytes=6,
    max_redirects=2,
    user_agent="toqraq-tests/1",
)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("io_timeout_seconds", 0),
        ("idle_timeout_seconds", 0.5),
        ("total_timeout_seconds", float("inf")),
        ("chunk_bytes", 0),
        ("chunk_bytes", MAX_DOWNLOAD_CHUNK_BYTES + 1),
        ("checkpoint_bytes", 2),
        ("max_redirects", -1),
        ("user_agent", "bad agent"),
    ],
)
def test_download_policy_rejects_unbounded_or_invalid_values(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        replace(_VALID_POLICY, **{field: value})
