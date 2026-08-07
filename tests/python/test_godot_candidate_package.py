"""Deterministic Godot candidate package and evidence tests."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path

import pytest
from scripts import package_godot_candidate as package_module
from scripts.godot_candidate_evidence import (
    CANDIDATE_CHECKSUM_NAME,
    CANDIDATE_PACKAGE_NAME,
    CANDIDATE_PROVENANCE_NAME,
    GODOT_CANDIDATE_SCONS_ARGUMENTS,
    GodotCandidateBuildFacts,
    candidate_recipe_sha256,
)
from scripts.package_godot_candidate import package_godot_candidate
from scripts.verify_godot_candidate import verify_godot_candidate
from toqraq.components.archive import extract_zip
from toqraq.components.content import fingerprint_staging_tree
from toqraq.components.settings import component_settings
from toqraq.engines.godot.identity import GODOT_RUNTIME_DISTRIBUTION_ID
from toqraq.version import PLUGIN_VERSION

_UPSTREAM_COMMIT = "a" * 40
_TOQRAQ_COMMIT = "b" * 40
_MODULE_TREE = "c" * 40
_SCONS_ARGUMENTS = GODOT_CANDIDATE_SCONS_ARGUMENTS
_EXPECTED_MEMBERS = (
    "bin/godot.exe",
    "notices/godot/COPYRIGHT.txt",
    "notices/godot/LICENSE.txt",
    "notices/toqraq/LICENSE.txt",
)


def _facts(**changes: object) -> GodotCandidateBuildFacts:
    recipe = candidate_recipe_sha256(_UPSTREAM_COMMIT, _MODULE_TREE, _SCONS_ARGUMENTS)
    values: dict[str, object] = {
        "upstream_tag": "4.7.1-stable",
        "upstream_commit": _UPSTREAM_COMMIT,
        "toqraq_commit": _TOQRAQ_COMMIT,
        "module_git_tree": _MODULE_TREE,
        "recipe_sha256": recipe,
        "build_id": f"gh.123456.2.{recipe}",
        "distribution_id": GODOT_RUNTIME_DISTRIBUTION_ID,
        "workflow_run_id": "123456",
        "workflow_run_attempt": 2,
        "runner_image": "win22",
        "runner_image_version": "20260801.1",
        "python_version": "3.12.11",
        "scons_version": "4.10.1",
        "scons_arguments": _SCONS_ARGUMENTS,
    }
    values.update(changes)
    return GodotCandidateBuildFacts(**values)  # type: ignore[arg-type]


def _inputs(root: Path) -> dict[str, Path]:
    source = root / "source"
    source.mkdir()
    values = {
        "executable": b"MZ\0toqraq-godot-candidate\r\n",
        "godot_license": b"Godot license\r\nunchanged\r\n",
        "godot_copyright": b"Godot copyright\nunchanged\n",
        "toqraq_license": b"Toqraq license\nunchanged\n",
    }
    paths: dict[str, Path] = {}
    for name, content in values.items():
        path = source / name
        path.write_bytes(content)
        paths[name] = path
    return paths


def _package(root: Path, output_name: str = "candidate") -> tuple[Path, dict[str, Path]]:
    inputs = _inputs(root)
    output = root / output_name
    package_godot_candidate(
        **inputs,
        output_directory=output,
        facts=_facts(),
    )
    return output, inputs


def _refresh_checksum(output: Path) -> None:
    package = output / CANDIDATE_PACKAGE_NAME
    provenance = output / CANDIDATE_PROVENANCE_NAME
    (output / CANDIDATE_CHECKSUM_NAME).write_text(
        f"{hashlib.sha256(package.read_bytes()).hexdigest()}  {CANDIDATE_PACKAGE_NAME}\n"
        f"{hashlib.sha256(provenance.read_bytes()).hexdigest()}  "
        f"{CANDIDATE_PROVENANCE_NAME}\n",
        encoding="ascii",
    )


def test_candidate_is_byte_deterministic_and_uses_fixed_zip_metadata(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first, first_inputs = _package(first_root)
    second, _ = _package(second_root)

    for name in (CANDIDATE_PACKAGE_NAME, CANDIDATE_PROVENANCE_NAME, CANDIDATE_CHECKSUM_NAME):
        assert (first / name).read_bytes() == (second / name).read_bytes()

    package = first / CANDIDATE_PACKAGE_NAME
    with zipfile.ZipFile(package) as archive:
        assert tuple(archive.namelist()) == _EXPECTED_MEMBERS
        for info in archive.infolist():
            assert info.date_time == (1980, 1, 1, 0, 0, 0)
            assert info.compress_type == zipfile.ZIP_STORED
            assert info.create_system == 3
            assert info.create_version == 45
            assert info.extract_version == 45
            assert info.extra == info.comment == b""
            assert not info.is_dir()
            assert stat.S_IFMT(info.external_attr >> 16) == stat.S_IFREG
            assert stat.S_IMODE(info.external_attr >> 16) == 0o600
        assert archive.read("bin/godot.exe") == first_inputs["executable"].read_bytes()
        assert (
            archive.read("notices/godot/LICENSE.txt") == first_inputs["godot_license"].read_bytes()
        )
        assert (
            archive.read("notices/godot/COPYRIGHT.txt")
            == first_inputs["godot_copyright"].read_bytes()
        )
        assert (
            archive.read("notices/toqraq/LICENSE.txt")
            == first_inputs["toqraq_license"].read_bytes()
        )
        assert "component.json" not in archive.namelist()
        assert CANDIDATE_PROVENANCE_NAME not in archive.namelist()


def test_provenance_matches_production_fingerprint_and_checksum_algorithms(
    tmp_path: Path,
) -> None:
    output, inputs = _package(tmp_path)
    package = output / CANDIDATE_PACKAGE_NAME
    provenance_path = output / CANDIDATE_PROVENANCE_NAME
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    component = provenance["component"]

    extracted = tmp_path / "extracted"
    extracted.mkdir()
    settings = component_settings(PLUGIN_VERSION)
    with zipfile.ZipFile(package) as archive:
        extract_zip(archive, extracted, settings.zip)
    fingerprint = fingerprint_staging_tree(extracted, settings.zip.content)

    assert provenance["schema"] == "toqraq.godot-candidate.v2"
    assert component["package_bytes"] == package.stat().st_size
    assert (
        component["identity"]["package_sha256"] == hashlib.sha256(package.read_bytes()).hexdigest()
    )
    assert component["installed_bytes"] == fingerprint.total_bytes
    assert component["expected_tree_sha256"] == fingerprint.tree_sha256
    assert component["files"] == [
        {
            "relative_path": value.relative_path,
            "size": value.size,
            "sha256": value.sha256,
        }
        for value in fingerprint.files
    ]
    encoded = provenance_path.read_text(encoding="utf-8")
    assert encoded.endswith("\n")
    assert "\n " not in encoded
    assert all(str(path.resolve()) not in encoded for path in inputs.values())
    expected_sums = (
        f"{hashlib.sha256(package.read_bytes()).hexdigest()}  {CANDIDATE_PACKAGE_NAME}\n"
        f"{hashlib.sha256(provenance_path.read_bytes()).hexdigest()}  "
        f"{CANDIDATE_PROVENANCE_NAME}\n"
    )
    assert (output / CANDIDATE_CHECKSUM_NAME).read_text(encoding="ascii") == expected_sums


def test_strict_verifier_extracts_the_exact_candidate(tmp_path: Path) -> None:
    output, inputs = _package(tmp_path)
    extraction = tmp_path / "verified"
    extraction.mkdir()

    verified = verify_godot_candidate(output, extraction)

    assert verified.executable.read_bytes() == inputs["executable"].read_bytes()
    assert verified.identity.version == "4.7.1-stable"
    assert (
        verified.identity.package_sha256
        == hashlib.sha256((output / CANDIDATE_PACKAGE_NAME).read_bytes()).hexdigest()
    )


@pytest.mark.parametrize("mutation", ["duplicate", "extra", "noncanonical"])
def test_strict_verifier_rejects_ambiguous_provenance(
    tmp_path: Path,
    mutation: str,
) -> None:
    output, _ = _package(tmp_path)
    provenance_path = output / CANDIDATE_PROVENANCE_NAME
    content = provenance_path.read_text(encoding="utf-8")
    if mutation == "duplicate":
        content = content.replace(
            '{"build":',
            '{"schema":"toqraq.godot-candidate.v2","build":',
            1,
        )
    elif mutation == "extra":
        value = json.loads(content)
        value["unexpected"] = True
        content = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    else:
        content = json.dumps(json.loads(content), indent=2, sort_keys=True) + "\n"
    provenance_path.write_text(content, encoding="utf-8")
    if mutation != "duplicate":
        _refresh_checksum(output)
    extraction = tmp_path / "rejected"
    extraction.mkdir()

    with pytest.raises(ValueError):
        verify_godot_candidate(output, extraction)


def test_strict_verifier_rejects_package_or_directory_tampering(tmp_path: Path) -> None:
    output, _ = _package(tmp_path)
    package = output / CANDIDATE_PACKAGE_NAME
    package.write_bytes(package.read_bytes() + b"tampered")
    extraction = tmp_path / "package-rejected"
    extraction.mkdir()
    with pytest.raises(ValueError, match="digest"):
        verify_godot_candidate(output, extraction)

    second_root = tmp_path / "second"
    second_root.mkdir()
    output_two, _ = _package(second_root)
    (output_two / "extra.txt").write_bytes(b"unexpected")
    extraction_two = tmp_path / "directory-rejected"
    extraction_two.mkdir()
    with pytest.raises(ValueError, match="contents"):
        verify_godot_candidate(output_two, extraction_two)


def test_strict_verifier_rejects_checksum_tampering(tmp_path: Path) -> None:
    output, _ = _package(tmp_path)
    (output / CANDIDATE_CHECKSUM_NAME).write_bytes(b"0" * 64)
    extraction = tmp_path / "checksum-rejected"
    extraction.mkdir()

    with pytest.raises(ValueError, match="checksum"):
        verify_godot_candidate(output, extraction)


def test_existing_output_and_failed_build_leave_no_partial_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path)
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "sentinel"
    sentinel.write_bytes(b"owned")

    with pytest.raises(FileExistsError):
        package_godot_candidate(
            **inputs,
            output_directory=existing,
            facts=_facts(),
        )
    assert sentinel.read_bytes() == b"owned"

    def fail_archive(*_args: object, **_kwargs: object) -> None:
        raise OSError("archive failure")

    monkeypatch.setattr(package_module, "_write_archive", fail_archive)
    failed = tmp_path / "failed"
    with pytest.raises(OSError, match="archive failure"):
        package_godot_candidate(
            **inputs,
            output_directory=failed,
            facts=_facts(),
        )
    assert not failed.exists()
    assert not any(path.name.startswith(".toqraq-godot-candidate-") for path in tmp_path.iterdir())


def test_candidate_publish_retries_transient_permission_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "payload").write_bytes(b"complete")
    output = tmp_path / "published"
    original_rename = Path.rename
    attempts = 0
    delays: list[float] = []

    def transient_rename(source: Path, target: Path) -> Path:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("candidate is temporarily locked")
        return original_rename(source, target)

    monkeypatch.setattr(Path, "rename", transient_rename)
    monkeypatch.setattr(package_module.time, "sleep", delays.append)

    package_module._publish_candidate(candidate, output)

    assert attempts == 3
    assert delays == [package_module._PUBLISH_RETRY_SECONDS] * 2
    assert (output / "payload").read_bytes() == b"complete"


def test_candidate_publish_stops_when_output_appears(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    output = tmp_path / "published"
    delays: list[float] = []

    def raced_rename(_source: Path, _target: Path) -> Path:
        output.mkdir()
        (output / "sentinel").write_bytes(b"other publisher")
        raise PermissionError("publish race")

    monkeypatch.setattr(Path, "rename", raced_rename)
    monkeypatch.setattr(package_module.time, "sleep", delays.append)

    with pytest.raises(FileExistsError, match="already exists"):
        package_module._publish_candidate(candidate, output)

    assert delays == []
    assert candidate.is_dir()
    assert (output / "sentinel").read_bytes() == b"other publisher"


def test_candidate_publish_permission_retry_is_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    output = tmp_path / "published"
    attempts = 0
    delays: list[float] = []

    def locked_rename(_source: Path, _target: Path) -> Path:
        nonlocal attempts
        attempts += 1
        raise PermissionError("candidate remains locked")

    monkeypatch.setattr(Path, "rename", locked_rename)
    monkeypatch.setattr(package_module.time, "sleep", delays.append)

    with pytest.raises(PermissionError, match="remains locked"):
        package_module._publish_candidate(candidate, output)

    assert attempts == package_module._PUBLISH_ATTEMPTS
    assert delays == [package_module._PUBLISH_RETRY_SECONDS] * (attempts - 1)
    assert candidate.is_dir()
    assert not output.exists()


def test_candidate_publish_does_not_retry_other_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    output = tmp_path / "published"
    attempts = 0
    delays: list[float] = []

    def failed_rename(_source: Path, _target: Path) -> Path:
        nonlocal attempts
        attempts += 1
        raise OSError("rename failed")

    monkeypatch.setattr(Path, "rename", failed_rename)
    monkeypatch.setattr(package_module.time, "sleep", delays.append)

    with pytest.raises(OSError, match="rename failed"):
        package_module._publish_candidate(candidate, output)

    assert attempts == 1
    assert delays == []
    assert candidate.is_dir()
    assert not output.exists()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"recipe_sha256": "f" * 64}, "recipe digest"),
        ({"distribution_id": "toqraq.other"}, "distribution"),
        ({"runner_image": "C:/runner"}, "environment fact"),
        ({"scons_arguments": ("platform=windows", "platform=linux")}, "unique"),
        ({"scons_arguments": _SCONS_ARGUMENTS[:-1]}, "reviewed candidate vector"),
        (
            {"scons_arguments": (*_SCONS_ARGUMENTS, "deprecated=no")},
            "reviewed candidate vector",
        ),
        (
            {"scons_arguments": tuple(reversed(_SCONS_ARGUMENTS))},
            "reviewed candidate vector",
        ),
    ],
)
def test_build_facts_fail_closed(changes: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _facts(**changes)


def test_hard_linked_source_is_rejected_without_output(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    linked = tmp_path / "linked.exe"
    try:
        os.link(inputs["executable"], linked)
    except OSError:
        pytest.skip("filesystem does not support hard links")
    output = tmp_path / "candidate"

    with pytest.raises(ValueError, match="privately owned"):
        package_godot_candidate(
            **inputs,
            output_directory=output,
            facts=_facts(),
        )

    assert not output.exists()
