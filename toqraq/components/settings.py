"""Validated production policy for the isolated managed-component subsystem."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .archive import ZipExtractionPolicy
from .content_policy import ComponentContentPolicy
from .download_models import ComponentDownloadPolicy
from .lock import ComponentLockPolicy
from .space import ComponentSpacePolicy

_MEBIBYTE = 1 << 20
_GIBIBYTE = 1 << 30
_PLUGIN_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")

DEFAULT_COMPONENT_MAX_ENTRIES = 200_000
DEFAULT_COMPONENT_MAX_FILE_BYTES = 64 * _GIBIBYTE
DEFAULT_COMPONENT_MAX_TREE_BYTES = 256 * _GIBIBYTE
DEFAULT_COMPONENT_MAX_PATH_DEPTH = 64
DEFAULT_COMPONENT_MAX_PATH_CHARACTERS = 1_024
DEFAULT_COMPONENT_IO_CHUNK_BYTES = _MEBIBYTE
DEFAULT_COMPONENT_CHECKPOINT_BYTES = 16 * _MEBIBYTE
DEFAULT_COMPONENT_LOCK_TIMEOUT_SECONDS = 120.0
DEFAULT_COMPONENT_LOCK_POLL_SECONDS = 0.1
DEFAULT_COMPONENT_IO_TIMEOUT_SECONDS = 30.0
DEFAULT_COMPONENT_IDLE_TIMEOUT_SECONDS = 120.0
DEFAULT_COMPONENT_TOTAL_TIMEOUT_SECONDS = 86_400.0
DEFAULT_COMPONENT_MAX_REDIRECTS = 5
DEFAULT_COMPONENT_SPACE_RESERVE_BYTES = 512 * _MEBIBYTE


@dataclass(frozen=True, slots=True)
class ComponentSettings:
    """Complete injected product policy for one component service graph."""

    lock: ComponentLockPolicy
    download: ComponentDownloadPolicy
    zip: ZipExtractionPolicy
    space: ComponentSpacePolicy


def component_settings(plugin_version: str) -> ComponentSettings:
    """Build production policy with one versioned bounded network identity."""
    if not isinstance(plugin_version, str) or _PLUGIN_VERSION.fullmatch(plugin_version) is None:
        raise ValueError("component policy requires a bounded plugin version")
    content = ComponentContentPolicy(
        max_entries=DEFAULT_COMPONENT_MAX_ENTRIES,
        max_file_bytes=DEFAULT_COMPONENT_MAX_FILE_BYTES,
        max_total_bytes=DEFAULT_COMPONENT_MAX_TREE_BYTES,
        max_path_depth=DEFAULT_COMPONENT_MAX_PATH_DEPTH,
        max_path_characters=DEFAULT_COMPONENT_MAX_PATH_CHARACTERS,
        read_chunk_bytes=DEFAULT_COMPONENT_IO_CHUNK_BYTES,
    )
    return ComponentSettings(
        lock=ComponentLockPolicy(
            timeout_seconds=DEFAULT_COMPONENT_LOCK_TIMEOUT_SECONDS,
            poll_seconds=DEFAULT_COMPONENT_LOCK_POLL_SECONDS,
        ),
        download=ComponentDownloadPolicy(
            io_timeout_seconds=DEFAULT_COMPONENT_IO_TIMEOUT_SECONDS,
            idle_timeout_seconds=DEFAULT_COMPONENT_IDLE_TIMEOUT_SECONDS,
            total_timeout_seconds=DEFAULT_COMPONENT_TOTAL_TIMEOUT_SECONDS,
            chunk_bytes=DEFAULT_COMPONENT_IO_CHUNK_BYTES,
            checkpoint_bytes=DEFAULT_COMPONENT_CHECKPOINT_BYTES,
            max_redirects=DEFAULT_COMPONENT_MAX_REDIRECTS,
            user_agent=f"Toqraq/{plugin_version}",
        ),
        zip=ZipExtractionPolicy(
            content=content,
            copy_chunk_bytes=DEFAULT_COMPONENT_IO_CHUNK_BYTES,
        ),
        space=ComponentSpacePolicy(
            reserve_bytes=DEFAULT_COMPONENT_SPACE_RESERVE_BYTES,
        ),
    )
