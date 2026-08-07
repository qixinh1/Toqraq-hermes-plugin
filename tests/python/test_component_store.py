from __future__ import annotations

import json
import logging
import multiprocessing
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from toqraq.components.content import (
    ComponentTreeProgress,
    fingerprint_staging_tree,
)
from toqraq.components.content_policy import ComponentContentPolicy
from toqraq.components.layout import ComponentStoreLayout
from toqraq.components.lock import ComponentLockPolicy
from toqraq.components.mutation import ComponentMutationOwner
from toqraq.components.release import ComponentIdentity, ComponentRelease
from toqraq.components.store import (
    ComponentInstallation,
    ComponentStore,
    ComponentStoreCancelledError,
    ComponentStoreRejectedError,
    ComponentStoreRejection,
)
from toqraq.core.component import ComponentReadiness

_POLICY = ComponentContentPolicy(
    max_entries=32,
    max_file_bytes=1 << 20,
    max_total_bytes=4 << 20,
    max_path_depth=8,
    max_path_characters=256,
    read_chunk_bytes=4,
)
_LOCK_POLICY = ComponentLockPolicy(timeout_seconds=3, poll_seconds=0.01)


def _identity(package_sha256: str = "1" * 64) -> ComponentIdentity:
    return ComponentIdentity.model_validate(
        {
            "component_id": "engine.godot",
            "version": "4.7.1-stable",
            "build_id": "toqraq.windows.x86_64.release",
            "platform": "windows",
            "architecture": "x86_64",
            "package_sha256": package_sha256,
        }
    )


def _release(
    identity: ComponentIdentity,
    tree_sha256: str,
    installed_bytes: int,
) -> ComponentRelease:
    return ComponentRelease.model_validate_json(
        json.dumps(
            {
                "record_version": 1,
                "kind": "engine",
                "plugin_version": "0.1.0",
                "identity": identity.model_dump(mode="json"),
                "label": "Godot 4.7.1",
                "source": {
                    "publisher": "Toqraq",
                    "package_url": "https://downloads.example.test/godot.zip",
                    "provenance_url": "https://builds.example.test/godot/4.7.1",
                    "allowed_origins": ["https://downloads.example.test"],
                },
                "package_bytes": 1_000,
                "installed_bytes": installed_bytes,
                "install_strategy": "archive.zip",
                "expected_tree_sha256": tree_sha256,
                "entry_points": [
                    {
                        "name": "editor",
                        "relative_path": "bin/editor.exe",
                        "executable": True,
                    }
                ],
                "dependencies": [],
                "capabilities": ["toqraq.play.lifecycle"],
                "bridge": None,
                "license": {
                    "identifier": "MIT",
                    "name": "MIT License",
                    "url": "https://godotengine.org/license/",
                    "acceptance_required": False,
                },
                "authentication_required": False,
            }
        )
    )


def _fill(staging: Path, content: bytes = b"engine") -> None:
    executable = staging / "bin" / "editor.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(content)
    if os.name != "nt":
        executable.chmod(0o700)
    (staging / "notice.txt").write_text("license", encoding="utf-8")


def _prepare(
    layout: ComponentStoreLayout,
    identity: ComponentIdentity | None = None,
) -> tuple[Path, ComponentRelease]:
    selected = identity or _identity()
    staging = layout.create_staging(selected)
    _fill(staging)
    fingerprint = fingerprint_staging_tree(staging, _POLICY)
    return staging, _release(
        selected,
        fingerprint.tree_sha256,
        fingerprint.total_bytes,
    )


def _store(root: Path) -> tuple[ComponentStoreLayout, ComponentStore]:
    layout = ComponentStoreLayout(root)
    store = ComponentStore(layout, _LOCK_POLICY)
    store.initialize()
    return layout, store


def _publish(
    layout: ComponentStoreLayout,
    store: ComponentStore,
    staging: Path,
    release: ComponentRelease,
    *,
    cancellation: threading.Event | None = None,
    progress: Callable[[ComponentTreeProgress], None] | None = None,
) -> ComponentInstallation:
    with ComponentMutationOwner(layout, _LOCK_POLICY).acquire(release.identity) as mutation:
        return store.publish_staging(
            staging,
            release,
            _POLICY,
            mutation,
            cancellation=cancellation,
            progress=progress,
        )


def _remove(
    layout: ComponentStoreLayout,
    store: ComponentStore,
    identity: ComponentIdentity,
    *,
    cancellation: threading.Event | None = None,
) -> bool:
    with ComponentMutationOwner(layout, _LOCK_POLICY).acquire(identity) as mutation:
        return store.remove(identity, mutation, cancellation=cancellation)


def _publish_process(root: str, staging: str, release_json: str, result: Any) -> None:
    try:
        layout = ComponentStoreLayout(Path(root))
        store = ComponentStore(layout, _LOCK_POLICY)
        store.initialize()
        release = ComponentRelease.model_validate_json(release_json)
        installation = _publish(layout, store, Path(staging), release)
        result.put(("ready", installation.root.name))
    except BaseException as exc:
        result.put(("error", type(exc).__name__))


def test_publish_find_require_and_entry_point_use_one_exact_identity(tmp_path: Path) -> None:
    layout, store = _store(tmp_path / "toqraq")
    staging, release = _prepare(layout)

    installation = _publish(layout, store, staging, release)

    assert installation.root == layout.component_path(release.identity)
    assert not staging.exists()
    assert store.find(release, _POLICY) == installation
    assert store.require(release, _POLICY) == installation
    assert installation.entry_point("editor") == installation.root / "bin" / "editor.exe"
    with pytest.raises(ComponentStoreRejectedError) as captured:
        installation.entry_point("player")
    assert captured.value.reason is ComponentStoreRejection.ENTRY_POINT_MISSING


def test_readiness_distinguishes_missing_invalid_and_verified_state(tmp_path: Path) -> None:
    layout, store = _store(tmp_path / "toqraq")
    staging, release = _prepare(layout)

    assert store.readiness(release, _POLICY) is ComponentReadiness.MISSING

    installed = _publish(layout, store, staging, release)
    assert store.readiness(release, _POLICY) is ComponentReadiness.READY

    installed.entry_point("editor").write_bytes(b"corrupt")
    assert store.readiness(release, _POLICY) is ComponentReadiness.INVALID


def test_same_exact_release_is_deduplicated_and_extra_staging_is_cleaned(tmp_path: Path) -> None:
    layout, store = _store(tmp_path / "toqraq")
    first, release = _prepare(layout)
    installed = _publish(layout, store, first, release)
    second, same_release = _prepare(layout)

    result = _publish(layout, store, second, same_release)

    assert result == installed
    assert not second.exists()
    assert tuple(layout.components.iterdir()) == (installed.root,)


def test_repair_replaces_only_an_invalid_exact_destination(tmp_path: Path) -> None:
    layout, store = _store(tmp_path / "toqraq")
    first, release = _prepare(layout)
    installed = _publish(layout, store, first, release)
    installed.entry_point("editor").write_bytes(b"corrupt")
    assert store.find(release, _POLICY) is None
    repair, same_release = _prepare(layout)

    repaired = _publish(layout, store, repair, same_release)

    assert repaired.entry_point("editor").read_bytes() == b"engine"
    assert store.find(release, _POLICY) == repaired
    assert not any(".discard." in path.name for path in layout.staging.iterdir())


def test_staging_must_match_certified_digest_before_store_mutation(tmp_path: Path) -> None:
    layout, store = _store(tmp_path / "toqraq")
    staging, release = _prepare(layout)
    (staging / "notice.txt").write_text("changed after certification", encoding="utf-8")

    with pytest.raises(ComponentStoreRejectedError) as captured:
        _publish(layout, store, staging, release)

    assert captured.value.reason is ComponentStoreRejection.STAGING_INVALID
    assert staging.exists()
    assert not layout.component_path(release.identity).exists()


def test_staging_must_be_a_direct_identity_owned_store_child(tmp_path: Path) -> None:
    layout, store = _store(tmp_path / "toqraq")
    staging, release = _prepare(layout)
    outside = tmp_path / "outside"
    outside.mkdir()
    _fill(outside)

    with pytest.raises(ComponentStoreRejectedError) as captured:
        _publish(layout, store, outside, release)

    assert captured.value.reason is ComponentStoreRejection.STAGING_INVALID
    assert staging.exists()


def test_invalid_destination_symlink_is_replaced_without_touching_target(tmp_path: Path) -> None:
    layout, store = _store(tmp_path / "toqraq")
    staging, release = _prepare(layout)
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    destination = layout.component_path(release.identity)
    try:
        destination.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symbolic links unavailable: {type(exc).__name__}")

    installation = _publish(layout, store, staging, release)

    assert installation.root.is_dir()
    assert not installation.root.is_symlink()
    assert marker.read_text(encoding="utf-8") == "keep"


def test_concurrent_threads_publish_one_complete_destination(tmp_path: Path) -> None:
    layout, store = _store(tmp_path / "toqraq")
    first, release = _prepare(layout)
    second, _ = _prepare(layout)
    results: list[Path] = []
    failures: list[BaseException] = []

    def publish(staging: Path) -> None:
        try:
            results.append(_publish(layout, store, staging, release).root)
        except BaseException as exc:
            failures.append(exc)

    threads = [threading.Thread(target=publish, args=(path,)) for path in (first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert failures == []
    assert results == [layout.component_path(release.identity)] * 2
    assert store.require(release, _POLICY).entry_point("editor").read_bytes() == b"engine"


def test_concurrent_processes_publish_one_complete_destination(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    layout, _ = _store(tmp_path / "toqraq")
    first, release = _prepare(layout)
    second, _ = _prepare(layout)
    result = context.Queue()
    arguments = (
        str(layout.root),
        release.model_dump_json(),
        result,
    )
    processes = [
        context.Process(target=_publish_process, args=(arguments[0], str(path), *arguments[1:]))
        for path in (first, second)
    ]

    for process in processes:
        process.start()
    outcomes = [result.get(timeout=10) for _ in processes]
    for process in processes:
        process.join(timeout=10)

    assert outcomes == [("ready", layout.component_path(release.identity).name)] * 2
    assert all(process.exitcode == 0 for process in processes)
    assert (
        ComponentStore(layout, _LOCK_POLICY)
        .require(release, _POLICY)
        .entry_point("editor")
        .read_bytes()
        == b"engine"
    )


def test_cleanup_failure_is_observed_after_existing_installation_is_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    layout, store = _store(tmp_path / "toqraq")
    first, release = _prepare(layout)
    _publish(layout, store, first, release)
    second, _ = _prepare(layout)
    monkeypatch.setattr(
        "toqraq.components.staging.shutil.rmtree",
        lambda _path: _raise_os_error(),
    )
    caplog.set_level(logging.WARNING)

    ready = _publish(layout, store, second, release)

    assert ready.root == layout.component_path(release.identity)
    assert second.exists()
    assert "component cleanup deferred" in caplog.text
    assert release.identity.version not in caplog.text


def _raise_os_error() -> None:
    raise OSError("private cleanup failure")


def test_require_reports_invalid_installation_without_exposing_a_path(tmp_path: Path) -> None:
    layout, store = _store(tmp_path / "toqraq")
    _, release = _prepare(layout)

    with pytest.raises(ComponentStoreRejectedError) as captured:
        store.require(release, _POLICY)

    assert captured.value.reason is ComponentStoreRejection.INSTALLATION_INVALID
    assert str(layout.root) not in str(captured.value)


def test_require_cancellation_wins_before_full_installation_verification(
    tmp_path: Path,
) -> None:
    layout, store = _store(tmp_path / "toqraq")
    staging, release = _prepare(layout)
    _publish(layout, store, staging, release)
    cancellation = threading.Event()
    cancellation.set()

    with pytest.raises(ComponentStoreCancelledError):
        store.require(release, _POLICY, cancellation=cancellation)
