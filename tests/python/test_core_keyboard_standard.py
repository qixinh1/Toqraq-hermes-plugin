"""W3C keyboard identity baseline and Unicode key-string invariants."""

from __future__ import annotations

import pytest
from toqraq.core.keyboard_standard import (
    MAX_LOGICAL_KEY_BYTES,
    W3C_BASELINE_NAMED_LOGICAL_KEYS,
    W3C_REQUIRED_PHYSICAL_KEY_CODES,
    validate_logical_key,
    validate_physical_key_code,
)


def test_physical_baseline_is_exact_identified_required_w3c_set() -> None:
    assert len(W3C_REQUIRED_PHYSICAL_KEY_CODES) == 111
    assert {f"Key{letter}" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}.issubset(
        W3C_REQUIRED_PHYSICAL_KEY_CODES
    )
    assert {f"Digit{index}" for index in range(10)}.issubset(W3C_REQUIRED_PHYSICAL_KEY_CODES)
    assert {f"F{index}" for index in range(1, 13)}.issubset(W3C_REQUIRED_PHYSICAL_KEY_CODES)
    assert "IntlRo" in W3C_REQUIRED_PHYSICAL_KEY_CODES
    assert "Unidentified" not in W3C_REQUIRED_PHYSICAL_KEY_CODES
    assert "MediaPlayPause" not in W3C_REQUIRED_PHYSICAL_KEY_CODES


@pytest.mark.parametrize(
    "value",
    ("KeyW", "IntlBackslash", "NumpadMultiply", "F12"),
)
def test_physical_code_accepts_only_the_common_baseline(value: str) -> None:
    assert validate_physical_key_code(value) == value

    with pytest.raises(ValueError, match="common W3C baseline"):
        validate_physical_key_code(f"{value}Unknown")


@pytest.mark.parametrize(
    "value",
    ("a", "é", "ḍ\u0307", " ", "\u200c", "\u0301", "F12", "Dead"),
)
def test_logical_key_accepts_named_or_nfc_w3c_key_strings(value: str) -> None:
    assert validate_logical_key(value) == value


@pytest.mark.parametrize(
    ("value", "message"),
    (
        ("", "byte bound"),
        ("a" * (MAX_LOGICAL_KEY_BYTES + 1), "byte bound"),
        ("e\u0301", "NFC"),
        ("two", "W3C key string"),
        ("\t", "W3C key string"),
        ("Unidentified", "W3C key string"),
        ("\ud800", "valid UTF-8"),
    ),
)
def test_logical_key_rejects_ambiguous_or_nonconforming_values(
    value: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_logical_key(value)


def test_named_logical_baseline_contains_gameplay_navigation_and_modifiers() -> None:
    assert {
        "Alt",
        "ArrowDown",
        "Control",
        "Enter",
        "Escape",
        "Meta",
        "Shift",
        "Tab",
    }.issubset(W3C_BASELINE_NAMED_LOGICAL_KEYS)
