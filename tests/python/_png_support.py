"""Canonical minimal PNG headers for frame and PNG tests."""

from __future__ import annotations

import binascii
import struct

from toqraq.core.png import PNG_SIGNATURE


def png_header(width: int, height: int, *, padding_bytes: int = 0) -> bytes:
    """Build one CRC-valid IHDR followed by optional inert test padding."""
    chunk = b"IHDR" + struct.pack(">II5B", width, height, 8, 6, 0, 0, 0)
    return (
        PNG_SIGNATURE
        + struct.pack(">I", 13)
        + chunk
        + struct.pack(">I", binascii.crc32(chunk))
        + b"x" * padding_bytes
    )
