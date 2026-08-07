from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import threading
import zipfile
from itertools import pairwise
from pathlib import Path

import pytest
from toqraq.components.archive import ZipExtractionPolicy
from toqraq.components.content_policy import ComponentContentPolicy
from toqraq.components.release import ComponentRelease
from toqraq.components.strategy import (
    ComponentInstallCancelledError,
    ComponentInstallProgress,
    ComponentStrategyCatalog,
    ComponentStrategyRejectedError,
    ComponentStrategyRejection,
)
from toqraq.components.zip_strategy import ZipComponentInstallStrategy

_CONTENT_POLICY = ComponentContentPolicy(
    max_entries=16,
    max_file_bytes=1024,
    max_total_bytes=4096,
    max_path_depth=4,
    max_path_characters=128,
    read_chunk_bytes=3,
)
_ZIP_POLICY = ZipExtractionPolicy(content=_CONTENT_POLICY, copy_chunk_bytes=3)


def _package(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return output.getvalue()


def _release(package: bytes, installed_bytes: int) -> ComponentRelease:
    return ComponentRelease.model_validate_json(
        json.dumps(
            {
                "record_version": 1,
                "kind": "engine",
                "plugin_version": "0.1.0",
                "identity": {
                    "component_id": "engine.godot",
                    "version": "4.7.1-stable",
                    "build_id": "toqraq.windows.x86_64.release",
                    "platform": "windows",
                    "architecture": "x86_64",
                    "package_sha256": hashlib.sha256(package).hexdigest(),
                },
                "label": "Godot 4.7.1",
                "source": {
                    "publisher": "Toqraq",
                    "package_url": "https://downloads.example.test/godot.zip",
                    "provenance_url": "https://builds.example.test/godot/4.7.1",
                    "allowed_origins": ["https://downloads.example.test"],
                },
                "package_bytes": len(package),
                "installed_bytes": installed_bytes,
                "install_strategy": "archive.zip",
                "expected_tree_sha256": "2" * 64,
                "entry_points": [
                    {
                        "name": "editor",
                        "relative_path": "bin/editor.exe",
                        "executable": True,
                    }
                ],
                "dependencies": [],
                "capabilities": [],
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


def test_zip_strategy_extracts_with_exact_progress_and_declared_permissions(
    tmp_path: Path,
) -> None:
    files = {"bin/editor.exe": b"engine", "notice.txt": b"notice"}
    package = _package(files)
    package_path = tmp_path / "component.zip"
    package_path.write_bytes(package)
    staging = tmp_path / "staging"
    staging.mkdir()
    strategy = ZipComponentInstallStrategy(_ZIP_POLICY)
    observed: list[ComponentInstallProgress] = []

    strategy.install(
        package_path,
        staging,
        _release(package, sum(map(len, files.values()))),
        progress=observed.append,
    )

    assert strategy.content_policy is _CONTENT_POLICY
    assert (staging / "bin" / "editor.exe").read_bytes() == b"engine"
    assert (staging / "notice.txt").read_bytes() == b"notice"
    assert observed[0] == ComponentInstallProgress(0, 12)
    assert observed[-1] == ComponentInstallProgress(12, 12)
    assert all(
        first.completed_bytes <= second.completed_bytes for first, second in pairwise(observed)
    )
    if os.name != "nt":
        assert stat.S_IMODE((staging / "bin" / "editor.exe").stat().st_mode) == 0o700
        assert stat.S_IMODE((staging / "notice.txt").stat().st_mode) == 0o600


def test_zip_strategy_translates_bounded_extraction_cancellation(tmp_path: Path) -> None:
    files = {"bin/editor.exe": b"12345678"}
    package = _package(files)
    package_path = tmp_path / "component.zip"
    package_path.write_bytes(package)
    staging = tmp_path / "staging"
    staging.mkdir()
    cancellation = threading.Event()

    def cancel(value: ComponentInstallProgress) -> None:
        if value.completed_bytes >= _ZIP_POLICY.copy_chunk_bytes:
            cancellation.set()

    with pytest.raises(ComponentInstallCancelledError):
        ZipComponentInstallStrategy(_ZIP_POLICY).install(
            package_path,
            staging,
            _release(package, 8),
            cancellation=cancellation,
            progress=cancel,
        )


def test_zip_strategy_rejects_redirected_or_wrong_size_packages(tmp_path: Path) -> None:
    package = _package({"bin/editor.exe": b"engine"})
    source = tmp_path / "source.zip"
    source.write_bytes(package)
    redirected = tmp_path / "redirected.zip"
    try:
        redirected.symlink_to(source)
    except OSError as exc:
        pytest.skip(f"symbolic links unavailable: {type(exc).__name__}")

    for candidate in (redirected, source):
        staging = tmp_path / f"staging-{candidate.stem}"
        staging.mkdir()
        expected = len(package) + (1 if candidate == source else 0)
        with pytest.raises((OSError, ValueError)):
            ZipComponentInstallStrategy(_ZIP_POLICY).install(
                candidate,
                staging,
                _release(package, 6).model_copy(update={"package_bytes": expected}),
            )


class _BlankZipStrategy(ZipComponentInstallStrategy):
    strategy_id = ""


def test_strategy_catalog_rejects_ambiguity_invalid_ids_and_missing_strategy() -> None:
    strategy = ZipComponentInstallStrategy(_ZIP_POLICY)
    with pytest.raises(ComponentStrategyRejectedError) as duplicate:
        ComponentStrategyCatalog((strategy, strategy))
    assert duplicate.value.reason is ComponentStrategyRejection.DUPLICATE

    with pytest.raises(ComponentStrategyRejectedError) as invalid:
        ComponentStrategyCatalog((_BlankZipStrategy(_ZIP_POLICY),))
    assert invalid.value.reason is ComponentStrategyRejection.NOT_REGISTERED

    catalog = ComponentStrategyCatalog((strategy,))
    assert catalog.resolve("archive.zip") is strategy
    with pytest.raises(ComponentStrategyRejectedError) as missing:
        catalog.resolve("archive.tar")
    assert missing.value.reason is ComponentStrategyRejection.NOT_REGISTERED
