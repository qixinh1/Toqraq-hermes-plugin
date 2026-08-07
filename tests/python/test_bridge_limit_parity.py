"""Parity tests for the common host and native Bridge resource policy."""

from __future__ import annotations

import re
from pathlib import Path

from toqraq.core.bridge import COMMON_BRIDGE_LIMITS

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
NATIVE_LIMITS = REPOSITORY_ROOT / "engine" / "godot" / "modules" / "toqraq" / "toqraq_limits.h"


def test_common_limits_equal_the_native_godot_offer() -> None:
    """The certified candidate cannot silently negotiate a different policy."""
    source = NATIVE_LIMITS.read_text(encoding="utf-8")
    assert _integer(source, "MAX_TEXT_MESSAGE_BYTES") == (
        COMMON_BRIDGE_LIMITS.max_text_message_bytes
    )
    assert _shifted_mebibytes(source, "MAX_BINARY_PAYLOAD_BYTES") == (
        COMMON_BRIDGE_LIMITS.max_binary_transfer_bytes
    )
    assert _integer(source, "MAX_IN_FLIGHT_REQUESTS") == (
        COMMON_BRIDGE_LIMITS.max_in_flight_requests
    )
    assert _integer(source, "TRANSFER_PREFIX_BYTES") == 16


def _integer(source: str, name: str) -> int:
    """Read one decimal constexpr owned by the reviewed native header."""
    match = re.search(rf"constexpr int {name} = ([0-9]+);", source)
    assert match is not None
    return int(match.group(1))


def _shifted_mebibytes(source: str, name: str) -> int:
    """Read the native `N << 20` spelling without evaluating source text."""
    match = re.search(rf"constexpr int {name} = ([0-9]+) << 20;", source)
    assert match is not None
    return int(match.group(1)) << 20
