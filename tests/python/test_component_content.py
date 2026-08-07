from __future__ import annotations

import os
import threading
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from toqraq.components import content as component_content
from toqraq.components.content import (
    COMPONENT_MANIFEST_NAME,
    ComponentTreeCancelledError,
    ComponentTreeProgress,
    ComponentTreeRejectedError,
    ComponentTreeRejection,
    fingerprint_published_tree,
    fingerprint_staging_tree,
)
from toqraq.components.content_policy import ComponentContentPolicy


def _policy(**changes: int) -> ComponentContentPolicy:
    values = {
        "max_entries": 32,
        "max_file_bytes": 1 << 20,
        "max_total_bytes": 4 << 20,
        "max_path_depth": 8,
        "max_path_characters": 256,
        "read_chunk_bytes": 4,
    }
    values.update(changes)
    return ComponentContentPolicy(**values)


def _assert_rejected(
    root: Path,
    reason: ComponentTreeRejection,
    *,
    published: bool = False,
    policy: ComponentContentPolicy | None = None,
) -> None:
    operation = fingerprint_published_tree if published else fingerprint_staging_tree
    with pytest.raises(ComponentTreeRejectedError) as captured:
        operation(root, policy or _policy())
    assert captured.value.reason is reason
    assert str(root) not in str(captured.value)


def _fixture_tree(root: Path, *, reverse_creation: bool = False) -> None:
    files = [
        ("a.txt", b"alpha"),
        ("nested/beta.bin", bytes((0, 1, 2))),
    ]
    if reverse_creation:
        files.reverse()
    for relative_path, content in files:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def test_tree_fingerprint_is_canonical_bounded_and_immutable(tmp_path: Path) -> None:
    _fixture_tree(tmp_path, reverse_creation=True)

    fingerprint = fingerprint_staging_tree(tmp_path, _policy())

    assert tuple(file.relative_path for file in fingerprint.files) == (
        "a.txt",
        "nested/beta.bin",
    )
    assert tuple(file.size for file in fingerprint.files) == (5, 3)
    assert fingerprint.total_bytes == 8
    assert fingerprint.tree_sha256 == (
        "426b94947ec4834eef802bfd1eb798ed997196e414ed06db4b1d01bba8eccad6"
    )
    with pytest.raises(FrozenInstanceError):
        fingerprint.total_bytes = 0
    with pytest.raises(TypeError):
        fingerprint.files[0] = fingerprint.files[0]


def test_tree_digest_is_independent_of_creation_and_traversal_order(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _fixture_tree(first)
    _fixture_tree(second, reverse_creation=True)

    one = fingerprint_staging_tree(first, _policy())
    two = fingerprint_staging_tree(second, _policy())

    assert one == two


def test_tree_progress_is_exact_chunked_and_immutable(tmp_path: Path) -> None:
    _fixture_tree(tmp_path)
    observed: list[ComponentTreeProgress] = []

    fingerprint_staging_tree(tmp_path, _policy(), progress=observed.append)

    assert observed == [
        ComponentTreeProgress(0, 8),
        ComponentTreeProgress(4, 8),
        ComponentTreeProgress(5, 8),
        ComponentTreeProgress(8, 8),
    ]
    with pytest.raises(FrozenInstanceError):
        observed[-1].completed_bytes = 0


def test_tree_rejects_impossible_progress_values() -> None:
    with pytest.raises(ValueError):
        ComponentTreeProgress(True, 1)
    with pytest.raises(ValueError):
        ComponentTreeProgress(2, 1)


def test_tree_cancellation_is_observed_after_each_read_chunk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "large.bin").write_bytes(b"0123456789")
    cancellation = threading.Event()
    original_read = os.read
    read_count = 0

    def cancel_after_read(descriptor: int, length: int) -> bytes:
        nonlocal read_count
        chunk = original_read(descriptor, length)
        if chunk:
            read_count += 1
            cancellation.set()
        return chunk

    monkeypatch.setattr(component_content.os, "read", cancel_after_read)

    with pytest.raises(ComponentTreeCancelledError):
        fingerprint_staging_tree(
            tmp_path,
            _policy(),
            cancellation=cancellation,
        )

    assert read_count == 1


def test_tree_cancellation_is_observed_during_directory_entry_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "one.bin").write_bytes(b"one")
    cancellation = threading.Event()
    original_scandir = os.scandir

    class CancellingScandir:
        def __init__(self, path: Path) -> None:
            self._entries = original_scandir(path)

        def __enter__(self) -> CancellingScandir:
            self._entries.__enter__()
            return self

        def __exit__(self, *details: object) -> None:
            self._entries.__exit__(*details)

        def __iter__(self) -> CancellingScandir:
            return self

        def __next__(self) -> os.DirEntry[str]:
            entry = next(self._entries)
            cancellation.set()
            return entry

    monkeypatch.setattr(component_content.os, "scandir", CancellingScandir)

    with pytest.raises(ComponentTreeCancelledError):
        fingerprint_staging_tree(
            tmp_path,
            _policy(),
            cancellation=cancellation,
        )


def test_published_fingerprint_requires_and_excludes_generated_manifest(tmp_path: Path) -> None:
    _fixture_tree(tmp_path)
    staging = fingerprint_staging_tree(tmp_path, _policy())
    _assert_rejected(
        tmp_path,
        ComponentTreeRejection.MANIFEST_MISSING,
        published=True,
    )

    manifest = tmp_path / COMPONENT_MANIFEST_NAME
    manifest.write_text('{"local":"metadata one"}', encoding="utf-8")
    first = fingerprint_published_tree(tmp_path, _policy())
    manifest.write_text('{"local":"metadata changed"}', encoding="utf-8")
    second = fingerprint_published_tree(tmp_path, _policy())

    assert first == staging
    assert second == staging


def test_staging_rejects_reserved_manifest_name_in_any_case(tmp_path: Path) -> None:
    manifest = tmp_path / "Component.JSON"
    manifest.write_text("{}", encoding="utf-8")
    if manifest.name != "Component.JSON":
        pytest.skip("filesystem did not preserve the case variant")

    _assert_rejected(tmp_path, ComponentTreeRejection.MANIFEST_PRESENT)


def test_file_content_path_and_length_all_affect_tree_identity(tmp_path: Path) -> None:
    (tmp_path / "one.bin").write_bytes(b"same")
    baseline = fingerprint_staging_tree(tmp_path, _policy())

    (tmp_path / "one.bin").write_bytes(b"changed")
    changed_content = fingerprint_staging_tree(tmp_path, _policy())
    (tmp_path / "one.bin").rename(tmp_path / "two.bin")
    changed_path = fingerprint_staging_tree(tmp_path, _policy())

    assert len({baseline.tree_sha256, changed_content.tree_sha256, changed_path.tree_sha256}) == 3


def test_rejects_missing_file_and_redirected_roots(tmp_path: Path) -> None:
    _assert_rejected(tmp_path / "missing", ComponentTreeRejection.ROOT_INVALID)
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "root-link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symbolic links unavailable: {type(exc).__name__}")
    _assert_rejected(link, ComponentTreeRejection.ROOT_INVALID)


def test_rejects_symbolic_links_and_special_files(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.write_bytes(b"outside")
    try:
        try:
            (tmp_path / "link").symlink_to(outside)
        except OSError as exc:
            pytest.skip(f"symbolic links unavailable: {type(exc).__name__}")
        _assert_rejected(tmp_path, ComponentTreeRejection.SPECIAL_FILE)
    finally:
        outside.unlink(missing_ok=True)


def test_rejects_hard_links(tmp_path: Path) -> None:
    original = tmp_path / "original"
    original.write_bytes(b"content")
    try:
        os.link(original, tmp_path / "alias")
    except OSError as exc:
        pytest.skip(f"hard links unavailable: {type(exc).__name__}")

    _assert_rejected(tmp_path, ComponentTreeRejection.HARD_LINK)


def test_rejects_named_pipe_without_blocking(tmp_path: Path) -> None:
    if os.name == "nt" or not hasattr(os, "mkfifo"):
        pytest.skip("POSIX named pipe only")
    os.mkfifo(tmp_path / "pipe")

    _assert_rejected(tmp_path, ComponentTreeRejection.SPECIAL_FILE)


def test_rejects_case_colliding_paths_when_filesystem_can_represent_them(
    tmp_path: Path,
) -> None:
    upper = tmp_path / "Engine"
    lower = tmp_path / "engine"
    upper.write_bytes(b"one")
    lower.write_bytes(b"two")
    if len(list(tmp_path.iterdir())) != 2:
        pytest.skip("case-insensitive filesystem")

    _assert_rejected(tmp_path, ComponentTreeRejection.PATH_CONFLICT)


@pytest.mark.parametrize(
    ("files", "policy", "reason"),
    [
        (
            (("one", b"1"), ("two", b"2")),
            _policy(max_entries=1),
            ComponentTreeRejection.TOO_MANY_ENTRIES,
        ),
        (
            (("large", b"123"),),
            _policy(max_file_bytes=2, max_total_bytes=4),
            ComponentTreeRejection.FILE_TOO_LARGE,
        ),
        (
            (("one", b"12"), ("two", b"34")),
            _policy(max_file_bytes=3, max_total_bytes=3),
            ComponentTreeRejection.TREE_TOO_LARGE,
        ),
        (
            (("nested/file", b"x"),),
            _policy(max_path_depth=1),
            ComponentTreeRejection.PATH_TOO_DEEP,
        ),
        (
            (("long-name", b"x"),),
            _policy(max_path_characters=8),
            ComponentTreeRejection.PATH_TOO_LONG,
        ),
    ],
)
def test_tree_reapplies_every_extraction_limit(
    tmp_path: Path,
    files: tuple[tuple[str, bytes], ...],
    policy: ComponentContentPolicy,
    reason: ComponentTreeRejection,
) -> None:
    for relative_path, content in files:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    _assert_rejected(tmp_path, reason, policy=policy)


def test_tree_rejects_the_complete_plan_before_opening_any_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later namespace-limit failure cannot hash an earlier accepted file."""
    (tmp_path / "first.bin").write_bytes(b"first")
    (tmp_path / "second.bin").write_bytes(b"second")
    opened: list[Path] = []
    original_open = os.open

    def record_open(path: str | bytes | os.PathLike[str] | os.PathLike[bytes], flags: int) -> int:
        opened.append(Path(path))
        return original_open(path, flags)

    monkeypatch.setattr(component_content.os, "open", record_open)

    _assert_rejected(
        tmp_path,
        ComponentTreeRejection.TOO_MANY_ENTRIES,
        policy=_policy(max_entries=1),
    )

    assert opened == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_entries", 0),
        ("max_file_bytes", 0),
        ("max_total_bytes", 0),
        ("max_path_depth", 0),
        ("max_path_characters", 0),
        ("read_chunk_bytes", 0),
        ("max_file_bytes", 5 << 20),
    ],
)
def test_content_policy_rejects_invalid_bounds(field: str, value: int) -> None:
    values = {
        "max_entries": 32,
        "max_file_bytes": 1 << 20,
        "max_total_bytes": 4 << 20,
        "max_path_depth": 8,
        "max_path_characters": 256,
        "read_chunk_bytes": 4,
    }
    values[field] = value

    with pytest.raises(ValueError):
        ComponentContentPolicy(**values)
