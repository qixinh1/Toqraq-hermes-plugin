from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from toqraq.core.runtime import (
    PreparedRuntime,
    RuntimeEntryPoint,
    RuntimeEntryPointBinding,
    RuntimeIdentity,
    RuntimeRelease,
)

_COMPONENT_ONE = "1" * 64
_COMPONENT_TWO = "2" * 64


class RecordingResource:
    def __init__(self, name: str) -> None:
        self.name = name
        self.close_count = 0

    async def close(self) -> None:
        self.close_count += 1


class SynchronousResource:
    def close(self) -> None:
        return None


def _identity(
    *,
    engine_id: str = "godot",
    version: str = "4.7.1-stable",
    build_id: str = "toqraq.windows.x86_64.release",
    distribution_id: str = "toqraq",
    platform: str = "windows",
    architecture: str = "x86_64",
) -> RuntimeIdentity:
    return RuntimeIdentity(
        engine_id=engine_id,
        version=version,
        build_id=build_id,
        distribution_id=distribution_id,
        platform=platform,
        architecture=architecture,
    )


def _release(identity: RuntimeIdentity | None = None) -> RuntimeRelease:
    return RuntimeRelease(
        identity=identity or _identity(),
        component_release_ids=(_COMPONENT_ONE, _COMPONENT_TWO),
        entry_point_bindings=(
            RuntimeEntryPointBinding(
                name="editor",
                component_release_id=_COMPONENT_ONE,
                component_entry_point_name="godot_editor",
            ),
            RuntimeEntryPointBinding(
                name="bridge_host",
                component_release_id=_COMPONENT_TWO,
                component_entry_point_name="bridge_host",
            ),
        ),
        bridge_id="toqraq.godot.bridge",
        bridge_protocol="1.0",
        capability_ids=frozenset(
            {
                "toqraq.play.lifecycle",
                "toqraq.preview.display",
            }
        ),
        bridge_capability_ids=frozenset(),
    )


def _entry_points(root: Path) -> tuple[RuntimeEntryPoint, ...]:
    return (
        RuntimeEntryPoint(name="editor", path=root / "bin" / "editor.exe"),
        RuntimeEntryPoint(name="bridge_host", path=root / "bin" / "bridge.exe"),
    )


def test_runtime_identity_contains_complete_immutable_build_identity() -> None:
    identity = _identity()

    assert identity == RuntimeIdentity(
        engine_id="godot",
        version="4.7.1-stable",
        build_id="toqraq.windows.x86_64.release",
        distribution_id="toqraq",
        platform="windows",
        architecture="x86_64",
    )
    with pytest.raises(FrozenInstanceError):
        identity.version = "different"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("engine_id", "Godot"),
        ("version", "4.7 / stable"),
        ("build_id", ""),
        ("distribution_id", "vendor/runtime"),
        ("platform", "Windows"),
        ("architecture", "x86 64"),
    ],
)
def test_runtime_identity_rejects_invalid_fields(field: str, value: str) -> None:
    with pytest.raises(ValueError):
        replace(_identity(), **{field: value})


def test_release_nests_identity_and_has_only_strict_immutable_collections() -> None:
    identity = _identity()
    release = _release(identity)

    assert release.identity is identity
    assert release.component_release_ids == (_COMPONENT_ONE, _COMPONENT_TWO)
    assert release.entry_point_names == ("editor", "bridge_host")
    assert release.entry_point_bindings[0].component_entry_point_name == "godot_editor"
    assert release.capability_ids == frozenset({"toqraq.play.lifecycle", "toqraq.preview.display"})
    assert release.bridge_capability_ids == frozenset()
    with pytest.raises(FrozenInstanceError):
        release.bridge_protocol = "2.0"


@pytest.mark.parametrize(
    "changes",
    [
        {"component_release_ids": ()},
        {"component_release_ids": (_COMPONENT_ONE, _COMPONENT_ONE)},
        {"component_release_ids": ("not-a-digest",)},
        {"component_release_ids": [_COMPONENT_ONE]},
        {"entry_point_bindings": ()},
        {
            "entry_point_bindings": (
                RuntimeEntryPointBinding(
                    name="editor",
                    component_release_id=_COMPONENT_ONE,
                    component_entry_point_name="godot_editor",
                ),
                RuntimeEntryPointBinding(
                    name="editor",
                    component_release_id=_COMPONENT_TWO,
                    component_entry_point_name="bridge_host",
                ),
            )
        },
        {
            "entry_point_bindings": (
                RuntimeEntryPointBinding(
                    name="editor",
                    component_release_id="3" * 64,
                    component_entry_point_name="godot_editor",
                ),
            )
        },
        {"capability_ids": {"toqraq.play.lifecycle"}},
        {"capability_ids": frozenset({"lifecycle"})},
        {"bridge_capability_ids": {"toqraq.play.lifecycle"}},
        {"bridge_capability_ids": frozenset({"toqraq.observe.frame"})},
        {"bridge_capability_ids": frozenset({"frame"})},
        {"bridge_capability_ids": frozenset({"toqraq.play.lifecycle"})},
        {"bridge_id": "bridge"},
        {"bridge_protocol": "protocol 1"},
    ],
)
def test_release_rejects_incomplete_identity_and_ambiguous_collections(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        replace(_release(), **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "Editor"},
        {"component_release_id": "not-a-digest"},
        {"component_entry_point_name": "editor/exe"},
    ],
)
def test_entry_point_binding_requires_explicit_valid_identifiers(
    changes: dict[str, object],
) -> None:
    binding = RuntimeEntryPointBinding(
        name="editor",
        component_release_id=_COMPONENT_ONE,
        component_entry_point_name="godot_editor",
    )
    with pytest.raises(ValueError):
        replace(binding, **changes)


def test_prepared_runtime_cannot_fork_release_identity(tmp_path: Path) -> None:
    identity = _identity()
    release = _release(identity)
    first = RecordingResource("engine lease")
    second = RecordingResource("bridge lease")
    prepared = PreparedRuntime(
        release=release,
        entry_points=_entry_points(tmp_path),
        owned_resources=(first, second),
    )

    assert prepared.release is release
    assert prepared.release.identity is identity
    assert prepared.entry_point("editor") == tmp_path / "bin" / "editor.exe"
    assert prepared.owned_resources == (first, second)
    assert not hasattr(prepared, "close")
    with pytest.raises(FrozenInstanceError):
        prepared.release = _release(_identity(version="4.8-stable"))
    with pytest.raises(KeyError):
        prepared.entry_point("player")


def test_prepared_runtime_requires_exact_release_entry_points(tmp_path: Path) -> None:
    release = _release()

    with pytest.raises(ValueError):
        PreparedRuntime(
            release=release,
            entry_points=tuple(reversed(_entry_points(tmp_path))),
            owned_resources=(),
        )
    with pytest.raises(ValueError):
        PreparedRuntime(
            release=release,
            entry_points=(RuntimeEntryPoint(name="editor", path=tmp_path / "editor.exe"),),
            owned_resources=(),
        )


def test_prepared_runtime_rejects_relative_paths_and_duplicate_ownership(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        RuntimeEntryPoint(name="editor", path=Path("relative/editor.exe"))
    with pytest.raises(ValueError):
        RuntimeEntryPoint(name="editor", path=tmp_path / "bin" / ".." / "editor.exe")

    resource = RecordingResource("lease")
    with pytest.raises(ValueError):
        PreparedRuntime(
            release=_release(),
            entry_points=_entry_points(tmp_path),
            owned_resources=(),
        )
    with pytest.raises(ValueError):
        PreparedRuntime(
            release=_release(),
            entry_points=_entry_points(tmp_path),
            owned_resources=(resource, resource),
        )
    with pytest.raises(ValueError):
        PreparedRuntime(
            release=_release(),
            entry_points=_entry_points(tmp_path),
            owned_resources=[resource],
        )
    with pytest.raises(ValueError):
        PreparedRuntime(
            release=_release(),
            entry_points=_entry_points(tmp_path),
            owned_resources=(SynchronousResource(),),
        )
