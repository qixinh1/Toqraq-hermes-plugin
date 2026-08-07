"""Installed component manifest creation, persistence, and verification."""

from __future__ import annotations

import os
import stat
from contextlib import suppress
from enum import StrEnum
from pathlib import Path
from threading import Event
from typing import Annotated, Self

from pydantic import Field, ValidationError, model_validator

from .content import (
    COMPONENT_MANIFEST_NAME,
    ComponentTreeFingerprint,
    component_tree_digest,
    fingerprint_published_tree,
)
from .content_policy import ComponentContentPolicy
from .identity import component_identity_key
from .json_file import read_bounded_json_object
from .paths import ComponentPathConflictError, ComponentPathNamespace, is_link_or_reparse
from .release import (
    MAX_COMPONENT_INSTALLED_BYTES,
    ComponentRecord,
    ComponentRelease,
    RelativeInstallPath,
    Sha256,
)

MAX_COMPONENT_MANIFEST_BYTES = 64 << 20
MAX_COMPONENT_MANIFEST_FILES = 200_000


class ComponentManifestRejection(StrEnum):
    """Stable reasons an installation manifest cannot be trusted."""

    ROOT_INVALID = "root_invalid"
    MANIFEST_EXISTS = "manifest_exists"
    MANIFEST_INVALID = "manifest_invalid"
    CONTENT_MISMATCH = "content_mismatch"


class ComponentManifestRejectedError(ValueError):
    """Installed metadata or content differs from its certified release."""

    def __init__(
        self,
        reason: ComponentManifestRejection,
        *,
        cause: BaseException | None = None,
    ) -> None:
        """Retain a stable reason and private diagnostic cause."""
        self.reason = reason
        self.cause = cause
        super().__init__(f"component manifest rejected: {reason.value}")


class ComponentManifestFile(ComponentRecord):
    """One regular file recorded in a published component."""

    relative_path: RelativeInstallPath
    size: Annotated[int, Field(ge=0, le=MAX_COMPONENT_INSTALLED_BYTES)]
    sha256: Sha256


class ComponentManifest(ComponentRecord):
    """Strict self-describing receipt written last before publication."""

    manifest_version: Annotated[int, Field(ge=1, le=1)]
    release: ComponentRelease
    identity_key: Sha256
    tree_sha256: Sha256
    total_bytes: Annotated[int, Field(ge=0, le=MAX_COMPONENT_INSTALLED_BYTES)]
    files: tuple[ComponentManifestFile, ...] = Field(max_length=MAX_COMPONENT_MANIFEST_FILES)

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        """Require the receipt, release, and canonical file list to agree."""
        if self.identity_key != component_identity_key(self.release.identity):
            raise ValueError("component identity key does not match its release")
        if self.tree_sha256 != self.release.expected_tree_sha256:
            raise ValueError("component tree digest is not the certified digest")
        if self.total_bytes != self.release.installed_bytes:
            raise ValueError("component installed size does not match its release")
        if self.total_bytes != sum(file.size for file in self.files):
            raise ValueError("component total byte count does not match its files")
        paths = tuple(file.relative_path for file in self.files)
        if paths != tuple(sorted(paths, key=lambda path: path.encode("utf-8"))):
            raise ValueError("component manifest files are not canonically ordered")
        namespace = ComponentPathNamespace()
        namespace.add((COMPONENT_MANIFEST_NAME,), is_directory=False)
        try:
            for path in paths:
                namespace.add(tuple(path.split("/")), is_directory=False)
        except ComponentPathConflictError as exc:
            raise ValueError("component manifest contains conflicting paths") from exc
        if component_tree_digest(self.files) != self.tree_sha256:
            raise ValueError("component manifest digest does not match its files")
        available = set(paths)
        if any(entry.relative_path not in available for entry in self.release.entry_points):
            raise ValueError("component entry point is absent from its file manifest")
        return self


def create_component_manifest(
    release: ComponentRelease,
    fingerprint: ComponentTreeFingerprint,
) -> ComponentManifest:
    """Create a receipt only when staging matches the certified tree."""
    if (
        fingerprint.tree_sha256 != release.expected_tree_sha256
        or fingerprint.total_bytes != release.installed_bytes
    ):
        raise ComponentManifestRejectedError(ComponentManifestRejection.CONTENT_MISMATCH)
    try:
        return ComponentManifest(
            manifest_version=1,
            release=release,
            identity_key=component_identity_key(release.identity),
            tree_sha256=fingerprint.tree_sha256,
            total_bytes=fingerprint.total_bytes,
            files=tuple(
                ComponentManifestFile(
                    relative_path=file.relative_path,
                    size=file.size,
                    sha256=file.sha256,
                )
                for file in fingerprint.files
            ),
        )
    except ValidationError as exc:
        raise ComponentManifestRejectedError(
            ComponentManifestRejection.MANIFEST_INVALID,
            cause=exc,
        ) from exc


def write_component_manifest(root: Path, manifest: ComponentManifest) -> None:
    """Create and durably flush `component.json` without replacing anything."""
    absolute = _component_root(root)
    content = (manifest.model_dump_json(indent=2) + "\n").encode("utf-8")
    if len(content) > MAX_COMPONENT_MANIFEST_BYTES:
        raise ComponentManifestRejectedError(ComponentManifestRejection.MANIFEST_INVALID)
    target = absolute / COMPONENT_MANIFEST_NAME
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags, 0o600)
    except FileExistsError as exc:
        raise ComponentManifestRejectedError(
            ComponentManifestRejection.MANIFEST_EXISTS,
            cause=exc,
        ) from exc
    try:
        offset = 0
        while offset < len(content):
            written = os.write(descriptor, content[offset:])
            if written <= 0:
                raise OSError("component manifest write made no progress")
            offset += written
        os.fsync(descriptor)
    except BaseException:
        with suppress(OSError):
            os.close(descriptor)
        with suppress(OSError):
            target.unlink()
        raise
    else:
        os.close(descriptor)


def read_component_manifest(root: Path) -> ComponentManifest:
    """Read and validate installed metadata without hashing component content."""
    absolute = _component_root(root)
    target = absolute / COMPONENT_MANIFEST_NAME
    try:
        info = os.lstat(target)
        if is_link_or_reparse(info) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("component manifest is not an owned regular file")
        content = read_bounded_json_object(target, maximum_bytes=MAX_COMPONENT_MANIFEST_BYTES)
        manifest: ComponentManifest = ComponentManifest.model_validate_json(content)
        return manifest
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError, ValidationError) as exc:
        raise ComponentManifestRejectedError(
            ComponentManifestRejection.MANIFEST_INVALID,
            cause=exc,
        ) from exc


def verify_component_installation(
    root: Path,
    release: ComponentRelease,
    policy: ComponentContentPolicy,
    *,
    cancellation: Event | None = None,
) -> ComponentManifest:
    """Rehash a published tree and require the exact certified release."""
    manifest = read_component_manifest(root)
    if manifest.release != release:
        raise ComponentManifestRejectedError(ComponentManifestRejection.CONTENT_MISMATCH)
    try:
        fingerprint = fingerprint_published_tree(
            root,
            policy,
            cancellation=cancellation,
        )
    except ValueError as exc:
        raise ComponentManifestRejectedError(
            ComponentManifestRejection.CONTENT_MISMATCH,
            cause=exc,
        ) from exc
    expected_files = tuple((file.relative_path, file.size, file.sha256) for file in manifest.files)
    actual_files = tuple((file.relative_path, file.size, file.sha256) for file in fingerprint.files)
    if (
        fingerprint.tree_sha256 != release.expected_tree_sha256
        or fingerprint.total_bytes != manifest.total_bytes
        or actual_files != expected_files
        or not _entry_points_are_usable(root, release)
    ):
        raise ComponentManifestRejectedError(ComponentManifestRejection.CONTENT_MISMATCH)
    return manifest


def _entry_points_are_usable(root: Path, release: ComponentRelease) -> bool:
    """Return whether every certified entry point is still an owned usable file."""
    absolute = Path(os.path.abspath(root))
    for entry in release.entry_points:
        path = absolute.joinpath(*entry.relative_path.split("/"))
        try:
            info = os.lstat(path)
        except OSError:
            return False
        if (
            is_link_or_reparse(info)
            or not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or (entry.executable and os.name != "nt" and not info.st_mode & stat.S_IXUSR)
        ):
            return False
    return True


def _component_root(root: Path) -> Path:
    """Return one unredirected component directory."""
    absolute = Path(os.path.abspath(root))
    try:
        info = os.lstat(absolute)
    except OSError as exc:
        raise ComponentManifestRejectedError(
            ComponentManifestRejection.ROOT_INVALID,
            cause=exc,
        ) from exc
    if is_link_or_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise ComponentManifestRejectedError(ComponentManifestRejection.ROOT_INVALID)
    return absolute
