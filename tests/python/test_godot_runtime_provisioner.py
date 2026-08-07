"""Exact installed Godot runtime preparation and lease tests."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import cast

import pytest
from toqraq.components.catalog import CertifiedComponentCatalog
from toqraq.components.layout import ComponentStoreLayout
from toqraq.components.lease import ComponentLease
from toqraq.components.mutation import ComponentMutation, ComponentMutationOwner
from toqraq.components.release import ComponentRelease
from toqraq.components.store import (
    ComponentInstallation,
    ComponentStore,
    ComponentStoreRejectedError,
    ComponentStoreRejection,
)
from toqraq.components.strategy import (
    ComponentInstallProgress,
    ComponentStrategyCatalog,
)
from toqraq.core.capability_ids import (
    MANDATORY_BRIDGE_CAPABILITY_IDS,
    MANDATORY_ENGINE_CAPABILITY_IDS,
)
from toqraq.core.engine_contribution import ProjectDescription, RuntimeProvisioner
from toqraq.core.errors import (
    ComponentReleaseInvalidError,
    RuntimeNotInstalledError,
)
from toqraq.core.runtime import RuntimePreparationCancelledError, RuntimeRelease
from toqraq.engines.godot.runtime_catalog import GodotRuntimeCatalog
from toqraq.engines.godot.runtime_provisioner import GodotRuntimeProvisioner

from test_component_store import (
    _LOCK_POLICY,
    _POLICY,
    _prepare,
    _publish,
    _remove,
    _store,
)


class _PolicyOnlyStrategy:
    strategy_id = "archive.zip"
    content_policy = _POLICY

    def install(
        self,
        package: Path,
        staging: Path,
        release: ComponentRelease,
        *,
        cancellation: Event | None = None,
        progress: Callable[[ComponentInstallProgress], None] | None = None,
    ) -> None:
        raise AssertionError("runtime preparation must not install a package")


class _CancellingStore(ComponentStore):
    def __init__(self, layout: ComponentStoreLayout, cancellation: Event) -> None:
        super().__init__(layout, _LOCK_POLICY)
        self._test_cancellation = cancellation

    def acquire_lease(
        self,
        installation: ComponentInstallation,
        mutation: ComponentMutation,
        *,
        cancellation: Event | None = None,
    ) -> ComponentLease[ComponentInstallation]:
        lease = super().acquire_lease(
            installation,
            mutation,
            cancellation=cancellation,
        )
        self._test_cancellation.set()
        return lease


class _DeferredMutationRelease:
    """Fail the first ownership transfer without losing the real token."""

    def __init__(self, mutation: ComponentMutation) -> None:
        self._mutation = mutation
        self.close_count = 0

    def require(self, identity) -> None:
        """Delegate exact-identity authorization."""
        self._mutation.require(identity)

    def close(self) -> None:
        """Retain the real lock once, then release it on cleanup retry."""
        self.close_count += 1
        if self.close_count == 1:
            raise OSError("native mutation unlock failed")
        self._mutation.close()


class _DeferredMutationOwner:
    def __init__(self, owner: ComponentMutationOwner) -> None:
        self._owner = owner
        self.acquired: _DeferredMutationRelease | None = None

    def acquire(self, identity, *, cancellation: Event | None = None) -> ComponentMutation:
        """Wrap one real acquired token with a deterministic release failure."""
        mutation = _DeferredMutationRelease(
            self._owner.acquire(identity, cancellation=cancellation)
        )
        self.acquired = mutation
        return cast(ComponentMutation, mutation)


def _runtime_component(release: ComponentRelease) -> ComponentRelease:
    payload = release.model_dump(mode="json")
    payload["capabilities"] = sorted(MANDATORY_ENGINE_CAPABILITY_IDS)
    payload["bridge"] = {
        "bridge_id": "toqraq.godot.bridge",
        "protocol": "2026.08",
        "capabilities": sorted(MANDATORY_BRIDGE_CAPABILITY_IDS),
    }
    return ComponentRelease.model_validate_json(json.dumps(payload))


def _graph(
    root: Path,
    *,
    publish: bool,
    cancellation_store: Event | None = None,
    include_strategy: bool = True,
) -> tuple[
    GodotRuntimeProvisioner,
    ComponentStoreLayout,
    ComponentStore,
    ComponentRelease,
    RuntimeRelease,
]:
    layout, store = _store(root)
    staging, base_release = _prepare(layout)
    component = _runtime_component(base_release)
    if publish:
        _publish(layout, store, staging, component)
    components = CertifiedComponentCatalog((component,))
    release_id = components.release_id(component)
    runtimes = GodotRuntimeCatalog(components, (release_id,))
    selected_store = (
        _CancellingStore(layout, cancellation_store) if cancellation_store is not None else store
    )
    provisioner = GodotRuntimeProvisioner(
        components,
        selected_store,
        ComponentStrategyCatalog((_PolicyOnlyStrategy(),) if include_strategy else ()),
        ComponentMutationOwner(layout, _LOCK_POLICY),
    )
    return provisioner, layout, store, component, runtimes.releases(_project(root))[0]


def _project(root: Path) -> ProjectDescription:
    return ProjectDescription(
        engine_id="godot",
        project_root=root,
        marker_path=root / "project.godot",
        confidence=100,
    )


def test_prepare_transfers_exact_verified_entry_and_lease(tmp_path: Path) -> None:
    provisioner, layout, store, component, release = _graph(
        tmp_path / "store",
        publish=True,
    )

    prepared = provisioner.prepare(release, Event())

    assert isinstance(provisioner, RuntimeProvisioner)
    assert prepared.release is release
    assert prepared.entry_point("editor").name == "editor.exe"
    with pytest.raises(ComponentStoreRejectedError) as caught:
        _remove(layout, store, component.identity)
    assert caught.value.reason is ComponentStoreRejection.COMPONENT_IN_USE

    asyncio.run(prepared.owned_resources[0].close())
    assert _remove(layout, store, component.identity) is True


def test_prepare_never_installs_a_missing_component(tmp_path: Path) -> None:
    provisioner, _, _, _, release = _graph(tmp_path / "store", publish=False)

    with pytest.raises(RuntimeNotInstalledError) as caught:
        provisioner.prepare(release, Event())

    assert caught.value.details["reason"] == "installation_invalid"


def test_prepare_rejects_cancelled_request(tmp_path: Path) -> None:
    provisioner, _, _, _, release = _graph(tmp_path / "store", publish=True)
    cancellation = Event()
    cancellation.set()

    with pytest.raises(RuntimePreparationCancelledError):
        provisioner.prepare(release, cancellation)


def test_prepare_uses_selected_release_without_catalog_revalidation(tmp_path: Path) -> None:
    provisioner, _, _, _, release = _graph(tmp_path / "store", publish=True)
    selected = replace(release)

    prepared = provisioner.prepare(selected, Event())

    assert prepared.release is selected
    asyncio.run(prepared.owned_resources[0].close())


def test_cancellation_after_lease_commit_belongs_to_prepared_runtime(tmp_path: Path) -> None:
    cancellation = Event()
    provisioner, layout, store, component, release = _graph(
        tmp_path / "store",
        publish=True,
        cancellation_store=cancellation,
    )

    prepared = provisioner.prepare(release, cancellation)

    with pytest.raises(ComponentStoreRejectedError) as caught:
        _remove(layout, store, component.identity)
    assert caught.value.reason is ComponentStoreRejection.COMPONENT_IN_USE
    asyncio.run(prepared.owned_resources[0].close())
    assert _remove(layout, store, component.identity) is True


def test_failed_mutation_release_transfers_both_owners_to_prepared_runtime(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    provisioner, layout, store, component, release = _graph(
        tmp_path / "store",
        publish=True,
    )
    mutations = _DeferredMutationOwner(ComponentMutationOwner(layout, _LOCK_POLICY))
    provisioner._mutations = cast(ComponentMutationOwner, mutations)

    prepared = provisioner.prepare(release, Event())

    assert mutations.acquired is not None
    assert mutations.acquired.close_count == 1
    assert "component mutation release deferred" in caplog.text
    asyncio.run(prepared.owned_resources[0].close())
    assert mutations.acquired.close_count == 2
    assert _remove(layout, store, component.identity) is True


def test_prepare_rejects_unregistered_component_strategy(tmp_path: Path) -> None:
    provisioner, layout, store, component, release = _graph(
        tmp_path / "store",
        publish=True,
        include_strategy=False,
    )

    with pytest.raises(ComponentReleaseInvalidError) as caught:
        provisioner.prepare(release, Event())

    assert caught.value.details["reason"] == "runtime_component_strategy_invalid"
    assert _remove(layout, store, component.identity) is True
