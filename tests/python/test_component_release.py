from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from pydantic import ValidationError
from toqraq.components.release import ComponentRelease

_DIGEST = "1" * 64
_TREE_DIGEST = "2" * 64


def _identity(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "component_id": "engine.godot",
        "version": "4.7.1-stable",
        "build_id": "toqraq.windows.x86_64.release",
        "platform": "windows",
        "architecture": "x86_64",
        "package_sha256": _DIGEST,
    }
    value.update(changes)
    return value


def _release(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "record_version": 1,
        "kind": "engine",
        "plugin_version": "0.1.0",
        "identity": _identity(),
        "label": "Godot 4.7.1",
        "source": {
            "publisher": "Toqraq",
            "package_url": "https://downloads.example.test/godot.zip",
            "provenance_url": "https://builds.example.test/godot/4.7.1",
            "allowed_origins": ("https://downloads.example.test",),
        },
        "package_bytes": 1_000,
        "installed_bytes": 2_000,
        "install_strategy": "archive.zip",
        "expected_tree_sha256": _TREE_DIGEST,
        "entry_points": (
            {
                "name": "editor",
                "relative_path": "bin/godot.exe",
                "executable": True,
            },
        ),
        "dependencies": (),
        "capabilities": ("toqraq.play.lifecycle",),
        "bridge": {
            "bridge_id": "toqraq.godot.bridge",
            "protocol": "1.0",
            "capabilities": (),
        },
        "license": {
            "identifier": "MIT",
            "name": "MIT License",
            "url": "https://godotengine.org/license/",
            "acceptance_required": False,
        },
        "authentication_required": False,
    }
    value.update(changes)
    return value


def _invalid(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ComponentRelease.model_validate_json(json.dumps(payload))


def test_release_decodes_strict_json_into_recursive_immutable_values() -> None:
    release = ComponentRelease.model_validate_json(json.dumps(_release()))

    assert release.identity.key == (
        "engine.godot",
        "4.7.1-stable",
        "toqraq.windows.x86_64.release",
        "windows",
        "x86_64",
        _DIGEST,
    )
    assert isinstance(release.entry_points, tuple)
    assert isinstance(release.dependencies, tuple)
    assert isinstance(release.capabilities, tuple)
    assert release.bridge is not None
    assert release.bridge.bridge_id == "toqraq.godot.bridge"
    assert release.bridge.protocol == "1.0"
    assert release.bridge.capabilities == ()
    with pytest.raises(ValidationError):
        release.label = "changed"
    with pytest.raises(ValidationError):
        release.identity.version = "changed"


def test_release_round_trip_uses_only_json_values() -> None:
    release = ComponentRelease.model_validate_json(json.dumps(_release()))

    encoded = release.model_dump_json()
    decoded: Any = json.loads(encoded)

    assert decoded == json.loads(json.dumps(_release()))
    assert ComponentRelease.model_validate_json(encoded) == release


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("record_version", True),
        ("record_version", 2),
        ("plugin_version", " ../0.1.0"),
        ("package_bytes", True),
        ("package_bytes", 0),
        ("installed_bytes", 1 << 40),
        ("install_strategy", "zip"),
        ("expected_tree_sha256", "A" * 64),
        ("authentication_required", 0),
    ],
)
def test_release_rejects_noncanonical_scalar_fields(field: str, value: object) -> None:
    _invalid(_release(**{field: value}))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("component_id", "godot"),
        ("component_id", "engine/Godot"),
        ("version", "../4.7.1"),
        ("version", "4.7.1\\stable"),
        ("version", "4.7:1"),
        ("version", "4.7.1."),
        ("version", "CON"),
        ("version", " 4.7.1"),
        ("build_id", "build\x00id"),
        ("platform", "Windows"),
        ("architecture", "x86/64"),
        ("package_sha256", "f" * 63),
    ],
)
def test_identity_rejects_values_unsafe_for_selection_or_paths(field: str, value: object) -> None:
    _invalid(_release(identity=_identity(**{field: value})))


@pytest.mark.parametrize(
    "url",
    [
        "http://downloads.example.test/godot.zip",
        "https://user:secret@downloads.example.test/godot.zip",
        "https://downloads.example.test/godot.zip#fragment",
        "https://downloads..example.test/godot.zip",
        "https://-downloads.example.test/godot.zip",
        "https://downloads-.example.test/godot.zip",
        "https://downloads.example.test.:443/godot.zip",
        "https://downloads.example.test:invalid/godot.zip",
        "https://downloads.example.test/godot zip",
        "https://downloads.example.test\\evil.test/godot.zip",
    ],
)
def test_source_rejects_ambiguous_or_insecure_package_urls(url: str) -> None:
    payload = _release()
    source = copy.deepcopy(payload["source"])
    assert isinstance(source, dict)
    source["package_url"] = url
    payload["source"] = source

    _invalid(payload)


def test_source_requires_package_origin_to_be_explicitly_allowed() -> None:
    payload = _release()
    source = copy.deepcopy(payload["source"])
    assert isinstance(source, dict)
    source["allowed_origins"] = ("https://mirror.example.test",)
    payload["source"] = source

    _invalid(payload)


def test_source_canonicalizes_origins_and_rejects_duplicates() -> None:
    payload = _release()
    source = copy.deepcopy(payload["source"])
    assert isinstance(source, dict)
    source["package_url"] = "https://DOWNLOADS.EXAMPLE.TEST:443/godot.zip"
    source["allowed_origins"] = ("https://DOWNLOADS.EXAMPLE.TEST:443/",)
    payload["source"] = source

    release = ComponentRelease.model_validate_json(json.dumps(payload))

    assert release.source.allowed_origins == ("https://downloads.example.test",)

    source["allowed_origins"] = (
        "https://downloads.example.test",
        "https://DOWNLOADS.EXAMPLE.TEST:443/",
    )
    _invalid(payload)


@pytest.mark.parametrize(
    "relative_path",
    [
        "/bin/godot.exe",
        "../godot.exe",
        "bin/./godot.exe",
        "bin\\godot.exe",
        "bin//godot.exe",
        "bin/CON.exe",
        "bin/COM¹.log",
        "bin/godot.exe.",
        "bin/godot.exe ",
        "bin/C:godot.exe",
        "bin/godot\x00.exe",
        "bin/e\u0301ditor.exe",
    ],
)
def test_entry_point_rejects_nonportable_or_ambiguous_paths(relative_path: str) -> None:
    payload = _release()
    payload["entry_points"] = (
        {"name": "editor", "relative_path": relative_path, "executable": True},
    )

    _invalid(payload)


def test_release_rejects_duplicate_entry_names_and_case_colliding_paths() -> None:
    payload = _release()
    payload["entry_points"] = (
        {"name": "editor", "relative_path": "bin/godot.exe", "executable": True},
        {"name": "editor", "relative_path": "bin/player.exe", "executable": True},
    )
    _invalid(payload)

    payload["entry_points"] = (
        {"name": "editor", "relative_path": "bin/godot.exe", "executable": True},
        {"name": "player", "relative_path": "BIN/GODOT.EXE", "executable": True},
    )
    _invalid(payload)


def test_release_rejects_duplicate_self_and_oversized_dependencies() -> None:
    payload = _release(dependencies=(_identity(), _identity()))
    _invalid(payload)

    other = _identity(component_id="bridge.godot", package_sha256="3" * 64)
    payload = _release(dependencies=(other, other))
    _invalid(payload)

    dependencies = tuple(
        _identity(
            component_id=f"bridge.part{index}",
            package_sha256=f"{index + 3:064x}",
        )
        for index in range(17)
    )
    _invalid(_release(dependencies=dependencies))


def test_release_rejects_duplicate_or_oversized_capabilities() -> None:
    _invalid(_release(capabilities=("toqraq.play.lifecycle", "toqraq.play.lifecycle")))
    _invalid(_release(capabilities=tuple(f"toqraq.feature{index}" for index in range(65))))

    bridge = {
        "bridge_id": "toqraq.godot.bridge",
        "protocol": "1.0",
        "capabilities": ("toqraq.observe.frame", "toqraq.observe.frame"),
    }
    _invalid(_release(bridge=bridge))
    bridge["capabilities"] = ("toqraq.observe.frame",)
    _invalid(_release(bridge=bridge))
    bridge["capabilities"] = ("toqraq.play.lifecycle",)
    _invalid(_release(bridge=bridge))


@pytest.mark.parametrize(
    "bridge",
    [
        {"bridge_id": "bridge", "protocol": "1.0", "capabilities": ()},
        {"bridge_id": "toqraq.godot.bridge", "protocol": "1 0", "capabilities": ()},
        {"bridge_id": "toqraq.godot.bridge"},
        {
            "bridge_id": "toqraq.godot.bridge",
            "protocol": "1.0",
            "capabilities": (),
            "extra": True,
        },
        False,
    ],
)
def test_release_rejects_invalid_bridge_facts(bridge: object) -> None:
    _invalid(_release(bridge=bridge))


def test_release_requires_explicit_bridge_absence() -> None:
    payload = _release()
    del payload["bridge"]

    _invalid(payload)

    release = ComponentRelease.model_validate_json(json.dumps(_release(bridge=None)))
    assert release.bridge is None


def test_release_rejects_unknown_fields_at_every_level() -> None:
    payload = _release(unexpected=True)
    _invalid(payload)

    payload = _release()
    identity = copy.deepcopy(payload["identity"])
    assert isinstance(identity, dict)
    identity["channel"] = "official"
    payload["identity"] = identity
    _invalid(payload)
