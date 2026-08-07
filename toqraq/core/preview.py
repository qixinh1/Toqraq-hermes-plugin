"""Pure tagged surfaces returned by engine-owned preview discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeAlias
from urllib.parse import urlsplit

from .geometry import Size

MAX_NATIVE_WINDOW_REFERENCE = (1 << 64) - 1
WEB_PREVIEW_CREDENTIAL_HEX_CHARACTERS = 64
_WEB_PREVIEW_CREDENTIAL = re.compile(rf"^[0-9a-f]{{{WEB_PREVIEW_CREDENTIAL_HEX_CHARACTERS}}}$")


@dataclass(frozen=True, slots=True, kw_only=True)
class NativeWindowReference:
    """Process-local platform reference never serialized to the renderer."""

    value: int

    def __post_init__(self) -> None:
        """Reject booleans, null handles, and values outside a native word."""
        if (
            isinstance(self.value, bool)
            or not isinstance(self.value, int)
            or not 1 <= self.value <= MAX_NATIVE_WINDOW_REFERENCE
        ):
            raise ValueError("native window reference is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class NativeWindowSurface:
    """Standalone engine window and its authoritative game viewport size."""

    window: NativeWindowReference
    viewport_size: Size

    def __post_init__(self) -> None:
        """Require one platform reference and one real viewport size."""
        if not isinstance(self.window, NativeWindowReference):
            raise ValueError("native preview window is invalid")
        if not isinstance(self.viewport_size, Size):
            raise ValueError("native preview viewport size is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class WebSurface:
    """Loopback web player whose authorization stays outside renderer storage."""

    url: str
    access_credential: str = field(repr=False)
    viewport_size: Size

    def __post_init__(self) -> None:
        """Reject remote origins, URL credentials, fragments, and weak tokens."""
        _validate_web_preview_url(self.url)
        if (
            not isinstance(self.access_credential, str)
            or _WEB_PREVIEW_CREDENTIAL.fullmatch(self.access_credential) is None
        ):
            raise ValueError("web preview credential is invalid")
        if not isinstance(self.viewport_size, Size):
            raise ValueError("web preview viewport size is invalid")


PreviewSurface: TypeAlias = NativeWindowSurface | WebSurface


class PreviewSurfaceKind(StrEnum):
    """Safe public kinds for the two engine-located preview surfaces."""

    NATIVE_WINDOW = "native_window"
    WEB = "web"


@dataclass(frozen=True, slots=True, kw_only=True)
class PreviewSurfaceSnapshot:
    """Safe surface projection containing no locator or authorization value."""

    kind: PreviewSurfaceKind
    viewport_size: Size

    def __post_init__(self) -> None:
        """Require one closed kind and authoritative viewport size."""
        if not isinstance(self.kind, PreviewSurfaceKind):
            raise ValueError("preview surface kind is invalid")
        if not isinstance(self.viewport_size, Size):
            raise ValueError("preview surface viewport size is invalid")

    @classmethod
    def from_surface(cls, surface: PreviewSurface) -> PreviewSurfaceSnapshot:
        """Remove native references, URLs, and credentials from one surface."""
        if isinstance(surface, NativeWindowSurface):
            return cls(
                kind=PreviewSurfaceKind.NATIVE_WINDOW,
                viewport_size=surface.viewport_size,
            )
        if isinstance(surface, WebSurface):
            return cls(
                kind=PreviewSurfaceKind.WEB,
                viewport_size=surface.viewport_size,
            )
        raise ValueError("preview surface is invalid")


def _validate_web_preview_url(value: str) -> None:
    """Require an explicit HTTP loopback origin with no embedded authority."""
    if not isinstance(value, str) or not value:
        raise ValueError("web preview URL is invalid")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("web preview URL is invalid") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname != "127.0.0.1"
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or not parsed.path.startswith("/")
    ):
        raise ValueError("web preview URL is invalid")
