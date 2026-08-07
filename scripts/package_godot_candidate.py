"""Build one deterministic, uncertified Godot component candidate."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import stat
import tempfile
import time
import zipfile
from pathlib import Path
from typing import IO

from scripts.godot_candidate_evidence import (
    CANDIDATE_CHECKSUM_NAME,
    CANDIDATE_PACKAGE_NAME,
    CANDIDATE_PROVENANCE_NAME,
    GodotCandidateBuildFacts,
    candidate_provenance,
    canonical_candidate_json,
)
from toqraq.components.archive import extract_zip
from toqraq.components.content import (
    ComponentFileFingerprint,
    ComponentTreeFingerprint,
    fingerprint_staging_tree,
)
from toqraq.components.download_file import hash_partial, open_partial
from toqraq.components.paths import is_link_or_reparse
from toqraq.components.release import ComponentIdentity
from toqraq.components.settings import component_settings
from toqraq.engines.godot.identity import (
    GODOT_RUNTIME_COMPONENT_ID,
)
from toqraq.version import PLUGIN_VERSION

_ARCHIVE_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_WORK_PREFIX = ".toqraq-godot-candidate-"
_PUBLISH_ATTEMPTS = 8
_PUBLISH_RETRY_SECONDS = 0.05


def package_godot_candidate(
    *,
    executable: Path,
    godot_license: Path,
    godot_copyright: Path,
    toqraq_license: Path,
    output_directory: Path,
    facts: GodotCandidateBuildFacts,
) -> Path:
    """Create and atomically publish one deterministic candidate directory."""
    output, parent = _candidate_output(output_directory)
    work = Path(tempfile.mkdtemp(prefix=_WORK_PREFIX, dir=parent))
    try:
        component_root = work / "component"
        component_root.mkdir()
        sources = (
            ("bin/godot.exe", executable),
            ("notices/godot/COPYRIGHT.txt", godot_copyright),
            ("notices/godot/LICENSE.txt", godot_license),
            ("notices/toqraq/LICENSE.txt", toqraq_license),
        )
        for relative_path, source in sources:
            destination = component_root.joinpath(*relative_path.split("/"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            _copy_regular_file(source, destination)

        settings = component_settings(PLUGIN_VERSION)
        fingerprint = fingerprint_staging_tree(component_root, settings.zip.content)
        candidate = work / "candidate"
        candidate.mkdir()
        package = candidate / CANDIDATE_PACKAGE_NAME
        _write_archive(package, component_root, fingerprint)
        if fingerprint_staging_tree(component_root, settings.zip.content) != fingerprint:
            raise ValueError("candidate source tree changed during archive creation")
        package_bytes, package_sha256 = _owned_file_digest(package)

        extracted = work / "extracted"
        extracted.mkdir()
        with zipfile.ZipFile(package) as archive:
            extract_zip(archive, extracted, settings.zip)
        if fingerprint_staging_tree(extracted, settings.zip.content) != fingerprint:
            raise ValueError("candidate archive does not reproduce its verified content facts")

        identity = ComponentIdentity(
            component_id=GODOT_RUNTIME_COMPONENT_ID,
            version=facts.upstream_tag,
            build_id=facts.build_id,
            platform="windows",
            architecture="x86_64",
            package_sha256=package_sha256,
        )
        provenance = candidate_provenance(
            facts,
            identity,
            fingerprint,
            package_bytes,
        )
        provenance_path = candidate / CANDIDATE_PROVENANCE_NAME
        _write_bytes(provenance_path, canonical_candidate_json(provenance))
        _, provenance_sha256 = _owned_file_digest(provenance_path)
        checksums = (
            f"{package_sha256}  {CANDIDATE_PACKAGE_NAME}\n"
            f"{provenance_sha256}  {CANDIDATE_PROVENANCE_NAME}\n"
        ).encode("ascii")
        _write_bytes(candidate / CANDIDATE_CHECKSUM_NAME, checksums)

        _discard_owned_tree(component_root, work)
        _discard_owned_tree(extracted, work)
        _publish_candidate(candidate, output)
        return output
    finally:
        if os.path.lexists(work):
            _discard_work_directory(work, parent)


def _write_archive(
    target: Path,
    component_root: Path,
    fingerprint: ComponentTreeFingerprint,
) -> None:
    """Stream fixed regular members into one metadata-stable stored ZIP."""
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        archive.comment = b""
        for value in fingerprint.files:
            info = zipfile.ZipInfo(value.relative_path, _ARCHIVE_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.create_version = 45
            info.extract_version = 45
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            info.internal_attr = 0
            info.extra = b""
            info.comment = b""
            source = component_root.joinpath(*value.relative_path.split("/"))
            with archive.open(info, "w", force_zip64=True) as output:
                _stream_fingerprinted_file(source, output, value)


def _stream_fingerprinted_file(
    source: Path,
    output: IO[bytes],
    expected: ComponentFileFingerprint,
) -> None:
    """Copy one already-fingerprinted owned file and recheck it while streaming."""
    descriptor, before = _open_regular_source(source)
    digest = hashlib.sha256()
    copied = 0
    chunk_bytes = component_settings(PLUGIN_VERSION).zip.copy_chunk_bytes
    try:
        while chunk := os.read(descriptor, chunk_bytes):
            copied += len(chunk)
            if copied > expected.size:
                raise ValueError("candidate source file grew during archive creation")
            digest.update(chunk)
            if output.write(chunk) != len(chunk):
                raise OSError("candidate archive write made incomplete progress")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        copied != expected.size
        or digest.hexdigest() != expected.sha256
        or _file_identity(before) != _file_identity(after)
    ):
        raise ValueError("candidate source file changed during archive creation")


def _copy_regular_file(source: Path, destination: Path) -> None:
    """Copy one stable unredirected input into private candidate staging."""
    descriptor, before = _open_regular_source(source)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        output = os.open(destination, flags, 0o600)
    except BaseException:
        os.close(descriptor)
        raise
    try:
        while chunk := os.read(descriptor, component_settings(PLUGIN_VERSION).zip.copy_chunk_bytes):
            offset = 0
            while offset < len(chunk):
                written = os.write(output, chunk[offset:])
                if written <= 0:
                    raise OSError("candidate staging write made no progress")
                offset += written
        after = os.fstat(descriptor)
        if _file_identity(before) != _file_identity(after):
            raise ValueError("candidate input changed while being copied")
        os.fsync(output)
    finally:
        os.close(output)
        os.close(descriptor)


def _open_regular_source(path: Path) -> tuple[int, os.stat_result]:
    """Open one exact regular source without following links or hard links."""
    absolute = Path(os.path.abspath(path))
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(absolute, flags)
    try:
        opened = os.fstat(descriptor)
        named = os.lstat(absolute)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or is_link_or_reparse(named)
            or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
        ):
            raise ValueError("candidate input must be one privately owned regular file")
        return descriptor, opened
    except BaseException:
        os.close(descriptor)
        raise


def _owned_file_digest(path: Path) -> tuple[int, str]:
    """Hash one generated private file through the production partial-file logic."""
    size = os.lstat(path).st_size
    descriptor = open_partial(path, size)
    try:
        copied, digest = hash_partial(
            descriptor,
            size,
            component_settings(PLUGIN_VERSION).download.chunk_bytes,
        )
    finally:
        os.close(descriptor)
    if copied != size:
        raise ValueError("generated candidate file changed while hashing")
    return copied, digest.hexdigest()


def _write_bytes(path: Path, content: bytes) -> None:
    """Write one new private evidence file completely and durably."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        offset = 0
        while offset < len(content):
            written = os.write(descriptor, content[offset:])
            if written <= 0:
                raise OSError("candidate evidence write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _candidate_output(path: Path) -> tuple[Path, Path]:
    """Validate a new output directory below one existing unredirected parent."""
    output = Path(os.path.abspath(path))
    parent = output.parent
    info = os.lstat(parent)
    if is_link_or_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise ValueError("candidate output parent must be an unredirected directory")
    if os.path.lexists(output):
        raise FileExistsError("candidate output already exists")
    return output, parent


def _publish_candidate(candidate: Path, output: Path) -> None:
    """Publish after bounded retries for transient Windows file locks."""
    for attempt in range(_PUBLISH_ATTEMPTS):
        if os.path.lexists(output):
            raise FileExistsError("candidate output already exists")
        try:
            candidate.rename(output)
            return
        except PermissionError as error:
            if os.path.lexists(output):
                raise FileExistsError("candidate output already exists") from error
            if attempt + 1 == _PUBLISH_ATTEMPTS:
                raise
            time.sleep(_PUBLISH_RETRY_SECONDS)


def _discard_owned_tree(path: Path, work: Path) -> None:
    """Remove one generated direct child after validating its owned boundary."""
    if path.parent != work or not path.name or is_link_or_reparse(os.lstat(path)):
        raise OSError("refusing to remove an unowned candidate work tree")
    shutil.rmtree(path)


def _discard_work_directory(path: Path, parent: Path) -> None:
    """Remove only the unique direct work directory allocated by this process."""
    info = os.lstat(path)
    if (
        path.parent != parent
        or not path.name.startswith(_WORK_PREFIX)
        or is_link_or_reparse(info)
        or not stat.S_ISDIR(info.st_mode)
    ):
        raise OSError("refusing to remove an unowned candidate work directory")
    shutil.rmtree(path)


def _file_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    """Return fields that must remain stable during one source read."""
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


def _parse_args() -> argparse.Namespace:
    """Parse the explicit candidate build evidence surface."""
    parser = argparse.ArgumentParser()
    for name in ("executable", "godot-license", "godot-copyright", "toqraq-license"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    for name in (
        "upstream-tag",
        "upstream-commit",
        "toqraq-commit",
        "module-git-tree",
        "recipe-sha256",
        "build-id",
        "distribution-id",
        "workflow-run-id",
        "runner-image",
        "runner-image-version",
        "python-version",
        "scons-version",
    ):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--workflow-run-attempt", type=int, required=True)
    parser.add_argument("--scons-argument", action="append", required=True)
    return parser.parse_args()


def main() -> int:
    """Build the candidate selected by command-line facts."""
    options = _parse_args()
    facts = GodotCandidateBuildFacts(
        upstream_tag=options.upstream_tag,
        upstream_commit=options.upstream_commit,
        toqraq_commit=options.toqraq_commit,
        module_git_tree=options.module_git_tree,
        recipe_sha256=options.recipe_sha256,
        build_id=options.build_id,
        distribution_id=options.distribution_id,
        workflow_run_id=options.workflow_run_id,
        workflow_run_attempt=options.workflow_run_attempt,
        runner_image=options.runner_image,
        runner_image_version=options.runner_image_version,
        python_version=options.python_version,
        scons_version=options.scons_version,
        scons_arguments=tuple(options.scons_argument),
    )
    package_godot_candidate(
        executable=options.executable,
        godot_license=options.godot_license,
        godot_copyright=options.godot_copyright,
        toqraq_license=options.toqraq_license,
        output_directory=options.output_directory,
        facts=facts,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
