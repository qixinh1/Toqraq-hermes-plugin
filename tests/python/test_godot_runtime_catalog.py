from __future__ import annotations

import json
from pathlib import Path

import pytest
from toqraq.components.catalog import CertifiedComponentCatalog
from toqraq.components.release import ComponentRelease
from toqraq.core.capability_ids import (
    MANDATORY_BRIDGE_CAPABILITY_IDS,
    MANDATORY_ENGINE_CAPABILITY_IDS,
)
from toqraq.core.engine_contribution import ProjectDescription, RuntimeCatalog
from toqraq.core.errors import (
    ComponentReleaseInvalidError,
    RuntimeReleaseNotFoundError,
)
from toqraq.core.runtime import RuntimeIdentity
from toqraq.engines.godot.identity import (
    GODOT_EDITOR_ENTRY_POINT,
    GODOT_ENGINE_ID,
    GODOT_RUNTIME_COMPONENT_ID,
    GODOT_RUNTIME_DISTRIBUTION_ID,
)
from toqraq.engines.godot.runtime_catalog import GodotRuntimeCatalog

_DIGEST_ONE = "1" * 64
_TREE_DIGEST = "a" * 64
_EXTRA_CAPABILITY = "godot.observe.signals"
_BRIDGE_CAPABILITIES = MANDATORY_BRIDGE_CAPABILITY_IDS


def _component_payload(
    *,
    version: str = "4.7.1-stable",
    build_id: str = "toqraq.windows.x86_64.release",
    platform: str = "windows",
    architecture: str = "x86_64",
    component_id: str = GODOT_RUNTIME_COMPONENT_ID,
    kind: str = "engine",
    package_sha256: str = _DIGEST_ONE,
    entry_points: list[dict[str, object]] | None = None,
    dependencies: list[dict[str, object]] | None = None,
    capabilities: list[str] | None = None,
    bridge: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "record_version": 1,
        "kind": kind,
        "plugin_version": "0.1.0",
        "identity": {
            "component_id": component_id,
            "version": version,
            "build_id": build_id,
            "platform": platform,
            "architecture": architecture,
            "package_sha256": package_sha256,
        },
        "label": f"Godot {version}",
        "source": {
            "publisher": "Toqraq",
            "package_url": f"https://downloads.example.test/{package_sha256}.zip",
            "provenance_url": "https://builds.example.test/godot",
            "allowed_origins": ["https://downloads.example.test"],
        },
        "package_bytes": 1_000,
        "installed_bytes": 2_000,
        "install_strategy": "archive.zip",
        "expected_tree_sha256": _TREE_DIGEST,
        "entry_points": entry_points
        or [
            {
                "name": GODOT_EDITOR_ENTRY_POINT,
                "relative_path": "bin/godot.exe",
                "executable": True,
            }
        ],
        "dependencies": dependencies or [],
        "capabilities": capabilities
        if capabilities is not None
        else sorted((*MANDATORY_ENGINE_CAPABILITY_IDS, _EXTRA_CAPABILITY)),
        "bridge": bridge
        if bridge is not None
        else {
            "bridge_id": "toqraq.godot.bridge",
            "protocol": "2026.08",
            "capabilities": sorted(_BRIDGE_CAPABILITIES),
        },
        "license": {
            "identifier": "MIT",
            "name": "MIT License",
            "url": "https://godotengine.org/license/",
            "acceptance_required": False,
        },
        "authentication_required": False,
    }


def _component(**changes: object) -> ComponentRelease:
    return ComponentRelease.model_validate_json(json.dumps(_component_payload(**changes)))


def _project(root: Path, *, engine_id: str = GODOT_ENGINE_ID) -> ProjectDescription:
    return ProjectDescription(
        engine_id=engine_id,
        project_root=root,
        marker_path=root / "project.godot",
        confidence=100,
        declared_version="4.7.1-stable",
    )


def _runtime_catalog(
    *components: ComponentRelease,
    order: tuple[int, ...] | None = None,
) -> tuple[GodotRuntimeCatalog, CertifiedComponentCatalog, tuple[str, ...]]:
    component_catalog = CertifiedComponentCatalog(components)
    release_ids = tuple(component_catalog.release_id(component) for component in components)
    selected_ids = release_ids if order is None else tuple(release_ids[index] for index in order)
    return GodotRuntimeCatalog(component_catalog, selected_ids), component_catalog, release_ids


def test_catalog_maps_every_certified_fact_without_guessing(tmp_path: Path) -> None:
    component = _component(
        bridge={
            "bridge_id": "vendor.godot.bridge",
            "protocol": "rpc-7.2",
            "capabilities": sorted(_BRIDGE_CAPABILITIES),
        },
        entry_points=[
            {
                "name": "command_line",
                "relative_path": "bin/godot-console.exe",
                "executable": True,
            },
            {
                "name": GODOT_EDITOR_ENTRY_POINT,
                "relative_path": "bin/godot.exe",
                "executable": True,
            },
        ],
    )
    catalog, _, release_ids = _runtime_catalog(component)

    releases = catalog.releases(_project(tmp_path))
    runtime = releases[0]

    assert isinstance(catalog, RuntimeCatalog)
    assert catalog.engine_id == GODOT_ENGINE_ID
    assert len(releases) == 1
    assert runtime.identity == RuntimeIdentity(
        engine_id=GODOT_ENGINE_ID,
        version=component.identity.version,
        build_id=component.identity.build_id,
        distribution_id=GODOT_RUNTIME_DISTRIBUTION_ID,
        platform=component.identity.platform,
        architecture=component.identity.architecture,
    )
    assert runtime.component_release_ids == release_ids
    assert len(runtime.entry_point_bindings) == 1
    assert runtime.entry_point_bindings[0].name == GODOT_EDITOR_ENTRY_POINT
    assert runtime.entry_point_bindings[0].component_release_id == release_ids[0]
    assert runtime.entry_point_bindings[0].component_entry_point_name == GODOT_EDITOR_ENTRY_POINT
    assert runtime.bridge_id == "vendor.godot.bridge"
    assert runtime.bridge_protocol == "rpc-7.2"
    assert runtime.capability_ids == frozenset(component.capabilities)
    assert runtime.bridge_capability_ids == _BRIDGE_CAPABILITIES
    assert runtime.capability_ids > MANDATORY_ENGINE_CAPABILITY_IDS


def test_catalog_preserves_only_explicit_registration_order(tmp_path: Path) -> None:
    first = _component(version="4.6.3-stable", package_sha256="2" * 64)
    second = _component(version="4.7.1-stable", package_sha256="3" * 64)
    unrelated = _component(
        version="6.0.0",
        component_id="engine.unity",
        package_sha256="4" * 64,
    )
    components = CertifiedComponentCatalog((first, second, unrelated))
    first_id = components.release_id(first)
    second_id = components.release_id(second)
    catalog = GodotRuntimeCatalog(components, (second_id, first_id))

    assert tuple(release.identity.version for release in catalog.releases(_project(tmp_path))) == (
        "4.7.1-stable",
        "4.6.3-stable",
    )


def test_empty_registration_advertises_no_fake_runtime(tmp_path: Path) -> None:
    catalog = GodotRuntimeCatalog(CertifiedComponentCatalog(()), ())

    assert catalog.releases(_project(tmp_path)) == ()


def test_releases_rejects_a_project_from_another_engine(tmp_path: Path) -> None:
    catalog, _, _ = _runtime_catalog(_component())

    with pytest.raises(RuntimeReleaseNotFoundError) as captured:
        catalog.releases(_project(tmp_path, engine_id="unity"))

    assert captured.value.details["reason"] == "engine_mismatch"


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"kind": "bridge"}, "runtime_component_mismatch"),
        ({"component_id": "engine.unity"}, "runtime_component_mismatch"),
        ({"bridge": False}, "runtime_bridge_missing"),
        (
            {
                "entry_points": [
                    {
                        "name": "command_line",
                        "relative_path": "bin/godot.exe",
                        "executable": True,
                    }
                ]
            },
            "runtime_entry_point_missing",
        ),
        (
            {"capabilities": sorted(_BRIDGE_CAPABILITIES)},
            "runtime_baseline_capabilities_missing",
        ),
        (
            {
                "bridge": {
                    "bridge_id": "toqraq.godot.bridge",
                    "protocol": "2026.08",
                    "capabilities": sorted(_BRIDGE_CAPABILITIES - {"toqraq.observe.frame"}),
                }
            },
            "runtime_bridge_capabilities_missing",
        ),
        ({"version": "4.7 stable"}, "runtime_identity_invalid"),
        ({"build_id": "build id"}, "runtime_identity_invalid"),
    ],
)
def test_catalog_rejects_inconsistent_certified_component_facts(
    changes: dict[str, object],
    reason: str,
) -> None:
    payload = _component_payload()
    if changes.get("bridge") is False:
        changes = {**changes, "bridge": None}
    identity_changes = {
        key: changes.pop(key) for key in ("component_id", "version", "build_id") if key in changes
    }
    identity = payload["identity"]
    assert isinstance(identity, dict)
    payload["identity"] = {**identity, **identity_changes}
    component = ComponentRelease.model_validate_json(json.dumps({**payload, **changes}))
    components = CertifiedComponentCatalog((component,))

    with pytest.raises(ComponentReleaseInvalidError) as captured:
        GodotRuntimeCatalog(components, (components.release_id(component),))

    assert captured.value.details["reason"] == reason


def test_catalog_rejects_component_dependencies_until_explicitly_bound() -> None:
    dependency = _component_payload(component_id="bridge.godot")["identity"]
    component = _component(dependencies=[dependency])
    components = CertifiedComponentCatalog((component,))

    with pytest.raises(ComponentReleaseInvalidError) as captured:
        GodotRuntimeCatalog(components, (components.release_id(component),))

    assert captured.value.details["reason"] == "runtime_component_dependencies_not_registered"


def test_catalog_rejects_duplicate_or_unknown_registration() -> None:
    component = _component()
    components = CertifiedComponentCatalog((component,))
    release_id = components.release_id(component)

    with pytest.raises(ComponentReleaseInvalidError) as duplicate:
        GodotRuntimeCatalog(components, (release_id, release_id))
    assert duplicate.value.details["reason"] == "duplicate_runtime_component_registration"

    with pytest.raises(ComponentReleaseInvalidError) as unknown:
        GodotRuntimeCatalog(components, ("f" * 64,))
    assert unknown.value.details["reason"] == "runtime_component_not_registered"


def test_catalog_rejects_two_builds_for_one_public_runtime_choice() -> None:
    first = _component(package_sha256="5" * 64)
    second = _component(
        package_sha256="6" * 64,
        build_id="toqraq.windows.x86_64.debug",
        bridge={
            "bridge_id": "toqraq.godot.bridge",
            "protocol": "next",
            "capabilities": sorted(_BRIDGE_CAPABILITIES),
        },
    )
    components = CertifiedComponentCatalog((first, second))
    release_ids = (components.release_id(first), components.release_id(second))

    with pytest.raises(ComponentReleaseInvalidError) as captured:
        GodotRuntimeCatalog(components, release_ids)

    assert captured.value.details["reason"] == "ambiguous_runtime_version"
