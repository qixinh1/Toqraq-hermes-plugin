from __future__ import annotations

import json
import os
import stat
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import Any, cast

import pytest
from pydantic import ValidationError
from toqraq.components.content import (
    ComponentTreeCancelledError,
    ComponentTreeFingerprint,
    fingerprint_staging_tree,
)
from toqraq.components.content_policy import ComponentContentPolicy
from toqraq.components.manifest import (
    COMPONENT_MANIFEST_NAME,
    ComponentManifest,
    ComponentManifestRejectedError,
    ComponentManifestRejection,
    create_component_manifest,
    read_component_manifest,
    verify_component_installation,
    write_component_manifest,
)
from toqraq.components.release import ComponentRelease

_POLICY = ComponentContentPolicy(
    max_entries=32,
    max_file_bytes=1 << 20,
    max_total_bytes=4 << 20,
    max_path_depth=8,
    max_path_characters=256,
    read_chunk_bytes=4,
)


def _release(tree_sha256: str, **changes: object) -> ComponentRelease:
    payload: dict[str, object] = {
        "record_version": 1,
        "kind": "engine",
        "plugin_version": "0.1.0",
        "identity": {
            "component_id": "engine.godot",
            "version": "4.7.1-stable",
            "build_id": "toqraq.windows.x86_64.release",
            "platform": "windows",
            "architecture": "x86_64",
            "package_sha256": "1" * 64,
        },
        "label": "Godot 4.7.1",
        "source": {
            "publisher": "Toqraq",
            "package_url": "https://downloads.example.test/godot.zip",
            "provenance_url": "https://builds.example.test/godot/4.7.1",
            "allowed_origins": ["https://downloads.example.test"],
        },
        "package_bytes": 1_000,
        "installed_bytes": 2_000,
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
    payload.update(changes)
    return ComponentRelease.model_validate_json(json.dumps(payload))


def _staging(root: Path) -> tuple[ComponentRelease, ComponentTreeFingerprint]:
    executable = root / "bin" / "editor.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"engine")
    if os.name != "nt":
        executable.chmod(0o700)
    (root / "notice.txt").write_text("license", encoding="utf-8")
    fingerprint = fingerprint_staging_tree(root, _POLICY)
    return _release(
        fingerprint.tree_sha256,
        installed_bytes=fingerprint.total_bytes,
    ), fingerprint


def _published(root: Path) -> tuple[ComponentRelease, ComponentManifest]:
    release, fingerprint = _staging(root)
    manifest = create_component_manifest(release, fingerprint)
    write_component_manifest(root, manifest)
    return release, manifest


def _assert_rejected(
    operation: Callable[[], object],
    reason: ComponentManifestRejection,
) -> ComponentManifestRejectedError:
    with pytest.raises(ComponentManifestRejectedError) as captured:
        operation()
    assert captured.value.reason is reason
    return captured.value


def test_manifest_round_trip_and_full_content_verification(tmp_path: Path) -> None:
    release, fingerprint = _staging(tmp_path)

    manifest = create_component_manifest(release, fingerprint)
    write_component_manifest(tmp_path, manifest)
    loaded = read_component_manifest(tmp_path)
    verified = verify_component_installation(tmp_path, release, _POLICY)

    assert loaded == manifest
    assert verified == manifest
    assert (
        manifest.identity_key == "bad9ef2fd045fd315aa6a8af820273acd5d4994cdf4cb7cd43b854f5b3a724b3"
    )
    assert tuple(file.relative_path for file in manifest.files) == (
        "bin/editor.exe",
        "notice.txt",
    )
    assert json.loads((tmp_path / COMPONENT_MANIFEST_NAME).read_text(encoding="utf-8")) == (
        manifest.model_dump(mode="json")
    )
    if os.name != "nt":
        assert stat.S_IMODE(os.stat(tmp_path / COMPONENT_MANIFEST_NAME).st_mode) == 0o600


def test_full_installation_verification_observes_mid_tree_cancellation(
    tmp_path: Path,
) -> None:
    class DelayedCancellation(Event):
        def __init__(self) -> None:
            super().__init__()
            self.checks = 0

        def is_set(self) -> bool:
            self.checks += 1
            return self.checks >= 3

    release, _ = _published(tmp_path)
    cancellation = DelayedCancellation()

    with pytest.raises(ComponentTreeCancelledError):
        verify_component_installation(
            tmp_path,
            release,
            _POLICY,
            cancellation=cancellation,
        )

    assert cancellation.checks >= 3


def test_create_rejects_staging_that_differs_from_certified_release(tmp_path: Path) -> None:
    _, fingerprint = _staging(tmp_path)
    wrong = _release("f" * 64, installed_bytes=fingerprint.total_bytes)

    _assert_rejected(
        lambda: create_component_manifest(wrong, fingerprint),
        ComponentManifestRejection.CONTENT_MISMATCH,
    )


def test_create_rejects_inaccurate_certified_installed_size(tmp_path: Path) -> None:
    _, fingerprint = _staging(tmp_path)
    wrong = _release(
        fingerprint.tree_sha256,
        installed_bytes=fingerprint.total_bytes + 1,
    )

    _assert_rejected(
        lambda: create_component_manifest(wrong, fingerprint),
        ComponentManifestRejection.CONTENT_MISMATCH,
    )


def test_write_never_replaces_an_existing_manifest(tmp_path: Path) -> None:
    release, fingerprint = _staging(tmp_path)
    manifest = create_component_manifest(release, fingerprint)
    target = tmp_path / COMPONENT_MANIFEST_NAME
    target.write_text("keep", encoding="utf-8")

    _assert_rejected(
        lambda: write_component_manifest(tmp_path, manifest),
        ComponentManifestRejection.MANIFEST_EXISTS,
    )

    assert target.read_text(encoding="utf-8") == "keep"


def test_failed_write_removes_partial_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release, fingerprint = _staging(tmp_path)
    manifest = create_component_manifest(release, fingerprint)
    monkeypatch.setattr(os, "write", lambda _descriptor, _content: 0)

    with pytest.raises(OSError):
        write_component_manifest(tmp_path, manifest)

    assert not (tmp_path / COMPONENT_MANIFEST_NAME).exists()


@pytest.mark.parametrize(
    "content",
    [
        "not JSON",
        "[]",
        '{"manifest_version": NaN}',
        '{"manifest_version": 1, "manifest_version": 1}',
    ],
)
def test_read_rejects_malformed_or_ambiguous_manifest(tmp_path: Path, content: str) -> None:
    (tmp_path / COMPONENT_MANIFEST_NAME).write_text(content, encoding="utf-8")

    error = _assert_rejected(
        lambda: read_component_manifest(tmp_path),
        ComponentManifestRejection.MANIFEST_INVALID,
    )

    assert error.cause is not None
    assert str(tmp_path) not in str(error)


def test_read_rejects_hard_linked_manifest(tmp_path: Path) -> None:
    _, _ = _published(tmp_path)
    target = tmp_path / COMPONENT_MANIFEST_NAME
    alias = tmp_path / "manifest-alias"
    try:
        os.link(target, alias)
    except OSError as exc:
        pytest.skip(f"hard links unavailable: {type(exc).__name__}")

    _assert_rejected(
        lambda: read_component_manifest(tmp_path),
        ComponentManifestRejection.MANIFEST_INVALID,
    )


def test_read_rejects_redirected_component_root(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symbolic links unavailable: {type(exc).__name__}")

    _assert_rejected(
        lambda: read_component_manifest(link),
        ComponentManifestRejection.ROOT_INVALID,
    )


@pytest.mark.parametrize("mutation", ["content", "addition", "deletion"])
def test_verify_rejects_every_published_tree_change(tmp_path: Path, mutation: str) -> None:
    release, _ = _published(tmp_path)
    if mutation == "content":
        (tmp_path / "notice.txt").write_text("changed", encoding="utf-8")
    elif mutation == "addition":
        (tmp_path / "added.txt").write_text("added", encoding="utf-8")
    else:
        (tmp_path / "notice.txt").unlink()

    _assert_rejected(
        lambda: verify_component_installation(tmp_path, release, _POLICY),
        ComponentManifestRejection.CONTENT_MISMATCH,
    )


def test_verify_rejects_another_certified_release(tmp_path: Path) -> None:
    release, _ = _published(tmp_path)
    other_payload = release.model_dump(mode="json")
    identity = cast(dict[str, object], other_payload["identity"])
    identity["package_sha256"] = "2" * 64
    other = ComponentRelease.model_validate_json(json.dumps(other_payload))

    _assert_rejected(
        lambda: verify_component_installation(tmp_path, other, _POLICY),
        ComponentManifestRejection.CONTENT_MISMATCH,
    )


def test_verify_rejects_entry_point_that_is_no_longer_executable(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("Windows executable readiness is determined by the file type")
    release, _ = _published(tmp_path)
    (tmp_path / "bin" / "editor.exe").chmod(0o600)

    _assert_rejected(
        lambda: verify_component_installation(tmp_path, release, _POLICY),
        ComponentManifestRejection.CONTENT_MISMATCH,
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda value: value.update(identity_key="0" * 64),
        lambda value: value.update(total_bytes=value["total_bytes"] + 1),
        lambda value: value["files"].reverse(),
        lambda value: value["files"].append(value["files"][0]),
        lambda value: value["files"].pop(0),
        lambda value: value.update(unexpected=True),
    ],
)
def test_manifest_model_rejects_inconsistent_or_extra_metadata(
    tmp_path: Path,
    change: Callable[[dict[str, Any]], None],
) -> None:
    _, manifest = _published(tmp_path)
    payload = manifest.model_dump(mode="json")
    change(payload)

    with pytest.raises(ValidationError):
        ComponentManifest.model_validate_json(json.dumps(payload))
