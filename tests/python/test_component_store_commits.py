from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

import pytest
from toqraq.components import lease as component_lease
from toqraq.components import store as component_store
from toqraq.components.content import ComponentTreeCancelledError, ComponentTreeProgress
from toqraq.components.store import ComponentStoreCancelledError

from test_component_store import (
    _POLICY,
    _identity,
    _prepare,
    _publish,
    _remove,
    _store,
)


def test_tree_cancellation_becomes_stable_store_cancellation(tmp_path: Path) -> None:
    layout, store = _store(tmp_path / "toqraq")
    staging, release = _prepare(layout)
    cancellation = threading.Event()
    observed: list[ComponentTreeProgress] = []

    def cancel_after_first_chunk(value: ComponentTreeProgress) -> None:
        observed.append(value)
        if value.completed_bytes > 0:
            cancellation.set()

    with pytest.raises(ComponentStoreCancelledError) as captured:
        _publish(
            layout,
            store,
            staging,
            release,
            cancellation=cancellation,
            progress=cancel_after_first_chunk,
        )

    assert isinstance(captured.value.__cause__, ComponentTreeCancelledError)
    assert observed == [ComponentTreeProgress(0, 13), ComponentTreeProgress(4, 13)]
    assert staging.exists()
    assert not layout.component_path(release.identity).exists()


def test_cancellation_is_checked_immediately_before_publication_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, store = _store(tmp_path / "toqraq")
    staging, release = _prepare(layout)
    destination = layout.component_path(release.identity)
    cancellation = threading.Event()
    original_lexists = os.path.lexists

    def cancel_at_destination_check(path: os.PathLike[str] | str) -> bool:
        exists = original_lexists(path)
        if Path(path) == destination:
            cancellation.set()
        return exists

    monkeypatch.setattr(component_store.os.path, "lexists", cancel_at_destination_check)

    with pytest.raises(ComponentStoreCancelledError):
        _publish(
            layout,
            store,
            staging,
            release,
            cancellation=cancellation,
        )

    assert staging.exists()
    assert not destination.exists()


def test_cancellation_and_flush_failure_after_publication_return_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    layout, store = _store(tmp_path / "toqraq")
    staging, release = _prepare(layout)
    cancellation = threading.Event()

    def fail_after_commit(_path: Path) -> None:
        cancellation.set()
        raise OSError("private flush failure")

    monkeypatch.setattr(component_store, "_flush_directory", fail_after_commit)
    caplog.set_level(logging.WARNING)

    installation = _publish(
        layout,
        store,
        staging,
        release,
        cancellation=cancellation,
    )

    assert cancellation.is_set()
    assert installation == store.require(release, _POLICY)
    assert "component commit flush deferred" in caplog.text


def test_remove_checks_cancellation_after_lease_scan_before_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, store = _store(tmp_path / "toqraq")
    staging, release = _prepare(layout)
    installation = _publish(layout, store, staging, release)
    cache = layout.download_path(release.identity)
    cache.write_bytes(b"package")
    cancellation = threading.Event()

    def cancel_after_scan(*_details: object) -> int:
        cancellation.set()
        return 0

    monkeypatch.setattr(component_lease, "active_component_lease_count", cancel_after_scan)

    with pytest.raises(ComponentStoreCancelledError):
        _remove(
            layout,
            store,
            release.identity,
            cancellation=cancellation,
        )

    assert installation.root.exists()
    assert cache.exists()


def test_remove_commit_ignores_cancellation_and_reclaims_download(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    layout, store = _store(tmp_path / "toqraq")
    staging, release = _prepare(layout)
    installation = _publish(layout, store, staging, release)
    cache = layout.download_path(release.identity)
    cache.write_bytes(b"package")
    cancellation = threading.Event()

    def cancel_and_fail_flush(_path: Path) -> None:
        cancellation.set()
        raise OSError("private flush failure")

    monkeypatch.setattr(component_store, "_flush_directory", cancel_and_fail_flush)
    caplog.set_level(logging.WARNING)

    removed = _remove(
        layout,
        store,
        release.identity,
        cancellation=cancellation,
    )

    assert removed is True
    assert cancellation.is_set()
    assert not installation.root.exists()
    assert not cache.exists()
    assert "component commit flush deferred" in caplog.text


def test_committed_remove_reports_success_when_download_cleanup_is_deferred(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    layout, store = _store(tmp_path / "toqraq")
    staging, release = _prepare(layout)
    installation = _publish(layout, store, staging, release)
    cache = layout.download_path(release.identity)
    cache.write_bytes(b"package")
    original_unlink = Path.unlink

    def fail_cache_unlink(path: Path, *, missing_ok: bool = False) -> None:
        if path == cache:
            raise OSError("private cache cleanup failure")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_cache_unlink)
    caplog.set_level(logging.WARNING)

    assert _remove(layout, store, release.identity) is True
    assert not installation.root.exists()
    assert cache.exists()
    assert "component download cleanup deferred" in caplog.text


def test_remove_reclaims_download_even_without_an_installation(tmp_path: Path) -> None:
    layout, store = _store(tmp_path / "toqraq")
    identity = _identity()
    cache = layout.download_path(identity)
    cache.write_bytes(b"partial package")

    assert _remove(layout, store, identity) is False
    assert not cache.exists()
