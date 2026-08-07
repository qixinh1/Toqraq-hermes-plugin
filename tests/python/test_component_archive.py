"""Security contracts for managed component ZIP extraction."""

from __future__ import annotations

import io
import os
import stat
import threading
import warnings
import zipfile
from itertools import pairwise
from pathlib import Path

import pytest
from toqraq.components import archive as archive_module
from toqraq.components.archive import (
    ArchiveCancelledError,
    ArchiveProgress,
    ArchiveRejectedError,
    ArchiveRejection,
    ZipExtractionPolicy,
    extract_zip,
)
from toqraq.components.content_policy import ComponentContentPolicy

TEST_POLICY = ZipExtractionPolicy(
    content=ComponentContentPolicy(
        max_entries=8,
        max_file_bytes=16,
        max_total_bytes=24,
        max_path_depth=3,
        max_path_characters=32,
        read_chunk_bytes=4,
    ),
    copy_chunk_bytes=4,
)


def _extract(
    tmp_path: Path,
    members: list[tuple[str | zipfile.ZipInfo, bytes]],
    *,
    policy: ZipExtractionPolicy = TEST_POLICY,
) -> Path:
    archive_path = tmp_path / "component.zip"
    destination = tmp_path / "staging"
    destination.mkdir()
    with zipfile.ZipFile(archive_path, "w") as archive, warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Duplicate name:")
        for name, payload in members:
            archive.writestr(name, payload)
    with zipfile.ZipFile(archive_path) as archive:
        extract_zip(archive, destination, policy)
    return destination


def _assert_rejected(
    tmp_path: Path,
    members: list[tuple[str | zipfile.ZipInfo, bytes]],
    reason: ArchiveRejection,
) -> None:
    with pytest.raises(ArchiveRejectedError) as raised:
        _extract(tmp_path, members)
    assert raised.value.reason is reason


def test_extracts_regular_files_and_directories(tmp_path: Path) -> None:
    destination = _extract(
        tmp_path,
        [("bin/", b""), ("bin/engine.exe", b"engine")],
    )
    assert (destination / "bin" / "engine.exe").read_bytes() == b"engine"


def test_extraction_reports_exact_monotonic_uncompressed_progress(tmp_path: Path) -> None:
    archive_path = tmp_path / "component.zip"
    destination = tmp_path / "staging"
    destination.mkdir()
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("one", b"12345")
        archive.writestr("two", b"678")
    observed: list[ArchiveProgress] = []

    with zipfile.ZipFile(archive_path) as archive:
        extract_zip(archive, destination, TEST_POLICY, progress=observed.append)

    assert observed[0] == ArchiveProgress(0, 8)
    assert observed[-1] == ArchiveProgress(8, 8)
    assert all(
        first.completed_bytes <= second.completed_bytes for first, second in pairwise(observed)
    )


def test_extraction_cancellation_is_observed_between_bounded_chunks(tmp_path: Path) -> None:
    archive_path = tmp_path / "component.zip"
    destination = tmp_path / "staging"
    destination.mkdir()
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("payload", b"12345678")
    cancellation = threading.Event()

    def cancel_after_chunk(value: ArchiveProgress) -> None:
        if value.completed_bytes >= TEST_POLICY.copy_chunk_bytes:
            cancellation.set()

    with zipfile.ZipFile(archive_path) as archive, pytest.raises(ArchiveCancelledError):
        extract_zip(
            archive,
            destination,
            TEST_POLICY,
            cancellation=cancellation,
            progress=cancel_after_chunk,
        )

    assert (destination / "payload").read_bytes() == b"1234"


def test_pre_cancelled_extraction_writes_nothing(tmp_path: Path) -> None:
    archive_path = tmp_path / "component.zip"
    destination = tmp_path / "staging"
    destination.mkdir()
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("payload", b"1234")
    cancellation = threading.Event()
    cancellation.set()

    with zipfile.ZipFile(archive_path) as archive, pytest.raises(ArchiveCancelledError):
        extract_zip(archive, destination, TEST_POLICY, cancellation=cancellation)

    assert list(destination.iterdir()) == []


def test_does_not_preserve_archive_executable_permissions(tmp_path: Path) -> None:
    executable = zipfile.ZipInfo("engine")
    executable.create_system = 3
    executable.external_attr = (stat.S_IFREG | 0o777) << 16
    destination = _extract(tmp_path, [(executable, b"engine")])
    if os.name != "nt":
        assert os.stat(destination / "engine").st_mode & 0o111 == 0


@pytest.mark.parametrize(
    "name",
    [
        "/absolute",
        "../escape",
        "nested/../../escape",
        "C:/escape",
        "//server/share",
        "nested//file",
        "nested/./file",
        "nested/../file",
    ],
)
def test_rejects_noncanonical_or_escaping_paths(tmp_path: Path, name: str) -> None:
    _assert_rejected(tmp_path, [(name, b"x")], ArchiveRejection.INVALID_PATH)


@pytest.mark.parametrize(
    "name",
    [
        "CON",
        "nested/NUL.txt",
        "COM¹.log",
        "trailing.",
        "trailing ",
        "colon:name",
        "question?mark",
        "control\x1fchar",
        "e\u0301.txt",
    ],
)
def test_rejects_nonportable_names_on_every_host(tmp_path: Path, name: str) -> None:
    _assert_rejected(tmp_path, [(name, b"x")], ArchiveRejection.NON_PORTABLE_PATH)


@pytest.mark.parametrize(
    "members",
    [
        [("Engine", b"one"), ("engine", b"two")],
        [("café", b"one"), ("CAFÉ", b"two")],
        [("a/b", b"one"), ("a\\b", b"two")],
    ],
)
def test_rejects_cross_platform_path_collisions(
    tmp_path: Path,
    members: list[tuple[str, bytes]],
) -> None:
    _assert_rejected(tmp_path, members, ArchiveRejection.DUPLICATE_PATH)


@pytest.mark.parametrize(
    "members",
    [
        [("node", b"file"), ("node/child", b"child")],
        [("node/child", b"child"), ("node", b"file")],
    ],
)
def test_rejects_file_and_directory_namespace_conflicts(
    tmp_path: Path,
    members: list[tuple[str, bytes]],
) -> None:
    _assert_rejected(tmp_path, members, ArchiveRejection.PATH_TYPE_CONFLICT)


@pytest.mark.parametrize("file_type", [stat.S_IFLNK, stat.S_IFCHR, stat.S_IFIFO])
def test_rejects_links_and_special_files(tmp_path: Path, file_type: int) -> None:
    member = zipfile.ZipInfo("entry")
    member.create_system = 3
    member.external_attr = (file_type | 0o600) << 16
    _assert_rejected(tmp_path, [(member, b"payload")], ArchiveRejection.SPECIAL_FILE)


def test_rejects_encrypted_entry_before_writing(tmp_path: Path) -> None:
    archive_path = tmp_path / "component.zip"
    destination = tmp_path / "staging"
    destination.mkdir()
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("secret", b"payload")
    with zipfile.ZipFile(archive_path) as archive:
        archive.infolist()[0].flag_bits |= 1
        with pytest.raises(ArchiveRejectedError) as raised:
            extract_zip(archive, destination, TEST_POLICY)
    assert raised.value.reason is ArchiveRejection.ENCRYPTED_ENTRY


def test_rejects_directory_with_payload(tmp_path: Path) -> None:
    _assert_rejected(
        tmp_path,
        [("directory/", b"payload")],
        ArchiveRejection.ENTRY_SIZE_MISMATCH,
    )


def test_rejects_entry_count_limit(tmp_path: Path) -> None:
    members = [(f"entry-{index}", b"") for index in range(TEST_POLICY.content.max_entries + 1)]
    _assert_rejected(tmp_path, members, ArchiveRejection.TOO_MANY_ENTRIES)


def test_rejects_per_entry_and_total_size_limits(tmp_path: Path) -> None:
    _assert_rejected(
        tmp_path,
        [("large", b"x" * (TEST_POLICY.content.max_file_bytes + 1))],
        ArchiveRejection.ENTRY_TOO_LARGE,
    )

    another_root = tmp_path / "total"
    another_root.mkdir()
    _assert_rejected(
        another_root,
        [("one", b"x" * 13), ("two", b"x" * 13)],
        ArchiveRejection.ARCHIVE_TOO_LARGE,
    )


def test_rejects_path_depth_and_character_limits(tmp_path: Path) -> None:
    _assert_rejected(
        tmp_path,
        [("a/b/c/d", b"x")],
        ArchiveRejection.PATH_TOO_DEEP,
    )

    another_root = tmp_path / "characters"
    another_root.mkdir()
    _assert_rejected(
        another_root,
        [("x" * (TEST_POLICY.content.max_path_characters + 1), b"x")],
        ArchiveRejection.PATH_TOO_LONG,
    )


def test_validates_every_member_before_writing_any_file(tmp_path: Path) -> None:
    archive_path = tmp_path / "component.zip"
    destination = tmp_path / "staging"
    destination.mkdir()
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("valid", b"data")
        archive.writestr("../invalid", b"data")
    with zipfile.ZipFile(archive_path) as archive, pytest.raises(ArchiveRejectedError):
        extract_zip(archive, destination, TEST_POLICY)
    assert list(destination.iterdir()) == []


def test_rejects_missing_or_nonempty_destination(tmp_path: Path) -> None:
    archive_path = tmp_path / "component.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("file", b"data")

    missing = tmp_path / "missing"
    with zipfile.ZipFile(archive_path) as archive, pytest.raises(ArchiveRejectedError) as raised:
        extract_zip(archive, missing, TEST_POLICY)
    assert raised.value.reason is ArchiveRejection.DESTINATION_INVALID

    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "existing").write_bytes(b"data")
    with zipfile.ZipFile(archive_path) as archive, pytest.raises(ArchiveRejectedError) as raised:
        extract_zip(archive, occupied, TEST_POLICY)
    assert raised.value.reason is ArchiveRejection.DESTINATION_NOT_EMPTY


@pytest.mark.parametrize(
    ("payload", "declared"),
    [(b"too long", 1), (b"short", 10)],
)
def test_copy_rejects_declared_size_mismatch(payload: bytes, declared: int) -> None:
    output = io.BytesIO()
    with pytest.raises(ArchiveRejectedError) as raised:
        archive_module._copy_entry(
            io.BytesIO(payload),
            output,
            expected_size=declared,
            policy=TEST_POLICY,
        )
    assert raised.value.reason is ArchiveRejection.ENTRY_SIZE_MISMATCH


def test_policy_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        ZipExtractionPolicy(TEST_POLICY.content, 0)
