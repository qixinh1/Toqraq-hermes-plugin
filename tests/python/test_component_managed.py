"""Application adapter tests for certified managed components."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from types import TracebackType

import pytest
from toqraq.components.catalog import CertifiedComponentCatalog
from toqraq.components.content_policy import ComponentContentPolicy
from toqraq.components.lock import ComponentLockTimeoutError
from toqraq.components.managed import (
    CertifiedComponentInventory,
    CertifiedComponentPreparation,
    CertifiedComponentRemoval,
)
from toqraq.components.provision_models import (
    ComponentProvisionCancelledError,
    ComponentProvisionPhase,
    ComponentProvisionProgress,
    ComponentProvisionRejectedError,
    ComponentProvisionRejection,
)
from toqraq.components.release import ComponentRelease
from toqraq.components.store import (
    ComponentStoreCancelledError,
    ComponentStoreRejectedError,
    ComponentStoreRejection,
)
from toqraq.components.strategy import (
    ComponentStrategyRejectedError,
    ComponentStrategyRejection,
)
from toqraq.core.component import (
    ComponentReadiness,
    ComponentWorkCancelledError,
    ComponentWorkPhase,
)
from toqraq.core.errors import (
    ComponentDownloadError,
    ComponentInstallError,
    ComponentInUseError,
    ComponentOperationError,
    ComponentOperationTimeoutError,
    ComponentPublicationError,
    ComponentReleaseInvalidError,
    ComponentStorageError,
)

_POLICY = ComponentContentPolicy(32, 1 << 20, 4 << 20, 8, 256, 4)


def _release() -> ComponentRelease:
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
                "expected_tree_sha256": "2" * 64,
                "entry_points": [
                    {
                        "name": "editor",
                        "relative_path": "bin/godot.exe",
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


class FakeStrategy:
    content_policy = _POLICY


class FakeStrategies:
    def __init__(self, failure: BaseException | None = None) -> None:
        self.failure = failure

    def resolve(self, _strategy_id: str) -> FakeStrategy:
        if self.failure is not None:
            raise self.failure
        return FakeStrategy()


class FakeStore:
    def __init__(
        self,
        *,
        installation: object | None = None,
        readiness: ComponentReadiness | None = None,
        in_use: bool = False,
        initialize_failure: BaseException | None = None,
        remove_failure: BaseException | None = None,
    ) -> None:
        self.installation = installation
        self._readiness = readiness
        self._in_use = in_use
        self.initialize_failure = initialize_failure
        self.remove_failure = remove_failure
        self.removed = 0

    def initialize(self) -> None:
        if self.initialize_failure is not None:
            raise self.initialize_failure

    def find(self, *_args: object) -> object | None:
        return self.installation

    def readiness(self, *_args: object) -> ComponentReadiness:
        if self._readiness is not None:
            return self._readiness
        if self.installation is None:
            return ComponentReadiness.MISSING
        return ComponentReadiness.READY

    def is_leased(self, _release: ComponentRelease) -> bool:
        return self._in_use

    def remove(self, *_args: object, **_kwargs: object) -> bool:
        if self.remove_failure is not None:
            raise self.remove_failure
        self.removed += 1
        return True


class FakeProvisioner:
    def __init__(self, failure: BaseException | None = None) -> None:
        self.failure = failure

    def prepare(
        self,
        _release: ComponentRelease,
        *,
        cancellation: threading.Event,
        progress: Callable[[ComponentProvisionProgress], None],
    ) -> object:
        assert not cancellation.is_set()
        progress(ComponentProvisionProgress(ComponentProvisionPhase.CHECKING, 0, 0))
        progress(ComponentProvisionProgress(ComponentProvisionPhase.DOWNLOADING, 500, 1_000))
        progress(ComponentProvisionProgress(ComponentProvisionPhase.INSTALLING, 2_000, 2_000))
        progress(ComponentProvisionProgress(ComponentProvisionPhase.VERIFYING, 2_000, 2_000))
        if self.failure is not None:
            raise self.failure
        progress(ComponentProvisionProgress(ComponentProvisionPhase.READY, 2_000, 2_000))
        return object()


class FakeMutation(AbstractContextManager["FakeMutation"]):
    def __enter__(self) -> FakeMutation:
        return self

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        return None


class FakeMutations:
    def __init__(self, failure: BaseException | None = None) -> None:
        self.failure = failure

    def acquire(self, *_args: object, **_kwargs: object) -> FakeMutation:
        if self.failure is not None:
            raise self.failure
        return FakeMutation()


def _catalog() -> tuple[CertifiedComponentCatalog, ComponentRelease, str]:
    release = _release()
    catalog = CertifiedComponentCatalog((release,))
    return catalog, release, catalog.release_id(release)


def test_inventory_translates_complete_release_and_current_readiness() -> None:
    catalog, release, release_id = _catalog()
    missing = CertifiedComponentInventory(catalog, FakeStore(), FakeStrategies())
    ready = CertifiedComponentInventory(
        catalog,
        FakeStore(installation=object()),
        FakeStrategies(),
    )
    invalid = CertifiedComponentInventory(
        catalog,
        FakeStore(readiness=ComponentReadiness.INVALID),
        FakeStrategies(),
    )
    leased = CertifiedComponentInventory(
        catalog,
        FakeStore(installation=object(), in_use=True),
        FakeStrategies(),
    )

    result = missing.require_component(release_id)
    assert result.release_id == release_id
    assert result.component_id == release.identity.component_id
    assert result.version == release.identity.version
    assert result.source.package_url == release.source.package_url
    assert result.license.identifier == "MIT"
    assert result.capabilities == release.capabilities
    assert result.readiness is ComponentReadiness.MISSING
    assert ready.list_components()[0].readiness is ComponentReadiness.READY
    assert invalid.list_components()[0].readiness is ComponentReadiness.INVALID
    assert ready.list_components()[0].in_use is False
    assert leased.list_components()[0].in_use is True


def test_inventory_translates_strategy_and_store_failures() -> None:
    catalog, _, _ = _catalog()
    unavailable = ComponentStrategyRejectedError(ComponentStrategyRejection.NOT_REGISTERED)
    with pytest.raises(ComponentReleaseInvalidError):
        CertifiedComponentInventory(
            catalog, FakeStore(), FakeStrategies(unavailable)
        ).list_components()
    with pytest.raises(ComponentStorageError):
        CertifiedComponentInventory(
            catalog,
            FakeStore(initialize_failure=OSError("private")),
            FakeStrategies(),
        ).list_components()


def test_preparation_maps_all_monotonic_progress_and_success() -> None:
    catalog, _, release_id = _catalog()
    observed = []
    CertifiedComponentPreparation(catalog, FakeProvisioner()).prepare_component(
        release_id,
        threading.Event(),
        observed.append,
    )
    assert [value.phase for value in observed] == [
        ComponentWorkPhase.CHECKING,
        ComponentWorkPhase.DOWNLOADING,
        ComponentWorkPhase.INSTALLING,
        ComponentWorkPhase.VERIFYING,
        ComponentWorkPhase.READY,
    ]


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (ComponentProvisionRejection.STRATEGY_UNAVAILABLE, ComponentReleaseInvalidError),
        (ComponentProvisionRejection.STORAGE_UNAVAILABLE, ComponentStorageError),
        (ComponentProvisionRejection.DOWNLOAD_FAILED, ComponentDownloadError),
        (ComponentProvisionRejection.INSTALL_FAILED, ComponentInstallError),
        (ComponentProvisionRejection.PUBLICATION_FAILED, ComponentPublicationError),
        (ComponentProvisionRejection.OWNERSHIP_TIMEOUT, ComponentOperationTimeoutError),
        (ComponentProvisionRejection.OWNERSHIP_FAILED, ComponentOperationError),
    ],
)
def test_preparation_maps_every_stable_rejection(reason, expected) -> None:
    catalog, _, release_id = _catalog()
    failure = ComponentProvisionRejectedError(reason)
    with pytest.raises(expected) as captured:
        CertifiedComponentPreparation(catalog, FakeProvisioner(failure)).prepare_component(
            release_id,
            threading.Event(),
            lambda _value: None,
        )
    assert captured.value.parameters == {"release_id": release_id}
    assert captured.value.details == {"reason": reason.value, "phase": "verifying"}
    assert captured.value.cause is failure


def test_preparation_preserves_cooperative_cancellation() -> None:
    catalog, _, release_id = _catalog()
    with pytest.raises(ComponentWorkCancelledError):
        CertifiedComponentPreparation(
            catalog,
            FakeProvisioner(ComponentProvisionCancelledError()),
        ).prepare_component(release_id, threading.Event(), lambda _value: None)


def test_removal_is_owned_idempotent_and_reports_common_phases() -> None:
    catalog, _, release_id = _catalog()
    store = FakeStore()
    observed = []
    CertifiedComponentRemoval(catalog, store, FakeMutations()).remove_component(
        release_id,
        threading.Event(),
        observed.append,
    )
    assert store.removed == 1
    assert [value.phase for value in observed] == [
        ComponentWorkPhase.CHECKING,
        ComponentWorkPhase.REMOVING,
    ]


@pytest.mark.parametrize(
    ("store_failure", "expected"),
    [
        (
            ComponentStoreRejectedError(ComponentStoreRejection.COMPONENT_IN_USE),
            ComponentInUseError,
        ),
        (
            ComponentStoreRejectedError(ComponentStoreRejection.PUBLICATION_FAILED),
            ComponentPublicationError,
        ),
        (
            ComponentStoreRejectedError(ComponentStoreRejection.LEASE_FAILED),
            ComponentOperationError,
        ),
    ],
)
def test_removal_maps_store_rejections(store_failure, expected) -> None:
    catalog, _, release_id = _catalog()
    with pytest.raises(expected) as captured:
        CertifiedComponentRemoval(
            catalog,
            FakeStore(remove_failure=store_failure),
            FakeMutations(),
        ).remove_component(release_id, threading.Event(), lambda _value: None)
    assert captured.value.cause is store_failure


def test_removal_maps_cancellation_and_ownership_timeout() -> None:
    catalog, _, release_id = _catalog()
    cancelled = CertifiedComponentRemoval(
        catalog,
        FakeStore(remove_failure=ComponentStoreCancelledError()),
        FakeMutations(),
    )
    with pytest.raises(ComponentWorkCancelledError):
        cancelled.remove_component(release_id, threading.Event(), lambda _value: None)

    timed_out = CertifiedComponentRemoval(
        catalog,
        FakeStore(),
        FakeMutations(ComponentLockTimeoutError()),
    )
    with pytest.raises(ComponentOperationTimeoutError):
        timed_out.remove_component(release_id, threading.Event(), lambda _value: None)
