"""Canonical HTTPS URL and origin policy for managed component sources."""

from __future__ import annotations

import re
import urllib.parse

_DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def validate_component_https_url(value: str) -> str:
    """Validate a bounded HTTPS URL without credentials or fragments."""
    if (
        not value
        or len(value) > 2_048
        or "\\" in value
        or any(ord(character) <= 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError("component URL contains an unsafe character")
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError("component URL must be HTTPS without credentials or fragment")
    _canonical_host(parsed.hostname)
    _validated_port(parsed)
    return value


def canonical_component_origin(value: str) -> str:
    """Return the canonical HTTPS origin of a validated component URL."""
    validate_component_https_url(value)
    parsed = urllib.parse.urlsplit(value)
    host = _canonical_host(parsed.hostname or "")
    port = _validated_port(parsed)
    return f"https://{host}" if port in {None, 443} else f"https://{host}:{port}"


def canonical_allowed_origin(value: str) -> str:
    """Validate and canonicalize one origin-only allow-list entry."""
    validate_component_https_url(value)
    parsed = urllib.parse.urlsplit(value)
    if parsed.path not in {"", "/"} or parsed.query:
        raise ValueError("allowed component origin must not contain a path or query")
    return canonical_component_origin(value)


def _canonical_host(value: str) -> str:
    """Return a canonical ASCII DNS host or reject it."""
    host = value.lower()
    labels = host.split(".")
    if (
        len(host) > 253
        or not labels
        or any(_DNS_LABEL.fullmatch(label) is None for label in labels)
    ):
        raise ValueError("component URL host is not canonical ASCII DNS")
    return host


def _validated_port(parsed: urllib.parse.SplitResult) -> int | None:
    """Return a valid explicit port or None."""
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("component URL port is invalid") from exc
    if port is not None and not 1 <= port <= 65_535:
        raise ValueError("component URL port is invalid")
    return port
