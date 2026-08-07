"""Owned resumable package file operations for component downloads."""

from __future__ import annotations

import hashlib
import os
import stat
from contextlib import suppress
from pathlib import Path
from typing import Protocol

from .file_mode import restrict_component_file
from .paths import is_link_or_reparse


class DigestState(Protocol):
    """SHA-256 operations used while a package is streamed."""

    def update(self, content: bytes) -> None:
        """Add content to this digest."""
        ...

    def hexdigest(self) -> str:
        """Return the current lowercase digest."""
        ...


def new_digest() -> DigestState:
    """Create an empty SHA-256 state."""
    return hashlib.sha256()


def open_partial(path: Path, maximum_bytes: int) -> int:
    """Open one owned partial file without following or mutating links."""
    flags = os.O_RDWR | os.O_CREAT
    flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        restrict_component_file(descriptor)
        descriptor_info = os.fstat(descriptor)
        path_info = os.lstat(path)
        if (
            not stat.S_ISREG(descriptor_info.st_mode)
            or descriptor_info.st_nlink != 1
            or is_link_or_reparse(path_info)
            or (descriptor_info.st_dev, descriptor_info.st_ino)
            != (path_info.st_dev, path_info.st_ino)
            or not 0 <= descriptor_info.st_size <= maximum_bytes
        ):
            raise ValueError("component partial file is not privately owned")
        return descriptor
    except BaseException:
        with suppress(OSError):
            os.close(descriptor)
        raise


def hash_partial(
    descriptor: int,
    maximum_bytes: int,
    chunk_bytes: int,
) -> tuple[int, DigestState]:
    """Hash every retained byte before a range request appends to it."""
    info = os.fstat(descriptor)
    if not 0 <= info.st_size <= maximum_bytes:
        raise ValueError("component partial file has an invalid size")
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = new_digest()
    copied = 0
    while chunk := os.read(descriptor, chunk_bytes):
        copied += len(chunk)
        if copied > info.st_size:
            raise ValueError("component partial file changed while hashing")
        digest.update(chunk)
    after = os.fstat(descriptor)
    if copied != info.st_size or (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise ValueError("component partial file changed while hashing")
    return copied, digest


def reset_partial(descriptor: int) -> None:
    """Discard bytes that cannot be resumed into the certified package."""
    os.ftruncate(descriptor, 0)
    os.lseek(descriptor, 0, os.SEEK_SET)
    os.fsync(descriptor)


def write_all(descriptor: int, content: bytes) -> None:
    """Append a complete response chunk despite partial OS writes."""
    offset = 0
    while offset < len(content):
        written = os.write(descriptor, content[offset:])
        if written <= 0:
            raise OSError("component download write made no progress")
        offset += written


def unlink_download_cache(path: Path, downloads_root: Path) -> bool:
    """Unlink one exact cache file without following or recursively deleting it."""
    absolute = Path(os.path.abspath(path))
    expected_parent = downloads_root.resolve(strict=True)
    if absolute.parent.resolve(strict=True) != expected_parent:
        raise OSError("component download cleanup target is outside downloads")
    try:
        info = os.lstat(absolute)
    except FileNotFoundError:
        return False
    if stat.S_ISDIR(info.st_mode) and not is_link_or_reparse(info):
        raise OSError("component download cleanup target is a directory")
    absolute.unlink()
    return True
