"""Pure structural validation for bounded PNG transport payloads."""

from __future__ import annotations

import binascii
import struct

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_PNG_BYTES = 64 << 20
MAX_PNG_DIMENSION = 32_768
MAX_PNG_PIXELS = 8192 * 8192
_IHDR_LENGTH = 13
_IHDR_TYPE = b"IHDR"
_MINIMUM_HEADER_BYTES = 33
_BIT_DEPTHS_BY_COLOR_TYPE = {
    0: frozenset({1, 2, 4, 8, 16}),
    2: frozenset({8, 16}),
    3: frozenset({1, 2, 4, 8}),
    4: frozenset({8, 16}),
    6: frozenset({8, 16}),
}


def png_dimensions(data: bytes) -> tuple[int, int]:
    """Return dimensions from a structurally valid, bounded PNG header.

    Args:
        data: Complete PNG payload.

    Returns:
        ``(width, height)`` from the mandatory first IHDR chunk.

    Raises:
        ValueError: If the payload, header, or decoded surface is invalid.
    """
    if not isinstance(data, bytes) or not data.startswith(PNG_SIGNATURE):
        raise ValueError("PNG payload is not a PNG image")
    if len(data) > MAX_PNG_BYTES:
        raise ValueError(f"PNG payload exceeds {MAX_PNG_BYTES} bytes")
    if len(data) < _MINIMUM_HEADER_BYTES:
        raise ValueError("PNG header is truncated")
    (
        chunk_length,
        chunk_type,
        width,
        height,
        bit_depth,
        color_type,
        compression,
        filtering,
        interlace,
    ) = struct.unpack_from(">I4sII5B", data, 8)
    if chunk_length != _IHDR_LENGTH or chunk_type != _IHDR_TYPE:
        raise ValueError("PNG does not begin with an IHDR chunk")
    expected_crc = struct.unpack_from(">I", data, 29)[0]
    actual_crc = binascii.crc32(data[12:29]) & 0xFFFFFFFF
    if expected_crc != actual_crc:
        raise ValueError("PNG IHDR checksum is invalid")
    if (
        bit_depth not in _BIT_DEPTHS_BY_COLOR_TYPE.get(color_type, ())
        or compression != 0
        or filtering != 0
        or interlace not in (0, 1)
    ):
        raise ValueError("PNG IHDR fields are invalid")
    if (
        width == 0
        or height == 0
        or width > MAX_PNG_DIMENSION
        or height > MAX_PNG_DIMENSION
        or width * height > MAX_PNG_PIXELS
    ):
        raise ValueError("PNG dimensions are outside the transport bounds")
    return width, height
