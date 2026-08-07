"""Strictly verify and extract one published Godot candidate directory."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path

from scripts.godot_candidate_evidence import (
    CANDIDATE_CHECKSUM_NAME,
    CANDIDATE_PACKAGE_NAME,
    CANDIDATE_PROVENANCE_NAME,
    CANDIDATE_SCHEMA,
    GodotCandidateBuildFacts,
    candidate_provenance,
    canonical_candidate_json,
)
from toqraq.components.archive import extract_zip
from toqraq.components.content import fingerprint_staging_tree
from toqraq.components.download_file import hash_partial
from toqraq.components.paths import is_link_or_reparse
from toqraq.components.release import MAX_COMPONENT_PACKAGE_BYTES, ComponentIdentity
from toqraq.components.settings import component_settings
from toqraq.engines.godot.identity import GODOT_RUNTIME_COMPONENT_ID
from toqraq.version import PLUGIN_VERSION

_MAX_PROVENANCE_BYTES = 64 << 10
_MAX_CHECKSUM_BYTES = 512
_CANDIDATE_NAMES = frozenset(
    (CANDIDATE_PACKAGE_NAME, CANDIDATE_PROVENANCE_NAME, CANDIDATE_CHECKSUM_NAME)
)


@dataclass(frozen=True, slots=True)
class VerifiedGodotCandidate:
    """Exact identity and executable extracted from one verified candidate."""

    identity: ComponentIdentity
    executable: Path
    package_bytes: int
    expected_tree_sha256: str


def verify_godot_candidate(
    candidate_directory: Path,
    extraction_directory: Path,
) -> VerifiedGodotCandidate:
    """Verify canonical evidence and extract the exact candidate package."""
    root = _candidate_root(candidate_directory)
    provenance_bytes = _read_regular(
        root / CANDIDATE_PROVENANCE_NAME,
        _MAX_PROVENANCE_BYTES,
    )
    decoded = _decode_provenance(provenance_bytes)
    facts = _build_facts(decoded)
    component = _mapping(decoded["component"], "component")
    identity = ComponentIdentity.model_validate(component["identity"])
    _require_candidate_identity(identity, facts)

    settings = component_settings(PLUGIN_VERSION)
    package = root / CANDIDATE_PACKAGE_NAME
    descriptor, package_info = _open_regular(package, MAX_COMPONENT_PACKAGE_BYTES)
    try:
        package_bytes, digest = hash_partial(
            descriptor,
            package_info.st_size,
            settings.download.chunk_bytes,
        )
        package_sha256 = digest.hexdigest()
        if identity.package_sha256 != package_sha256:
            raise ValueError("candidate package digest does not match its identity")
        checksum = _read_regular(root / CANDIDATE_CHECKSUM_NAME, _MAX_CHECKSUM_BYTES)
        expected_checksum = (
            f"{package_sha256}  {CANDIDATE_PACKAGE_NAME}\n"
            f"{hashlib.sha256(provenance_bytes).hexdigest()}  {CANDIDATE_PROVENANCE_NAME}\n"
        ).encode("ascii")
        if checksum != expected_checksum:
            raise ValueError("candidate checksum file is not canonical")
        with (
            os.fdopen(os.dup(descriptor), "rb") as package_stream,
            zipfile.ZipFile(package_stream) as archive,
        ):
            extract_zip(archive, extraction_directory, settings.zip)
        _require_unchanged(descriptor, package_info)
    finally:
        os.close(descriptor)

    fingerprint = fingerprint_staging_tree(extraction_directory, settings.zip.content)
    expected = candidate_provenance(facts, identity, fingerprint, package_bytes)
    if decoded != expected or provenance_bytes != canonical_candidate_json(expected):
        raise ValueError("candidate provenance does not equal the verified package facts")
    _require_candidate_names(root)

    return VerifiedGodotCandidate(
        identity=identity,
        executable=extraction_directory / "bin" / "godot.exe",
        package_bytes=package_bytes,
        expected_tree_sha256=fingerprint.tree_sha256,
    )


def _candidate_root(path: Path) -> Path:
    """Require one unredirected directory containing only candidate outputs."""
    root = Path(os.path.abspath(path))
    info = os.lstat(root)
    if is_link_or_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise ValueError("candidate root must be an unredirected directory")
    _require_candidate_names(root)
    return root


def _require_candidate_names(root: Path) -> None:
    """Require the candidate namespace to remain exact during verification."""
    with os.scandir(root) as entries:
        names = frozenset(entry.name for entry in entries)
    if names != _CANDIDATE_NAMES:
        raise ValueError("candidate directory contents are not exact")


def _read_regular(path: Path, maximum_bytes: int) -> bytes:
    """Read one bounded privately owned evidence file without following links."""
    descriptor, before = _open_regular(path, maximum_bytes)
    try:
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(descriptor, min(remaining, 64 << 10))
            if not chunk:
                raise ValueError("candidate evidence ended before its declared size")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise ValueError("candidate evidence grew while being read")
        _require_unchanged(descriptor, before)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _open_regular(path: Path, maximum_bytes: int) -> tuple[int, os.stat_result]:
    """Open one exact bounded regular file and retain its stable identity."""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        named = os.lstat(path)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or is_link_or_reparse(named)
            or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
            or not 0 <= opened.st_size <= maximum_bytes
        ):
            raise ValueError("candidate file must be one bounded privately owned regular file")
        return descriptor, opened
    except BaseException:
        os.close(descriptor)
        raise


def _require_unchanged(descriptor: int, before: os.stat_result) -> None:
    """Reject a candidate file that changed while its descriptor was consumed."""
    after = os.fstat(descriptor)
    if _file_identity(before) != _file_identity(after):
        raise ValueError("candidate file changed while being verified")


def _decode_provenance(content: bytes) -> dict[str, object]:
    """Decode bounded UTF-8 JSON and reject duplicate or unknown root fields."""
    try:
        decoded: object = json.loads(
            content.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("candidate provenance is not strict UTF-8 JSON") from exc
    root = _mapping(decoded, "provenance")
    if set(root) != {"schema", "source", "build", "component", "runtime_contract"}:
        raise ValueError("candidate provenance root fields are not exact")
    if root["schema"] != CANDIDATE_SCHEMA:
        raise ValueError("candidate provenance schema is not exact")
    return root


def _build_facts(provenance: dict[str, object]) -> GodotCandidateBuildFacts:
    """Convert the external source and build objects into validated facts."""
    source = _exact_mapping(
        provenance["source"],
        "source",
        {
            "upstream_repository",
            "upstream_tag",
            "upstream_commit",
            "toqraq_commit",
            "module_git_tree",
        },
    )
    build = _exact_mapping(
        provenance["build"],
        "build",
        {
            "recipe_sha256",
            "scons_arguments",
            "workflow_run_id",
            "workflow_run_attempt",
            "environment",
        },
    )
    environment = _exact_mapping(
        build["environment"],
        "environment",
        {"runner_image", "runner_image_version", "python_version", "scons_version"},
    )
    arguments = _string_tuple(build["scons_arguments"], "SCons arguments")
    if len(arguments) < 2:
        raise ValueError("candidate provenance omits intrinsic SCons arguments")
    base_arguments = arguments[:-2]
    build_id = _argument_value(
        arguments[-2],
        "toqraq_build_id=",
        "embedded build argument",
    )
    distribution_id = _argument_value(
        arguments[-1],
        "toqraq_distribution_id=",
        "distribution build argument",
    )
    return GodotCandidateBuildFacts(
        upstream_tag=_string(source["upstream_tag"], "upstream tag"),
        upstream_commit=_string(source["upstream_commit"], "upstream commit"),
        toqraq_commit=_string(source["toqraq_commit"], "Toqraq commit"),
        module_git_tree=_string(source["module_git_tree"], "module tree"),
        recipe_sha256=_string(build["recipe_sha256"], "recipe digest"),
        build_id=build_id,
        distribution_id=distribution_id,
        workflow_run_id=_string(build["workflow_run_id"], "workflow run ID"),
        workflow_run_attempt=_integer(build["workflow_run_attempt"], "workflow run attempt"),
        runner_image=_string(environment["runner_image"], "runner image"),
        runner_image_version=_string(environment["runner_image_version"], "runner image version"),
        python_version=_string(environment["python_version"], "Python version"),
        scons_version=_string(environment["scons_version"], "SCons version"),
        scons_arguments=base_arguments,
    )


def _require_candidate_identity(
    identity: ComponentIdentity,
    facts: GodotCandidateBuildFacts,
) -> None:
    """Bind the package identity to the exact reviewed Godot contribution."""
    if (
        identity.component_id != GODOT_RUNTIME_COMPONENT_ID
        or identity.version != facts.upstream_tag
        or identity.build_id != facts.build_id
        or identity.platform != "windows"
        or identity.architecture != "x86_64"
    ):
        raise ValueError("candidate component identity is not exact")


def _exact_mapping(
    value: object,
    label: str,
    keys: set[str],
) -> dict[str, object]:
    """Require one JSON object with the exact named fields."""
    result = _mapping(value, label)
    if set(result) != keys:
        raise ValueError(f"candidate {label} fields are not exact")
    return result


def _mapping(value: object, label: str) -> dict[str, object]:
    """Convert one decoded JSON mapping without retaining unknown key types."""
    if not isinstance(value, dict):
        raise ValueError(f"candidate {label} must be an object")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"candidate {label} field name is invalid")
        result[key] = item
    return result


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON object names during the external decode."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("candidate provenance contains a duplicate field")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    """Reject non-standard NaN and infinity tokens."""
    raise ValueError(f"candidate provenance contains invalid constant {value!r}")


def _string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"candidate {label} must be a string")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"candidate {label} must be an integer")
    return value


def _argument_value(argument: str, prefix: str, label: str) -> str:
    if not argument.startswith(prefix) or len(argument) == len(prefix):
        raise ValueError(f"candidate {label} is invalid")
    return argument[len(prefix) :]


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"candidate {label} must be a string array")
    return tuple(value)


def _file_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns
