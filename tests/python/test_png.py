"""Tests for bounded structural PNG validation."""

from __future__ import annotations

import struct

import pytest
from toqraq.core.png import PNG_SIGNATURE, png_dimensions

from _png_support import png_header


def test_reads_ihdr_dimensions() -> None:
    assert png_dimensions(png_header(640, 360)) == (640, 360)


@pytest.mark.parametrize(
    "payload",
    [
        b"not-png",
        PNG_SIGNATURE,
        PNG_SIGNATURE + struct.pack(">I4sII", 12, b"IHDR", 1, 1),
        PNG_SIGNATURE + struct.pack(">I4sII", 13, b"IDAT", 1, 1),
        png_header(1, 1)[:-1] + b"\x00",
        png_header(0, 1),
        png_header(8193, 8192),
    ],
)
def test_rejects_invalid_or_oversized_headers(payload: bytes) -> None:
    with pytest.raises(ValueError):
        png_dimensions(payload)
