from __future__ import annotations

import hashlib
import io
import json
import os
import threading
import zipfile
from pathlib import Path

import pytest
from toqraq.components.archive import ZipExtractionPolicy
from toqraq.components.content import ComponentFileFingerprint, component_tree_digest
from toqraq.components.content_policy import ComponentContentPolicy
from toqraq.components.download import ComponentDownloader
from toqraq.components.layout import ComponentStoreLayout
from toqraq.components.lock import ComponentLockPolicy
from toqraq.components.mutation import ComponentMutationOwner
from toqraq.components.provision_models import (
    ComponentProvisionCancelledError,
    ComponentProvisionPhase,
    ComponentProvisionProgress,
    ComponentProvisionRejectedError,
    ComponentProvisionRejection,
)
from toqraq.components.provisioner import ComponentProvisioner
from toqraq.components.release import ComponentRelease
from toqraq.components.space import ComponentSpacePolicy
from toqraq.components.store import ComponentStore
from toqraq.components.strategy import ComponentStrategyCatalog
from toqraq.components.zip_strategy import ZipComponentInstallStrategy

from _component_download_support import (
    POLICY as _DOWNLOAD_POLICY,
)
from _component_download_support import (
    URL as _URL,
)
from _component_download_support import (
    OpenSequence,
    full_response,
    install_opener,
)

_CONTENT_POLICY = ComponentContentPolicy(
    max_entries=32,
    max_file_bytes=1 << 20,
    max_total_bytes=4 << 20,
    max_path_depth=8,
    max_path_characters=256,
    read_chunk_bytes=3,
)
_ZIP_POLICY = ZipExtractionPolicy(content=_CONTENT_POLICY, copy_chunk_bytes=3)
_LOCK_POLICY = ComponentLockPolicy(timeout_seconds=2, poll_seconds=0.01)


class _SpaceProbe:
    def __init__(self, available: int = 1 << 30) -> None:
        self.available = available
        self.paths: list[Path] = []

    def available_bytes(self, path: Path) -> int:
        self.paths.append(path)
        return self.available


def _package(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return output.getvalue()


def _tree_digest(files: dict[str, bytes]) -> str:
    values = tuple(
        ComponentFileFingerprint(
            relative_path=path,
            size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )
        for path, content in files.items()
    )
    return component_tree_digest(values)


def _release(package: bytes, files: dict[str, bytes]) -> ComponentRelease:
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
                    "package_url": _URL,
                    "provenance_url": "https://builds.example.test/godot/4.7.1",
                    "allowed_origins": ["https://downloads.example.test"],
                },
                "package_bytes": len(package),
                "installed_bytes": sum(len(content) for content in files.values()),
                "install_strategy": "archive.zip",
                "expected_tree_sha256": _tree_digest(files),
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


def _provisioner(
    tmp_path: Path,
    probe: _SpaceProbe,
    *,
    strategies: ComponentStrategyCatalog | None = None,
) -> tuple[ComponentStoreLayout, ComponentStore, ComponentProvisioner]:
    layout = ComponentStoreLayout(tmp_path / "toqraq")
    mutations = ComponentMutationOwner(layout, _LOCK_POLICY)
    store = ComponentStore(layout, _LOCK_POLICY)
    provisioner = ComponentProvisioner(
        layout,
        mutations,
        ComponentDownloader(layout, _DOWNLOAD_POLICY),
        store,
        strategies or ComponentStrategyCatalog((ZipComponentInstallStrategy(_ZIP_POLICY),)),
        probe,
        ComponentSpacePolicy(reserve_bytes=7),
    )
    return layout, store, provisioner


def _fixture() -> tuple[dict[str, bytes], bytes, ComponentRelease]:
    files = {"bin/editor.exe": b"engine", "notice.txt": b"license"}
    package = _package(files)
    return files, package, _release(package, files)


def test_empty_store_prepares_exact_release_and_emits_ordered_phases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files, package, release = _fixture()
    response = full_response(package)
    install_opener(monkeypatch, OpenSequence(response))
    probe = _SpaceProbe()
    layout, store, provisioner = _provisioner(tmp_path, probe)
    observed: list[ComponentProvisionProgress] = []

    installation = provisioner.prepare(release, progress=observed.append)

    assert installation.root == layout.component_path(release.identity)
    assert installation.entry_point("editor").read_bytes() == files["bin/editor.exe"]
    assert store.require(release, _CONTENT_POLICY) == installation
    assert response.closed
    assert probe.paths == [layout.downloads, layout.staging]
    phases = [value.phase for value in observed]
    assert phases[0] is ComponentProvisionPhase.CHECKING
    assert phases[-1] is ComponentProvisionPhase.READY
    assert set(phases) == set(ComponentProvisionPhase)
    assert phases == sorted(phases, key=list(ComponentProvisionPhase).index)
    assert list(layout.staging.iterdir()) == []
    if os.name != "nt":
        assert installation.entry_point("editor").stat().st_mode & 0o111


def test_ready_release_skips_network_space_and_new_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, package, release = _fixture()
    install_opener(monkeypatch, OpenSequence(full_response(package)))
    first_probe = _SpaceProbe()
    layout, _, provisioner = _provisioner(tmp_path, first_probe)
    expected = provisioner.prepare(release)
    monkeypatch.setattr(
        "toqraq.components.download_http.urllib.request.build_opener",
        lambda *_args: pytest.fail("ready component must not access the network"),
    )
    second_probe = _SpaceProbe(available=0)
    _, _, second = _provisioner(tmp_path, second_probe)

    result = second.prepare(release)

    assert result == expected
    assert second_probe.paths == []
    assert list(layout.staging.iterdir()) == []


def test_download_capacity_failure_happens_before_network_or_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, release = _fixture()
    monkeypatch.setattr(
        "toqraq.components.download_http.urllib.request.build_opener",
        lambda *_args: pytest.fail("capacity failure must precede network"),
    )
    layout, _, provisioner = _provisioner(tmp_path, _SpaceProbe(available=0))

    with pytest.raises(ComponentProvisionRejectedError) as captured:
        provisioner.prepare(release)

    assert captured.value.reason is ComponentProvisionRejection.STORAGE_UNAVAILABLE
    assert list(layout.staging.iterdir()) == []
    assert not layout.component_path(release.identity).exists()


def test_install_cancellation_removes_unique_staging_and_never_publishes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, package, release = _fixture()
    install_opener(monkeypatch, OpenSequence(full_response(package)))
    layout, _, provisioner = _provisioner(tmp_path, _SpaceProbe())
    cancellation = threading.Event()

    def cancel_during_install(value: ComponentProvisionProgress) -> None:
        if (
            value.phase is ComponentProvisionPhase.INSTALLING
            and value.completed_bytes >= _ZIP_POLICY.copy_chunk_bytes
        ):
            cancellation.set()

    with pytest.raises(ComponentProvisionCancelledError):
        provisioner.prepare(
            release,
            cancellation=cancellation,
            progress=cancel_during_install,
        )

    assert list(layout.staging.iterdir()) == []
    assert not layout.component_path(release.identity).exists()
    assert layout.download_path(release.identity).read_bytes() == package


def test_certified_tree_mismatch_fails_publication_and_cleans_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, package, release = _fixture()
    wrong = release.model_copy(update={"expected_tree_sha256": "f" * 64})
    install_opener(monkeypatch, OpenSequence(full_response(package)))
    layout, _, provisioner = _provisioner(tmp_path, _SpaceProbe())

    with pytest.raises(ComponentProvisionRejectedError) as captured:
        provisioner.prepare(wrong)

    assert captured.value.reason is ComponentProvisionRejection.PUBLICATION_FAILED
    assert list(layout.staging.iterdir()) == []
    assert not layout.component_path(release.identity).exists()


def test_unregistered_package_strategy_fails_before_store_mutation(tmp_path: Path) -> None:
    _, _, release = _fixture()
    selected = release.model_copy(update={"install_strategy": "archive.tar"})
    layout, _, provisioner = _provisioner(
        tmp_path,
        _SpaceProbe(),
        strategies=ComponentStrategyCatalog(()),
    )

    with pytest.raises(ComponentProvisionRejectedError) as captured:
        provisioner.prepare(selected)

    assert captured.value.reason is ComponentProvisionRejection.STRATEGY_UNAVAILABLE
    assert not layout.root.exists()
