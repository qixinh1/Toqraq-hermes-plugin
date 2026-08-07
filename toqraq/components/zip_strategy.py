"""Bounded ZIP package installation strategy for managed components."""

from __future__ import annotations

import os
import stat
import zipfile
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from threading import Event

from .archive import (
    ArchiveCancelledError,
    ArchiveProgress,
    ZipExtractionPolicy,
    extract_zip,
)
from .content_policy import ComponentContentPolicy
from .file_mode import make_component_file_executable
from .paths import is_link_or_reparse
from .release import ComponentRelease
from .strategy import (
    ComponentInstallCancelledError,
    ComponentInstallProgress,
    ComponentInstallRejectedError,
    ComponentInstallRejection,
)

ZIP_COMPONENT_STRATEGY_ID = "archive.zip"


class ZipComponentInstallStrategy:
    """Extract certified regular files while ignoring archive permissions."""

    strategy_id = ZIP_COMPONENT_STRATEGY_ID

    def __init__(self, policy: ZipExtractionPolicy) -> None:
        """Bind one explicit archive and installed-tree safety policy."""
        self._policy = policy

    @property
    def content_policy(self) -> ComponentContentPolicy:
        """Return the content policy used during extraction."""
        return self._policy.content

    def install(
        self,
        package: Path,
        staging: Path,
        release: ComponentRelease,
        *,
        cancellation: Event | None = None,
        progress: Callable[[ComponentInstallProgress], None] | None = None,
    ) -> None:
        """Extract an exact ZIP and grant execution only to declared entry points."""
        try:
            descriptor = _open_owned_package(package, release.package_bytes)
        except (OSError, ValueError) as exc:
            raise ComponentInstallRejectedError(
                ComponentInstallRejection.PACKAGE_INVALID,
                cause=exc,
            ) from exc
        try:
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = -1
                try:
                    with zipfile.ZipFile(stream) as archive:
                        extract_zip(
                            archive,
                            staging,
                            self._policy,
                            cancellation=cancellation,
                            progress=_archive_observer(progress),
                        )
                except ArchiveCancelledError as exc:
                    raise ComponentInstallCancelledError from exc
                except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
                    raise ComponentInstallRejectedError(
                        ComponentInstallRejection.CONTENT_INVALID,
                        cause=exc,
                    ) from exc
            if cancellation is not None and cancellation.is_set():
                raise ComponentInstallCancelledError
            try:
                _grant_declared_execution(staging, release, cancellation)
            except ComponentInstallCancelledError:
                raise
            except (OSError, ValueError) as exc:
                raise ComponentInstallRejectedError(
                    ComponentInstallRejection.ENTRY_POINT_INVALID,
                    cause=exc,
                ) from exc
        finally:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)


def _archive_observer(
    observer: Callable[[ComponentInstallProgress], None] | None,
) -> Callable[[ArchiveProgress], None] | None:
    """Adapt ZIP progress without leaking archive types into common jobs."""
    if observer is None:
        return None

    def notify(value: ArchiveProgress) -> None:
        observer(ComponentInstallProgress(value.completed_bytes, value.total_bytes))

    return notify


def _open_owned_package(path: Path, expected_size: int) -> int:
    """Open a regular exact-size package without following filesystem links."""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        descriptor_info = os.fstat(descriptor)
        path_info = os.lstat(path)
        if (
            not stat.S_ISREG(descriptor_info.st_mode)
            or descriptor_info.st_nlink != 1
            or is_link_or_reparse(path_info)
            or (descriptor_info.st_dev, descriptor_info.st_ino)
            != (path_info.st_dev, path_info.st_ino)
            or descriptor_info.st_size != expected_size
        ):
            raise ValueError("component package is not an owned exact-size file")
        return descriptor
    except BaseException:
        with suppress(OSError):
            os.close(descriptor)
        raise


def _grant_declared_execution(
    root: Path,
    release: ComponentRelease,
    cancellation: Event | None,
) -> None:
    """Make only certified executable entry points runnable on POSIX."""
    if os.name == "nt":
        return
    for entry in release.entry_points:
        if cancellation is not None and cancellation.is_set():
            raise ComponentInstallCancelledError
        if not entry.executable:
            continue
        path = root.joinpath(*entry.relative_path.split("/"))
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(path, flags)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("component executable entry point is not an owned file")
            make_component_file_executable(descriptor)
        finally:
            os.close(descriptor)
