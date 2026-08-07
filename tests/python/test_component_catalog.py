from __future__ import annotations

import json

import pytest
from toqraq.components.catalog import (
    MAX_COMPONENT_RECORDS_PER_CATALOG,
    CertifiedComponentCatalog,
)
from toqraq.components.identity import component_identity_key
from toqraq.components.release import ComponentRelease
from toqraq.core.errors import ComponentReleaseInvalidError, ComponentReleaseNotFoundError


def _payload(*, component_id: str = "engine.godot") -> dict[str, object]:
    return {
        "record_version": 1,
        "kind": "engine",
        "plugin_version": "0.1.0",
        "identity": {
            "component_id": component_id,
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


def _release(*, component_id: str = "engine.godot") -> ComponentRelease:
    return ComponentRelease.model_validate_json(json.dumps(_payload(component_id=component_id)))


def test_certified_catalog_owns_deterministic_opaque_release_lookup() -> None:
    godot = _release(component_id="engine.godot")
    bridge = _release(component_id="bridge.godot")
    catalog = CertifiedComponentCatalog((bridge, godot))

    assert catalog.list() == (bridge, godot)
    assert catalog.release_id(godot) == component_identity_key(godot.identity)
    assert catalog.require(catalog.release_id(bridge)) is bridge

    with pytest.raises(ComponentReleaseNotFoundError) as captured:
        catalog.require("f" * 64)
    assert captured.value.parameters == {"release_id": "f" * 64}


def test_certified_catalog_rejects_duplicates_unregistered_and_oversized_sets() -> None:
    release = _release()
    with pytest.raises(ComponentReleaseInvalidError) as duplicate:
        CertifiedComponentCatalog((release, release.model_copy()))
    assert duplicate.value.details == {"reason": "duplicate_component_identity"}

    catalog = CertifiedComponentCatalog((release,))
    changed = release.model_copy(update={"label": "Changed label"})
    with pytest.raises(ComponentReleaseInvalidError) as unregistered:
        catalog.release_id(changed)
    assert unregistered.value.details == {"reason": "release_not_registered"}

    with pytest.raises(ComponentReleaseInvalidError) as oversized:
        CertifiedComponentCatalog(
            release.model_copy(
                update={
                    "identity": release.identity.model_copy(
                        update={"package_sha256": f"{index:064x}"}
                    )
                }
            )
            for index in range(MAX_COMPONENT_RECORDS_PER_CATALOG + 1)
        )
    assert oversized.value.details == {"reason": "certified_record_set_too_large"}
