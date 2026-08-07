"""Private deterministic filesystem layout for managed components."""

from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .identity import component_identity_key
from .paths import is_link_or_reparse
from .release import ComponentIdentity


class ComponentStoreLayoutError(ValueError):
    """The configured component store is not a private directory tree."""


@dataclass(frozen=True, slots=True)
class ComponentStoreLayout:
    """All process-wide Toqraq component paths under one explicit root."""

    root: Path

    def __post_init__(self) -> None:
        """Require an absolute root and retain its normalized spelling."""
        if not self.root.is_absolute():
            raise ComponentStoreLayoutError("component store root must be absolute")
        object.__setattr__(self, "root", Path(os.path.abspath(self.root)))

    @property
    def components(self) -> Path:
        """Return the atomically published installation directory."""
        return self.root / "components"

    @property
    def downloads(self) -> Path:
        """Return the resumable package-download directory."""
        return self.root / "downloads"

    @property
    def staging(self) -> Path:
        """Return the private same-filesystem preparation directory."""
        return self.root / "staging"

    @property
    def locks(self) -> Path:
        """Return the cross-process mutation-lock directory."""
        return self.root / "locks"

    @property
    def logs(self) -> Path:
        """Return the bounded component-operation diagnostics directory."""
        return self.root / "logs"

    def initialize(self) -> None:
        """Create or revalidate every private directory idempotently."""
        _ensure_private_directory(self.root, parents=True)
        for directory in (
            self.components,
            self.downloads,
            self.staging,
            self.locks,
            self.logs,
        ):
            _ensure_private_directory(directory, parents=False)

    def component_path(self, identity: ComponentIdentity) -> Path:
        """Return the exact published destination for an identity."""
        return self.components / component_identity_key(identity)

    def download_path(self, identity: ComponentIdentity) -> Path:
        """Return the stable resumable package path for an identity."""
        return self.downloads / f"{component_identity_key(identity)}.download"

    def lock_path(self, identity: ComponentIdentity) -> Path:
        """Return the stable mutation lock path for an identity."""
        return self.locks / f"{component_identity_key(identity)}.lock"

    def create_staging(self, identity: ComponentIdentity) -> Path:
        """Create one unique private staging directory on the store filesystem."""
        _require_private_directory(self.staging)
        key = component_identity_key(identity)
        created = Path(tempfile.mkdtemp(prefix=f"{key}.", dir=self.staging))
        _require_private_directory(created)
        return created


def _ensure_private_directory(path: Path, *, parents: bool) -> None:
    """Create and constrain one Toqraq-owned directory."""
    try:
        path.mkdir(mode=0o700, parents=parents, exist_ok=True)
    except OSError as exc:
        raise ComponentStoreLayoutError("component store directory is unavailable") from exc
    _require_private_directory(path)
    if os.name != "nt":
        path.chmod(0o700)


def _require_private_directory(path: Path) -> None:
    """Reject a missing, redirected, or non-directory store path."""
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise ComponentStoreLayoutError("component store directory is unavailable") from exc
    if is_link_or_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise ComponentStoreLayoutError("component store directory is redirected or invalid")
