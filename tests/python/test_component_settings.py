"""Production managed-component policy composition tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from toqraq.components.settings import (
    DEFAULT_COMPONENT_CHECKPOINT_BYTES,
    DEFAULT_COMPONENT_IDLE_TIMEOUT_SECONDS,
    DEFAULT_COMPONENT_IO_CHUNK_BYTES,
    DEFAULT_COMPONENT_IO_TIMEOUT_SECONDS,
    DEFAULT_COMPONENT_LOCK_POLL_SECONDS,
    DEFAULT_COMPONENT_LOCK_TIMEOUT_SECONDS,
    DEFAULT_COMPONENT_MAX_ENTRIES,
    DEFAULT_COMPONENT_MAX_FILE_BYTES,
    DEFAULT_COMPONENT_MAX_PATH_CHARACTERS,
    DEFAULT_COMPONENT_MAX_PATH_DEPTH,
    DEFAULT_COMPONENT_MAX_REDIRECTS,
    DEFAULT_COMPONENT_MAX_TREE_BYTES,
    DEFAULT_COMPONENT_SPACE_RESERVE_BYTES,
    DEFAULT_COMPONENT_TOTAL_TIMEOUT_SECONDS,
    component_settings,
)
from toqraq.services.component_jobs import (
    DEFAULT_ACTIVE_COMPONENT_JOBS,
    DEFAULT_COMPONENT_SHUTDOWN_SECONDS,
    DEFAULT_RETAINED_COMPONENT_JOBS,
    component_job_policy,
)


def test_production_component_policy_has_one_exact_validated_owner() -> None:
    settings = component_settings("0.1.0")

    assert (settings.lock.timeout_seconds, settings.lock.poll_seconds) == (
        DEFAULT_COMPONENT_LOCK_TIMEOUT_SECONDS,
        DEFAULT_COMPONENT_LOCK_POLL_SECONDS,
    )
    assert (
        settings.download.io_timeout_seconds,
        settings.download.idle_timeout_seconds,
        settings.download.total_timeout_seconds,
    ) == (
        DEFAULT_COMPONENT_IO_TIMEOUT_SECONDS,
        DEFAULT_COMPONENT_IDLE_TIMEOUT_SECONDS,
        DEFAULT_COMPONENT_TOTAL_TIMEOUT_SECONDS,
    )
    assert (
        settings.download.chunk_bytes,
        settings.download.checkpoint_bytes,
        settings.download.max_redirects,
        settings.download.user_agent,
    ) == (
        DEFAULT_COMPONENT_IO_CHUNK_BYTES,
        DEFAULT_COMPONENT_CHECKPOINT_BYTES,
        DEFAULT_COMPONENT_MAX_REDIRECTS,
        "Toqraq/0.1.0",
    )
    assert (
        settings.zip.content.max_entries,
        settings.zip.content.max_file_bytes,
        settings.zip.content.max_total_bytes,
        settings.zip.content.max_path_depth,
        settings.zip.content.max_path_characters,
        settings.zip.content.read_chunk_bytes,
        settings.zip.copy_chunk_bytes,
    ) == (
        DEFAULT_COMPONENT_MAX_ENTRIES,
        DEFAULT_COMPONENT_MAX_FILE_BYTES,
        DEFAULT_COMPONENT_MAX_TREE_BYTES,
        DEFAULT_COMPONENT_MAX_PATH_DEPTH,
        DEFAULT_COMPONENT_MAX_PATH_CHARACTERS,
        DEFAULT_COMPONENT_IO_CHUNK_BYTES,
        DEFAULT_COMPONENT_IO_CHUNK_BYTES,
    )
    assert settings.space.reserve_bytes == DEFAULT_COMPONENT_SPACE_RESERVE_BYTES
    with pytest.raises(FrozenInstanceError):
        settings.space = settings.space  # type: ignore[misc]


def test_production_job_policy_has_one_exact_validated_owner() -> None:
    policy = component_job_policy()
    assert (
        policy.max_active_jobs,
        policy.max_terminal_jobs,
        policy.shutdown_timeout_seconds,
    ) == (
        DEFAULT_ACTIVE_COMPONENT_JOBS,
        DEFAULT_RETAINED_COMPONENT_JOBS,
        DEFAULT_COMPONENT_SHUTDOWN_SECONDS,
    )


@pytest.mark.parametrize(
    "version",
    ["", " version", "0.1.0 ", "0/1", "x" * 65, 1, None],
)
def test_component_policy_rejects_invalid_plugin_version(version: object) -> None:
    with pytest.raises(ValueError):
        component_settings(version)  # type: ignore[arg-type]
