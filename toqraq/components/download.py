"""Resumable bounded HTTPS acquisition of exact certified component packages."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from threading import Event

from .download_file import (
    DigestState,
    hash_partial,
    new_digest,
    open_partial,
    reset_partial,
    write_all,
)
from .download_http import (
    ComponentResponse,
    ComponentResponseMode,
    open_component_response,
    validate_component_response,
)
from .download_models import (
    ComponentDownloadCancelledError,
    ComponentDownloadPolicy,
    ComponentDownloadProgress,
    ComponentDownloadRejectedError,
    ComponentDownloadRejection,
    DownloadedComponentPackage,
)
from .layout import ComponentStoreLayout
from .mutation import ComponentMutation
from .release import ComponentRelease


class ComponentDownloader:
    """Acquire packages into the isolated store with exact digest identity."""

    def __init__(
        self,
        layout: ComponentStoreLayout,
        download_policy: ComponentDownloadPolicy,
    ) -> None:
        """Bind the explicit store and bounded network policy."""
        self._layout = layout
        self._policy = download_policy

    def download(
        self,
        release: ComponentRelease,
        mutation: ComponentMutation,
        *,
        cancellation: Event | None = None,
        progress: Callable[[ComponentDownloadProgress], None] | None = None,
        require_capacity: Callable[[int], None] | None = None,
    ) -> DownloadedComponentPackage:
        """Download or resume one package under exact mutation ownership."""
        mutation.require(release.identity)
        return self._download_owned(release, cancellation, progress, require_capacity)

    def _download_owned(
        self,
        release: ComponentRelease,
        cancellation: Event | None,
        progress: Callable[[ComponentDownloadProgress], None] | None,
        require_capacity: Callable[[int], None] | None,
    ) -> DownloadedComponentPackage:
        """Resume and verify one package while its mutation lock is held."""
        path = self._layout.download_path(release.identity)
        try:
            descriptor = open_partial(path, release.package_bytes)
        except (OSError, ValueError) as exc:
            raise ComponentDownloadRejectedError(
                ComponentDownloadRejection.FILE_INVALID,
                cause=exc,
            ) from exc
        try:
            return self._stream(
                descriptor,
                path,
                release,
                cancellation,
                progress,
                require_capacity,
            )
        finally:
            os.close(descriptor)

    def _stream(
        self,
        descriptor: int,
        path: Path,
        release: ComponentRelease,
        cancellation: Event | None,
        progress: Callable[[ComponentDownloadProgress], None] | None,
        require_capacity: Callable[[int], None] | None,
    ) -> DownloadedComponentPackage:
        """Stream the allowed response after hashing any retained prefix."""
        offset, digest = hash_partial(descriptor, release.package_bytes, self._policy.chunk_bytes)
        if offset == release.package_bytes:
            if digest.hexdigest() == release.identity.package_sha256:
                _notify(progress, offset, release.package_bytes)
                return DownloadedComponentPackage(path, offset, digest.hexdigest())
            reset_partial(descriptor)
            offset, digest = 0, new_digest()
        if cancellation is not None and cancellation.is_set():
            raise ComponentDownloadCancelledError
        if require_capacity is not None:
            require_capacity(release.package_bytes - offset)

        started = time.monotonic()
        response = open_component_response(self._policy, release, offset, started)
        try:
            offset, digest = self._consume_response(
                response,
                descriptor,
                release,
                offset,
                digest,
                started,
                cancellation,
                progress,
            )
        except BaseException:
            with suppress(OSError):
                os.fsync(descriptor)
            raise
        finally:
            response.close()
        if offset != release.package_bytes:
            raise ComponentDownloadRejectedError(ComponentDownloadRejection.SIZE_MISMATCH)
        actual_digest = digest.hexdigest()
        if actual_digest != release.identity.package_sha256:
            reset_partial(descriptor)
            raise ComponentDownloadRejectedError(ComponentDownloadRejection.DIGEST_MISMATCH)
        os.fsync(descriptor)
        return DownloadedComponentPackage(path, offset, actual_digest)

    def _consume_response(
        self,
        response: ComponentResponse,
        descriptor: int,
        release: ComponentRelease,
        offset: int,
        digest: DigestState,
        started: float,
        cancellation: Event | None,
        progress: Callable[[ComponentDownloadProgress], None] | None,
    ) -> tuple[int, DigestState]:
        """Validate response framing and append bounded bytes to the partial file."""
        mode = validate_component_response(response, offset, release.package_bytes)
        if mode is ComponentResponseMode.FULL and offset:
            reset_partial(descriptor)
            offset, digest = 0, new_digest()
        os.lseek(descriptor, offset, os.SEEK_SET)
        _notify(progress, offset, release.package_bytes)
        last_progress = time.monotonic()
        next_checkpoint = offset + self._policy.checkpoint_bytes
        while offset < release.package_bytes:
            now = time.monotonic()
            if cancellation is not None and cancellation.is_set():
                raise ComponentDownloadCancelledError
            if (
                now - started >= self._policy.total_timeout_seconds
                or now - last_progress >= self._policy.idle_timeout_seconds
            ):
                raise ComponentDownloadRejectedError(ComponentDownloadRejection.TIMEOUT)
            try:
                chunk = response.read(
                    min(self._policy.chunk_bytes, release.package_bytes - offset + 1)
                )
            except (OSError, TimeoutError) as exc:
                raise ComponentDownloadRejectedError(
                    _stream_rejection(exc),
                    cause=exc,
                ) from exc
            if not isinstance(chunk, bytes):
                raise ComponentDownloadRejectedError(ComponentDownloadRejection.RESPONSE_INVALID)
            if not chunk:
                break
            now = time.monotonic()
            if (
                now - started >= self._policy.total_timeout_seconds
                or now - last_progress >= self._policy.idle_timeout_seconds
            ):
                raise ComponentDownloadRejectedError(ComponentDownloadRejection.TIMEOUT)
            if offset + len(chunk) > release.package_bytes:
                reset_partial(descriptor)
                raise ComponentDownloadRejectedError(ComponentDownloadRejection.SIZE_MISMATCH)
            write_all(descriptor, chunk)
            digest.update(chunk)
            offset += len(chunk)
            last_progress = time.monotonic()
            if offset >= next_checkpoint:
                os.fsync(descriptor)
                next_checkpoint = offset + self._policy.checkpoint_bytes
            _notify(progress, offset, release.package_bytes)
        if offset == release.package_bytes:
            try:
                extra = response.read(1)
            except (OSError, TimeoutError) as exc:
                raise ComponentDownloadRejectedError(
                    _stream_rejection(exc),
                    cause=exc,
                ) from exc
            if not isinstance(extra, bytes):
                raise ComponentDownloadRejectedError(ComponentDownloadRejection.RESPONSE_INVALID)
            if extra:
                reset_partial(descriptor)
                raise ComponentDownloadRejectedError(ComponentDownloadRejection.SIZE_MISMATCH)
        return offset, digest


def _notify(
    progress: Callable[[ComponentDownloadProgress], None] | None,
    completed: int,
    total: int,
) -> None:
    """Publish one immutable byte snapshot when an observer exists."""
    if progress is not None:
        progress(ComponentDownloadProgress(completed, total))


def _stream_rejection(error: OSError) -> ComponentDownloadRejection:
    """Classify a bounded streaming failure."""
    if isinstance(error, TimeoutError):
        return ComponentDownloadRejection.TIMEOUT
    return ComponentDownloadRejection.TRANSPORT_FAILED
