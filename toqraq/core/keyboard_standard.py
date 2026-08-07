"""W3C keyboard identities supported by the common input contract."""

from __future__ import annotations

import unicodedata

# This is the required physical-key set in the 22 April 2025 W3C
# KeyboardEvent.code Recommendation, excluding ``Unidentified``. Toqraq uses
# ``None`` when a physical identity is unavailable; accepting ``Unidentified``
# would make a synthetic input look mappable when it is not.
W3C_REQUIRED_PHYSICAL_KEY_CODES: frozenset[str] = frozenset(
    {
        "AltLeft",
        "AltRight",
        "ArrowDown",
        "ArrowLeft",
        "ArrowRight",
        "ArrowUp",
        "Backquote",
        "Backslash",
        "Backspace",
        "BracketLeft",
        "BracketRight",
        "CapsLock",
        "Comma",
        "ContextMenu",
        "ControlLeft",
        "ControlRight",
        "Convert",
        "Delete",
        "End",
        "Enter",
        "Equal",
        "Escape",
        "Help",
        "Home",
        "Insert",
        "IntlBackslash",
        "IntlRo",
        "IntlYen",
        "KanaMode",
        "MetaLeft",
        "MetaRight",
        "Minus",
        "NonConvert",
        "NumLock",
        "NumpadAdd",
        "NumpadDecimal",
        "NumpadDivide",
        "NumpadEnter",
        "NumpadMultiply",
        "NumpadSubtract",
        "PageDown",
        "PageUp",
        "Pause",
        "Period",
        "PrintScreen",
        "Quote",
        "ScrollLock",
        "Semicolon",
        "ShiftLeft",
        "ShiftRight",
        "Slash",
        "Space",
        "Tab",
        *(f"Digit{index}" for index in range(10)),
        *(f"F{index}" for index in range(1, 13)),
        *(f"Key{letter}" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        *(f"Numpad{index}" for index in range(10)),
    }
)

MAX_LOGICAL_KEY_BYTES = 64

# Named W3C key values required for the same cross-engine gameplay baseline.
# Character-producing keys use the Unicode key-string algorithm below instead.
W3C_BASELINE_NAMED_LOGICAL_KEYS: frozenset[str] = frozenset(
    {
        "Alt",
        "AltGraph",
        "ArrowDown",
        "ArrowLeft",
        "ArrowRight",
        "ArrowUp",
        "Backspace",
        "CapsLock",
        "ContextMenu",
        "Control",
        "Convert",
        "Dead",
        "Delete",
        "End",
        "Enter",
        "Escape",
        "Help",
        "Home",
        "Insert",
        "KanaMode",
        "Meta",
        "NonConvert",
        "NumLock",
        "PageDown",
        "PageUp",
        "Pause",
        "PrintScreen",
        "ScrollLock",
        "Shift",
        "Tab",
        *(f"F{index}" for index in range(1, 13)),
    }
)


def validate_physical_key_code(value: str) -> str:
    """Return one supported W3C ``KeyboardEvent.code`` value or raise."""
    if not isinstance(value, str) or value not in W3C_REQUIRED_PHYSICAL_KEY_CODES:
        raise ValueError("physical key code is not in the common W3C baseline")
    return value


def validate_logical_key(value: str) -> str:
    """Return one baseline named key or NFC W3C Unicode key string."""
    if not isinstance(value, str):
        raise ValueError("logical key is invalid")
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise ValueError("logical key is not valid UTF-8") from error
    if not encoded or len(encoded) > MAX_LOGICAL_KEY_BYTES:
        raise ValueError("logical key exceeds its UTF-8 byte bound")
    if value in W3C_BASELINE_NAMED_LOGICAL_KEYS:
        return value
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError("logical key string must use NFC")

    base_seen = False
    combining_seen = False
    for character in value:
        category = unicodedata.category(character)
        is_combining = category == "Mc" or unicodedata.combining(character) != 0
        if is_combining:
            combining_seen = True
            continue
        if category == "Cc" or base_seen or combining_seen:
            raise ValueError("logical key is not a W3C key string")
        base_seen = True
    return value
