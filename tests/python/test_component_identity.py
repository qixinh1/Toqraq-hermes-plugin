from __future__ import annotations

from toqraq.components.identity import component_identity_key
from toqraq.components.release import ComponentIdentity


def _identity(**changes: str) -> ComponentIdentity:
    fields = {
        "component_id": "engine.godot",
        "version": "4.7.1-stable",
        "build_id": "toqraq.windows.x86_64.release",
        "platform": "windows",
        "architecture": "x86_64",
        "package_sha256": "1" * 64,
    }
    fields.update(changes)
    return ComponentIdentity.model_validate(fields)


def test_identity_key_has_a_stable_versioned_framing() -> None:
    key = component_identity_key(_identity())

    assert key == "bad9ef2fd045fd315aa6a8af820273acd5d4994cdf4cb7cd43b854f5b3a724b3"
    assert len(key) == 64
    assert key == key.lower()


def test_every_identity_field_affects_the_store_key() -> None:
    baseline = component_identity_key(_identity())
    variants = {
        component_identity_key(_identity(component_id="engine.cocos")),
        component_identity_key(_identity(version="4.7.2-stable")),
        component_identity_key(_identity(build_id="toqraq.windows.arm64.release")),
        component_identity_key(_identity(platform="linux")),
        component_identity_key(_identity(architecture="arm64")),
        component_identity_key(_identity(package_sha256="2" * 64)),
    }

    assert baseline not in variants
    assert len(variants) == 6
