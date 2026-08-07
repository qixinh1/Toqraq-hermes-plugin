"""Atomic publication and lookup of exact verified component installations."""

from __future__ import annotations

import logging
import os
import stat
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Event

from ..core.component import ComponentReadiness
from . import lease as component_lease
from .content import (
    ComponentTreeCancelledError,
    ComponentTreeProgress,
    fingerprint_staging_tree,
)
from .content_policy import ComponentContentPolicy
from .download_file import unlink_download_cache
from .identity import component_identity_key
from .layout import ComponentStoreLayout
from .lock import ComponentLockPolicy
from .manifest import (
    ComponentManifest,
    ComponentManifestRejectedError,
    create_component_manifest,
    read_component_manifest,
    verify_component_installation,
    write_component_manifest,
)
from .mutation import ComponentMutation
from .paths import is_link_or_reparse
from .release import ComponentIdentity, ComponentRelease
from .staging import discard_component_staging

logger = logging.getLogger(__name__)


class ComponentStoreRejection(StrEnum):
    """Stable reasons a store operation cannot complete."""

    STAGING_INVALID = "staging_invalid"
    PUBLICATION_FAILED = "publication_failed"
    INSTALLATION_INVALID = "installation_invalid"
    ENTRY_POINT_MISSING = "entry_point_missing"
    LEASE_FAILED = "lease_failed"
    COMPONENT_IN_USE = "component_in_use"
    REMOVAL_FAILED = "removal_failed"


class ComponentStoreRejectedError(ValueError):
    """A component store operation violated identity or publication policy."""

    def __init__(
        self,
        reason: ComponentStoreRejection,
        *,
        cause: BaseException | None = None,
    ) -> None:
        """Retain one stable reason and a private diagnostic cause."""
        self.reason = reason
        self.cause = cause
        super().__init__(f"component store rejected: {reason.value}")


class ComponentStoreCancelledError(Exception):
    """The owning component operation cancelled before publication committed."""


@dataclass(frozen=True, slots=True)
class ComponentInstallation:
    """One exact verified component root and immutable local receipt."""

    root: Path
    manifest: ComponentManifest

    def entry_point(self, name: str) -> Path:
        """Resolve one certified named entry point without guessing a file."""
        entry = next(
            (
                candidate
                for candidate in self.manifest.release.entry_points
                if candidate.name == name
            ),
            None,
        )
        if entry is None:
            raise ComponentStoreRejectedError(ComponentStoreRejection.ENTRY_POINT_MISSING)
        path = self.root.joinpath(*entry.relative_path.split("/"))
        try:
            info = os.lstat(path)
        except OSError as exc:
            raise ComponentStoreRejectedError(
                ComponentStoreRejection.ENTRY_POINT_MISSING,
                cause=exc,
            ) from exc
        if (
            is_link_or_reparse(info)
            or not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or (entry.executable and os.name != "nt" and not info.st_mode & stat.S_IXUSR)
        ):
            raise ComponentStoreRejectedError(ComponentStoreRejection.ENTRY_POINT_MISSING)
        return path


class ComponentStore:
    """Process-local facade over one isolated component filesystem tree."""

    def __init__(
        self,
        layout: ComponentStoreLayout,
        lock_policy: ComponentLockPolicy,
    ) -> None:
        """Bind explicit layout and cross-process wait policy."""
        self._layout = layout
        self._lock_policy = lock_policy

    def initialize(self) -> None:
        """Create or revalidate the store layout."""
        self._layout.initialize()

    def find(
        self,
        release: ComponentRelease,
        policy: ComponentContentPolicy,
        *,
        cancellation: Event | None = None,
    ) -> ComponentInstallation | None:
        """Return an exact verified installation or None for absent/invalid state."""
        destination = self._layout.component_path(release.identity)
        if not os.path.lexists(destination):
            return None
        try:
            manifest = verify_component_installation(
                destination,
                release,
                policy,
                cancellation=cancellation,
            )
        except (OSError, ComponentManifestRejectedError):
            return None
        return ComponentInstallation(destination, manifest)

    def readiness(
        self,
        release: ComponentRelease,
        policy: ComponentContentPolicy,
    ) -> ComponentReadiness:
        """Classify absence separately from an existing unverified installation."""
        destination = self._layout.component_path(release.identity)
        if not os.path.lexists(destination):
            return ComponentReadiness.MISSING
        if self.find(release, policy) is None:
            return ComponentReadiness.INVALID
        return ComponentReadiness.READY

    def require(
        self,
        release: ComponentRelease,
        policy: ComponentContentPolicy,
        *,
        cancellation: Event | None = None,
    ) -> ComponentInstallation:
        """Return an exact installation or a stable invalid-state failure."""
        _require_not_cancelled(cancellation)
        installation = self.find(release, policy, cancellation=cancellation)
        if installation is None:
            raise ComponentStoreRejectedError(ComponentStoreRejection.INSTALLATION_INVALID)
        return installation

    def publish_staging(
        self,
        staging: Path,
        release: ComponentRelease,
        policy: ComponentContentPolicy,
        mutation: ComponentMutation,
        *,
        cancellation: Event | None = None,
        progress: Callable[[ComponentTreeProgress], None] | None = None,
    ) -> ComponentInstallation:
        """Verify and atomically publish one complete component staging tree."""
        mutation.require(release.identity)
        _require_not_cancelled(cancellation)
        self._require_owned_staging(staging, release)
        try:
            fingerprint = fingerprint_staging_tree(
                staging,
                policy,
                cancellation=cancellation,
                progress=progress,
            )
            manifest = create_component_manifest(release, fingerprint)
            write_component_manifest(staging, manifest)
            if read_component_manifest(staging) != manifest:
                raise ValueError("persisted component manifest changed")
        except ComponentTreeCancelledError as exc:
            raise ComponentStoreCancelledError from exc
        except (OSError, ValueError) as exc:
            raise ComponentStoreRejectedError(
                ComponentStoreRejection.STAGING_INVALID,
                cause=exc,
            ) from exc

        _require_not_cancelled(cancellation)
        return self._publish_owned(staging, release, policy, manifest, cancellation)

    def acquire_lease(
        self,
        installation: ComponentInstallation,
        mutation: ComponentMutation,
        *,
        cancellation: Event | None = None,
    ) -> component_lease.ComponentLease[ComponentInstallation]:
        """Lease one already-verified installation against concurrent removal."""
        release = installation.manifest.release
        mutation.require(release.identity)
        if installation.root != self._layout.component_path(release.identity):
            raise ComponentStoreRejectedError(ComponentStoreRejection.INSTALLATION_INVALID)
        _require_not_cancelled(cancellation)
        key = component_identity_key(release.identity)
        try:
            return component_lease.acquire_component_lease(
                installation,
                self._layout.locks,
                key,
                self._lock_policy,
                cancellation=cancellation,
            )
        except component_lease.ComponentLeaseAllocationError as exc:
            raise ComponentStoreRejectedError(ComponentStoreRejection.LEASE_FAILED) from exc

    def is_leased(self, release: ComponentRelease) -> bool:
        """Return whether an exact release has at least one live process lease."""
        key = component_identity_key(release.identity)
        try:
            return (
                component_lease.active_component_lease_count(
                    self._layout.locks,
                    key,
                    self._lock_policy,
                )
                > 0
            )
        except (OSError, ValueError) as exc:
            raise ComponentStoreRejectedError(
                ComponentStoreRejection.LEASE_FAILED,
                cause=exc,
            ) from exc

    def remove(
        self,
        identity: ComponentIdentity,
        mutation: ComponentMutation,
        *,
        cancellation: Event | None = None,
    ) -> bool:
        """Atomically unpublish an installation and reclaim its package cache."""
        mutation.require(identity)
        key = component_identity_key(identity)
        try:
            active = component_lease.active_component_lease_count(
                self._layout.locks,
                key,
                self._lock_policy,
            )
        except (OSError, ValueError) as exc:
            raise ComponentStoreRejectedError(
                ComponentStoreRejection.LEASE_FAILED,
                cause=exc,
            ) from exc
        if active:
            raise ComponentStoreRejectedError(ComponentStoreRejection.COMPONENT_IN_USE)
        destination = self._layout.component_path(identity)
        _require_not_cancelled(cancellation)
        if not os.path.lexists(destination):
            self._remove_uncommitted_download(identity, key)
            return False
        discarded = self._layout.staging / f"{key}.discard.{uuid.uuid4().hex}"
        try:
            destination.rename(discarded)
        except OSError as exc:
            raise ComponentStoreRejectedError(
                ComponentStoreRejection.REMOVAL_FAILED,
                cause=exc,
            ) from exc
        _observe_commit_flush(self._layout.components, key)
        discard_component_staging(discarded, self._layout.staging, key)
        self._remove_committed_download(identity, key)
        return True

    def _publish_owned(
        self,
        staging: Path,
        release: ComponentRelease,
        policy: ComponentContentPolicy,
        manifest: ComponentManifest,
        cancellation: Event | None,
    ) -> ComponentInstallation:
        """Settle one verified staging tree while holding its identity lock."""
        destination = self._layout.component_path(release.identity)
        key = component_identity_key(release.identity)
        discarded: Path | None = None
        if os.path.lexists(destination):
            existing = self.find(release, policy)
            if existing is not None:
                discard_component_staging(staging, self._layout.staging, key)
                return existing
            discarded = self._layout.staging / f"{key}.discard.{uuid.uuid4().hex}"
            _require_not_cancelled(cancellation)
            try:
                destination.rename(discarded)
            except OSError as exc:
                raise ComponentStoreRejectedError(
                    ComponentStoreRejection.PUBLICATION_FAILED,
                    cause=exc,
                ) from exc
        else:
            _require_not_cancelled(cancellation)
        try:
            staging.rename(destination)
        except OSError as exc:
            raise ComponentStoreRejectedError(
                ComponentStoreRejection.PUBLICATION_FAILED,
                cause=exc,
            ) from exc
        _observe_commit_flush(self._layout.components, key)
        if discarded is not None:
            discard_component_staging(discarded, self._layout.staging, key)
        return ComponentInstallation(destination, manifest)

    def _remove_uncommitted_download(
        self,
        identity: ComponentIdentity,
        identity_key: str,
    ) -> None:
        """Remove a cache when no installation commit constrains failure reporting."""
        try:
            removed = unlink_download_cache(
                self._layout.download_path(identity),
                self._layout.downloads,
            )
        except OSError as exc:
            raise ComponentStoreRejectedError(
                ComponentStoreRejection.REMOVAL_FAILED,
                cause=exc,
            ) from exc
        if removed:
            _observe_commit_flush(self._layout.downloads, identity_key)

    def _remove_committed_download(
        self,
        identity: ComponentIdentity,
        identity_key: str,
    ) -> None:
        """Best-effort cache cleanup after installation removal has committed."""
        try:
            removed = unlink_download_cache(
                self._layout.download_path(identity),
                self._layout.downloads,
            )
        except OSError as exc:
            logger.warning(
                "component download cleanup deferred identity_key=%s exception_type=%s",
                identity_key,
                type(exc).__name__,
            )
            return
        if removed:
            _observe_commit_flush(self._layout.downloads, identity_key)

    def _require_owned_staging(self, staging: Path, release: ComponentRelease) -> None:
        """Require one direct unique staging directory for the exact identity."""
        expected_parent = self._layout.staging.resolve(strict=True)
        candidate = Path(os.path.abspath(staging))
        try:
            info = os.lstat(candidate)
            parent = candidate.parent.resolve(strict=True)
        except OSError as exc:
            raise ComponentStoreRejectedError(
                ComponentStoreRejection.STAGING_INVALID,
                cause=exc,
            ) from exc
        prefix = component_identity_key(release.identity) + "."
        if (
            parent != expected_parent
            or not candidate.name.startswith(prefix)
            or is_link_or_reparse(info)
            or not stat.S_ISDIR(info.st_mode)
        ):
            raise ComponentStoreRejectedError(ComponentStoreRejection.STAGING_INVALID)


def _require_not_cancelled(cancellation: Event | None) -> None:
    """Stop before the publication transaction crosses its commit boundary."""
    if cancellation is not None and cancellation.is_set():
        raise ComponentStoreCancelledError


def _observe_commit_flush(path: Path, identity_key: str) -> None:
    """Observe durability failure without contradicting an irreversible commit."""
    try:
        _flush_directory(path)
    except OSError as exc:
        logger.warning(
            "component commit flush deferred identity_key=%s exception_type=%s",
            identity_key,
            type(exc).__name__,
        )


def _flush_directory(path: Path) -> None:
    """Durably record a publication rename where directory fsync is available."""
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
