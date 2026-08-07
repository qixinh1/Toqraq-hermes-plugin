from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from toqraq.components.identity import component_identity_key
from toqraq.components.layout import ComponentStoreLayout, ComponentStoreLayoutError
from toqraq.components.release import ComponentIdentity


def _identity() -> ComponentIdentity:
    return ComponentIdentity.model_validate(
        {
            "component_id": "engine.godot",
            "version": "4.7.1-stable",
            "build_id": "toqraq.windows.x86_64.release",
            "platform": "windows",
            "architecture": "x86_64",
            "package_sha256": "1" * 64,
        }
    )


def test_layout_requires_one_explicit_absolute_root() -> None:
    with pytest.raises(ComponentStoreLayoutError, match="absolute"):
        ComponentStoreLayout(Path("relative/store"))


def test_initialize_creates_only_the_documented_private_directories(tmp_path: Path) -> None:
    layout = ComponentStoreLayout(tmp_path / "toqraq")

    layout.initialize()
    layout.initialize()

    assert {path.name for path in layout.root.iterdir()} == {
        "components",
        "downloads",
        "staging",
        "locks",
        "logs",
    }
    for directory in (
        layout.root,
        layout.components,
        layout.downloads,
        layout.staging,
        layout.locks,
        layout.logs,
    ):
        assert directory.is_dir()
        if os.name != "nt":
            assert stat.S_IMODE(directory.stat().st_mode) == 0o700


def test_identity_values_never_become_component_store_segments(tmp_path: Path) -> None:
    layout = ComponentStoreLayout(tmp_path / "toqraq")
    identity = _identity()
    key = component_identity_key(identity)

    assert layout.component_path(identity) == layout.components / key
    assert layout.download_path(identity) == layout.downloads / f"{key}.download"
    assert layout.lock_path(identity) == layout.locks / f"{key}.lock"
    combined = "\n".join(
        str(path)
        for path in (
            layout.component_path(identity),
            layout.download_path(identity),
            layout.lock_path(identity),
        )
    )
    assert identity.version not in combined
    assert identity.build_id not in combined


def test_staging_directories_are_unique_private_and_direct_children(tmp_path: Path) -> None:
    layout = ComponentStoreLayout(tmp_path / "toqraq")
    layout.initialize()

    first = layout.create_staging(_identity())
    second = layout.create_staging(_identity())

    assert first != second
    assert first.parent == second.parent == layout.staging
    assert first.name.startswith(component_identity_key(_identity()) + ".")
    assert second.name.startswith(component_identity_key(_identity()) + ".")
    if os.name != "nt":
        assert stat.S_IMODE(first.stat().st_mode) == 0o700
        assert stat.S_IMODE(second.stat().st_mode) == 0o700


@pytest.mark.parametrize("child", ["components", "downloads", "staging", "locks", "logs"])
def test_initialize_rejects_a_non_directory_store_member(tmp_path: Path, child: str) -> None:
    root = tmp_path / "toqraq"
    root.mkdir()
    (root / child).write_text("not a directory", encoding="utf-8")

    with pytest.raises(ComponentStoreLayoutError):
        ComponentStoreLayout(root).initialize()


def test_initialize_rejects_redirected_root(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    root = tmp_path / "toqraq"
    try:
        root.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symbolic links unavailable: {type(exc).__name__}")

    with pytest.raises(ComponentStoreLayoutError, match="redirected"):
        ComponentStoreLayout(root).initialize()


def test_create_staging_requires_initialized_layout(tmp_path: Path) -> None:
    layout = ComponentStoreLayout(tmp_path / "toqraq")

    with pytest.raises(ComponentStoreLayoutError):
        layout.create_staging(_identity())
