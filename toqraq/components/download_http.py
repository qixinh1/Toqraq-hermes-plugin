"""Allow-listed urllib transport and strict component response framing."""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from contextlib import suppress
from enum import StrEnum
from typing import Any, Protocol, cast

from .download_models import (
    ComponentDownloadPolicy,
    ComponentDownloadRejectedError,
    ComponentDownloadRejection,
)
from .network import canonical_component_origin, validate_component_https_url
from .release import ComponentRelease

_CONTENT_RANGE = re.compile(r"^bytes ([0-9]+)-([0-9]+)/([0-9]+)$")


class ComponentResponseMode(StrEnum):
    """Whether the response replaces or continues the retained prefix."""

    FULL = "full"
    RESUME = "resume"


class ResponseHeaders(Protocol):
    """Response-header surface decoded at the HTTP adapter boundary."""

    def get_all(self, name: str) -> list[str] | None:
        """Return every value for one case-insensitive header."""
        ...


class ComponentResponse(Protocol):
    """Minimal urllib response surface used by the streaming adapter."""

    status: int
    headers: ResponseHeaders

    def read(self, size: int = -1) -> bytes:
        """Read at most size response bytes."""
        ...

    def geturl(self) -> str:
        """Return the final URL after redirects."""
        ...

    def close(self) -> None:
        """Close the response and transport."""
        ...


def open_component_response(
    policy: ComponentDownloadPolicy,
    release: ComponentRelease,
    offset: int,
    started: float,
) -> ComponentResponse:
    """Open one allow-listed request, restarting once after a stale range."""
    current_offset = offset
    for attempt in range(2):
        headers = {
            "Accept-Encoding": "identity",
            "User-Agent": policy.user_agent,
        }
        if current_offset:
            headers["Range"] = f"bytes={current_offset}-"
        request = urllib.request.Request(release.source.package_url, headers=headers)
        redirects = _AllowedRedirectHandler(
            frozenset(release.source.allowed_origins),
            policy.max_redirects,
        )
        opener = urllib.request.build_opener(redirects)
        remaining = policy.total_timeout_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise ComponentDownloadRejectedError(ComponentDownloadRejection.TIMEOUT)
        try:
            value: Any = opener.open(
                request,
                timeout=min(policy.io_timeout_seconds, remaining),
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 416 and current_offset and attempt == 0:
                with suppress(OSError):
                    exc.close()
                current_offset = 0
                continue
            with suppress(OSError):
                exc.close()
            raise ComponentDownloadRejectedError(
                ComponentDownloadRejection.RESPONSE_INVALID,
                cause=exc,
            ) from exc
        except ComponentDownloadRejectedError:
            raise
        except (OSError, urllib.error.URLError) as exc:
            raise ComponentDownloadRejectedError(
                _transport_rejection(exc),
                cause=exc,
            ) from exc
        response = cast(ComponentResponse, value)
        _validate_final_origin(response, release)
        return response
    raise ComponentDownloadRejectedError(ComponentDownloadRejection.RESPONSE_INVALID)


def validate_component_response(
    response: ComponentResponse,
    offset: int,
    total: int,
) -> ComponentResponseMode:
    """Validate status, encoding, length, and range framing."""
    status = response.status
    if isinstance(status, bool) or not isinstance(status, int) or status not in {200, 206}:
        raise ComponentDownloadRejectedError(ComponentDownloadRejection.RESPONSE_INVALID)
    if _single_header(response.headers, "Content-Encoding") not in {None, "identity"}:
        raise ComponentDownloadRejectedError(ComponentDownloadRejection.RESPONSE_INVALID)
    mode = ComponentResponseMode.FULL if status == 200 else ComponentResponseMode.RESUME
    framed_offset = 0 if mode is ComponentResponseMode.FULL else offset
    _validate_response_size(response.headers, mode, framed_offset, total)
    return mode


class _AllowedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject every redirect before urllib sends a request to its target."""

    def __init__(self, allowed_origins: frozenset[str], maximum_redirects: int) -> None:
        """Bind the exact certified origins and redirect count."""
        self._allowed_origins = allowed_origins
        self._maximum_redirects = maximum_redirects
        self._redirects = 0

    def redirect_request(
        self,
        request: urllib.request.Request,
        fp: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> urllib.request.Request | None:
        """Validate one target before delegating GET redirect construction."""
        try:
            validate_component_https_url(new_url)
            allowed = canonical_component_origin(new_url) in self._allowed_origins
        except ValueError as exc:
            raise ComponentDownloadRejectedError(
                ComponentDownloadRejection.ORIGIN_REJECTED,
                cause=exc,
            ) from exc
        self._redirects += 1
        if not allowed:
            raise ComponentDownloadRejectedError(ComponentDownloadRejection.ORIGIN_REJECTED)
        if self._redirects > self._maximum_redirects:
            raise ComponentDownloadRejectedError(ComponentDownloadRejection.REDIRECT_LIMIT)
        return super().redirect_request(request, fp, code, message, headers, new_url)


def _validate_final_origin(response: ComponentResponse, release: ComponentRelease) -> None:
    """Require the final response URL to remain in the certified origin set."""
    try:
        final_url = response.geturl()
        if not isinstance(final_url, str):
            raise TypeError("response URL must be text")
        origin = canonical_component_origin(final_url)
    except (TypeError, ValueError) as exc:
        response.close()
        raise ComponentDownloadRejectedError(
            ComponentDownloadRejection.ORIGIN_REJECTED,
            cause=exc,
        ) from exc
    if origin not in release.source.allowed_origins:
        response.close()
        raise ComponentDownloadRejectedError(ComponentDownloadRejection.ORIGIN_REJECTED)


def _validate_response_size(
    headers: ResponseHeaders,
    mode: ComponentResponseMode,
    offset: int,
    total: int,
) -> None:
    """Require exact Content-Length and Content-Range framing when present."""
    content_length = _single_header(headers, "Content-Length")
    if content_length is not None and (
        not content_length.isdigit() or int(content_length) != total - offset
    ):
        raise ComponentDownloadRejectedError(ComponentDownloadRejection.SIZE_MISMATCH)
    content_range = _single_header(headers, "Content-Range")
    if mode is ComponentResponseMode.FULL:
        if content_range is not None:
            raise ComponentDownloadRejectedError(ComponentDownloadRejection.RESPONSE_INVALID)
        return
    match = _CONTENT_RANGE.fullmatch(content_range or "")
    if match is None:
        raise ComponentDownloadRejectedError(ComponentDownloadRejection.RESPONSE_INVALID)
    start, end, declared_total = (int(value) for value in match.groups())
    if start != offset or end != total - 1 or declared_total != total:
        raise ComponentDownloadRejectedError(ComponentDownloadRejection.SIZE_MISMATCH)


def _single_header(headers: ResponseHeaders, name: str) -> str | None:
    """Return one bounded canonical header value or reject duplicates."""
    values = headers.get_all(name)
    if values is None:
        return None
    if len(values) != 1 or not isinstance(values[0], str) or len(values[0]) > 128:
        raise ComponentDownloadRejectedError(ComponentDownloadRejection.RESPONSE_INVALID)
    return values[0].strip().lower()


def _transport_rejection(
    error: OSError | urllib.error.URLError,
) -> ComponentDownloadRejection:
    """Classify direct and urllib-wrapped timeouts without exposing details."""
    reason = error.reason if isinstance(error, urllib.error.URLError) else error
    if isinstance(reason, TimeoutError):
        return ComponentDownloadRejection.TIMEOUT
    return ComponentDownloadRejection.TRANSPORT_FAILED
