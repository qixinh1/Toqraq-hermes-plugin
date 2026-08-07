"""Godot inventory confinement, classification, exclusion, and bound tests."""

from __future__ import annotations

import asyncio
import os
import stat
import subprocess
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import cast

import pytest
from toqraq.core.errors import ProjectIntrospectionError
from toqraq.core.project_inventory import ProjectInventoryCategory
from toqraq.engines.godot import project_inventory as inventory_module
from toqraq.engines.godot.project_inventory import GodotProjectInventoryReader

_SECRET_SENTINEL = "NEVER-PUBLISH-THIS-CONFIG-VALUE"
_JUNCTION_COMMAND_TIMEOUT_SECONDS = 10


def _write_project(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "project.godot").write_text(
        "\n".join(
            (
                "config_version=5",
                "[application]",
                f'config/name="{_SECRET_SENTINEL}"',
                'run/main_scene="res://main.tscn"',
                "[input]",
                f'jump={{"deadzone": 0.5, "sentinel": "{_SECRET_SENTINEL}"}}',
                "[autoload]",
                f'GameState="*res://{_SECRET_SENTINEL}.gd"',
                "[editor_plugins]",
                f'enabled=PackedStringArray("{_SECRET_SENTINEL}")',
                "[auth]",
                f'api_key="{_SECRET_SENTINEL}"',
            )
        ),
        encoding="utf-8",
    )


def _touch(root: Path, relative: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")


def _identities(snapshot) -> set[tuple[str, ProjectInventoryCategory, str | None]]:
    return {(entry.path, entry.category, entry.name) for entry in snapshot.entries}


def test_root_scan_classifies_files_and_emits_only_safe_declarations(tmp_path: Path) -> None:
    _write_project(tmp_path)
    for relative in (
        "main.tscn",
        "scripts/player.gd",
        "assets/logo.png",
        "addons/example/plugin.cfg",
        "native/example.gdextension",
        "export_presets.cfg",
        "notes.txt",
        "godot/level.tscn",
        "secret.txt",
        "credentials/hidden.tscn",
        ".godot/imported.tscn",
        "asset.png.import",
    ):
        _touch(tmp_path, relative)

    snapshot = GodotProjectInventoryReader().scan(tmp_path, None, Event())

    identities = _identities(snapshot)
    assert ("main.tscn", ProjectInventoryCategory.SCENE, None) in identities
    assert ("scripts/player.gd", ProjectInventoryCategory.SCRIPT, None) in identities
    assert ("assets/logo.png", ProjectInventoryCategory.RESOURCE, None) in identities
    assert ("godot/level.tscn", ProjectInventoryCategory.SCENE, None) in identities
    assert ("project.godot", ProjectInventoryCategory.SETTING, None) in identities
    assert ("export_presets.cfg", ProjectInventoryCategory.SETTING, None) in identities
    assert ("addons/example/plugin.cfg", ProjectInventoryCategory.DEPENDENCY, None) in identities
    assert ("native/example.gdextension", ProjectInventoryCategory.DEPENDENCY, None) in identities
    assert ("project.godot", ProjectInventoryCategory.INPUT, "input/jump") in identities
    assert (
        "project.godot",
        ProjectInventoryCategory.DEPENDENCY,
        "autoload/GameState",
    ) in identities
    assert (
        "project.godot",
        ProjectInventoryCategory.DEPENDENCY,
        "editor_plugins/enabled",
    ) in identities
    serialized = repr(snapshot)
    assert _SECRET_SENTINEL not in serialized
    assert "application/config/name" not in serialized
    assert "auth/api_key" not in serialized
    assert "secret.txt" not in serialized
    assert "credentials/hidden.tscn" not in serialized
    assert ".godot/imported.tscn" not in serialized
    assert "asset.png.import" not in serialized
    assert snapshot.statistics.excluded_policy >= 4
    assert snapshot.statistics.unclassified == 1
    assert snapshot.statistics.complete


def test_nested_scope_scans_only_subtree_and_never_reads_root_marker(tmp_path: Path) -> None:
    _write_project(tmp_path)
    _touch(tmp_path, "scripts/player.gd")
    _touch(tmp_path, "other/main.tscn")
    (tmp_path / "project.godot").write_bytes(b"not valid utf-8 \xff")

    snapshot = GodotProjectInventoryReader().scan(tmp_path, "scripts", Event())

    assert _identities(snapshot) == {("scripts/player.gd", ProjectInventoryCategory.SCRIPT, None)}
    assert snapshot.statistics.visited_directories == 1


@pytest.mark.parametrize("scope", ["missing", "main.tscn", ".godot"])
def test_scope_must_be_one_visible_no_follow_directory(tmp_path: Path, scope: str) -> None:
    _write_project(tmp_path)
    _touch(tmp_path, "main.tscn")
    (tmp_path / ".godot").mkdir()

    with pytest.raises(ProjectIntrospectionError):
        GodotProjectInventoryReader().scan(tmp_path, scope, Event())


def test_scope_lookup_uses_one_total_entry_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_project(tmp_path)
    _touch(tmp_path, "nested/deep/main.tscn")
    monkeypatch.setattr(inventory_module, "MAX_PROJECT_INVENTORY_SCAN_NODES", 1)

    with pytest.raises(ProjectIntrospectionError):
        GodotProjectInventoryReader().scan(tmp_path, "nested/deep", Event())


def test_links_are_counted_and_never_followed(tmp_path: Path) -> None:
    _write_project(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    _touch(outside, "outside.tscn")
    try:
        os.symlink(outside, tmp_path / "linked", target_is_directory=True)
        os.symlink(outside / "outside.tscn", tmp_path / "linked.tscn")
    except OSError as exc:
        pytest.skip(f"runner cannot create filesystem links: {type(exc).__name__}")

    snapshot = GodotProjectInventoryReader().scan(tmp_path, None, Event())

    assert all(not entry.path.startswith("linked") for entry in snapshot.entries)
    assert snapshot.statistics.excluded_links == 2
    with pytest.raises(ProjectIntrospectionError):
        GodotProjectInventoryReader().scan(tmp_path, "linked", Event())


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_windows_junction_is_excluded_without_reading_target(tmp_path: Path) -> None:
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    link = project / "junction"
    _write_project(project)
    _touch(outside, "outside.tscn")
    assert link.parent == project
    assert outside.parent == tmp_path
    script = (
        "New-Item -ItemType Junction "
        "-LiteralPath $env:TOQRAQ_TEST_JUNCTION_LINK "
        "-Target $env:TOQRAQ_TEST_JUNCTION_TARGET "
        "-ErrorAction Stop | Out-Null"
    )
    environment = os.environ.copy()
    environment["TOQRAQ_TEST_JUNCTION_LINK"] = str(link)
    environment["TOQRAQ_TEST_JUNCTION_TARGET"] = str(outside)
    try:
        created = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=_JUNCTION_COMMAND_TIMEOUT_SECONDS,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        if os.path.lexists(link):
            link.rmdir()
        pytest.skip("runner timed out while creating a Windows junction")
    if created.returncode != 0:
        if os.path.lexists(link):
            link.rmdir()
        pytest.skip("runner cannot create a Windows junction")
    try:
        snapshot = GodotProjectInventoryReader().scan(project, None, Event())
        assert all(not entry.path.startswith("junction") for entry in snapshot.entries)
        assert snapshot.statistics.excluded_links == 1
        with pytest.raises(ProjectIntrospectionError):
            GodotProjectInventoryReader().scan(project, "junction", Event())
    finally:
        link.rmdir()


def test_windows_reparse_attribute_is_always_link_policy() -> None:
    metadata = cast(
        os.stat_result,
        SimpleNamespace(
            st_mode=stat.S_IFDIR,
            st_file_attributes=inventory_module._REPARSE_ATTRIBUTE,
        ),
    )

    assert inventory_module._is_link_or_reparse(metadata)


@pytest.mark.parametrize(
    "scope",
    ["D:tests/fixtures/godot_project", "credentials.", "safe:stream", "CON"],
)
def test_unsafe_portable_scope_never_reaches_path_resolution(
    tmp_path: Path,
    scope: str,
) -> None:
    _write_project(tmp_path)
    _touch(tmp_path, "credentials/hidden.tscn")
    _touch(tmp_path, "safe/visible.tscn")

    with pytest.raises(ValueError):
        GodotProjectInventoryReader().scan(tmp_path, scope, Event())


@pytest.mark.skipif(os.name != "nt", reason="Windows exact-name contract")
def test_windows_scope_requires_exact_direntry_name(tmp_path: Path) -> None:
    _write_project(tmp_path)
    _touch(tmp_path, "safe/visible.tscn")

    with pytest.raises(ProjectIntrospectionError):
        GodotProjectInventoryReader().scan(tmp_path, "SAFE", Event())


def test_linked_project_marker_is_rejected(tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)
    target = tmp_path / "marker-target"
    target.write_text("config_version=5", encoding="utf-8")
    try:
        os.symlink(target, tmp_path / "project.godot")
    except OSError as exc:
        pytest.skip(f"runner cannot create file links: {type(exc).__name__}")

    with pytest.raises(ProjectIntrospectionError) as caught:
        GodotProjectInventoryReader().scan(tmp_path, None, Event())

    assert caught.value.details["reason"] == "project_file_unreadable"


def test_nested_unreadable_directory_marks_observed_counts_incomplete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_project(tmp_path)
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    _touch(blocked, "hidden.tscn")
    original = inventory_module.os.scandir

    def selective_scandir(path: os.PathLike[str] | str):
        if Path(path) == blocked:
            raise PermissionError("unreadable fixture")
        return original(path)

    monkeypatch.setattr(inventory_module.os, "scandir", selective_scandir)

    snapshot = GodotProjectInventoryReader().scan(tmp_path, None, Event())

    assert not snapshot.statistics.complete
    assert snapshot.statistics.unreadable == 1
    assert all(entry.path != "blocked/hidden.tscn" for entry in snapshot.entries)


def test_replaced_directory_discards_its_local_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_project(tmp_path)
    replaced = tmp_path / "replaced"
    _touch(replaced, "discarded.tscn")
    original = inventory_module.os.lstat
    replaced_reads = 0

    def changed_identity(path: os.PathLike[str] | str):
        nonlocal replaced_reads
        metadata = original(path)
        if Path(path) != replaced:
            return metadata
        replaced_reads += 1
        if replaced_reads == 1:
            return metadata
        return cast(
            os.stat_result,
            SimpleNamespace(
                st_mode=metadata.st_mode,
                st_dev=metadata.st_dev,
                st_ino=metadata.st_ino + 1,
                st_file_attributes=0,
            ),
        )

    monkeypatch.setattr(inventory_module.os, "lstat", changed_identity)

    snapshot = GodotProjectInventoryReader().scan(tmp_path, None, Event())

    assert not snapshot.statistics.complete
    assert snapshot.statistics.unreadable == 1
    assert all(entry.path != "replaced/discarded.tscn" for entry in snapshot.entries)


@pytest.mark.parametrize(
    ("constant", "value"),
    [
        ("MAX_PROJECT_INVENTORY_SCAN_NODES", 1),
        ("MAX_PROJECT_INVENTORY_DIRECTORIES", 1),
        ("MAX_PROJECT_INVENTORY_RECORDS", 1),
    ],
)
def test_scan_bounds_stop_with_partial_statistics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    constant: str,
    value: int,
) -> None:
    _write_project(tmp_path)
    _touch(tmp_path, "a.tscn")
    _touch(tmp_path, "nested/b.gd")
    monkeypatch.setattr(inventory_module, constant, value)

    snapshot = GodotProjectInventoryReader().scan(tmp_path, None, Event())

    assert not snapshot.statistics.complete


def test_marker_skips_unrepresentable_input_names(tmp_path: Path) -> None:
    long_name = "x" * 257
    (tmp_path / "project.godot").write_text(
        "\n".join(
            (
                "config_version=5",
                "[input]",
                f"{long_name}=true",
                "control\tname=true",
                "valid=true",
            )
        ),
        encoding="utf-8",
    )

    snapshot = GodotProjectInventoryReader().scan(tmp_path, None, Event())

    names = {entry.name for entry in snapshot.entries if entry.name is not None}
    assert names == {"input/valid"}
    assert snapshot.statistics.excluded_policy == 2


def test_pre_cancelled_scan_never_publishes_a_snapshot(tmp_path: Path) -> None:
    _write_project(tmp_path)
    cancellation = Event()
    cancellation.set()

    with pytest.raises(asyncio.CancelledError):
        GodotProjectInventoryReader().scan(tmp_path, None, cancellation)


def test_marker_parse_observes_inventory_cancellation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_project(tmp_path)
    cancellation = Event()

    def cancel_after_read(descriptor: int, owned: Event) -> bytes:
        del descriptor
        assert owned is cancellation
        owned.set()
        return b"config_version=5\n[input]\njump=true\n"

    monkeypatch.setattr(
        inventory_module,
        "_read_bounded_descriptor",
        cancel_after_read,
    )

    with pytest.raises(asyncio.CancelledError):
        GodotProjectInventoryReader().scan(tmp_path, None, cancellation)
