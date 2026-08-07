"""Pure preview-surface validation tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from toqraq.core.geometry import Size
from toqraq.core.preview import (
    NativeWindowReference,
    NativeWindowSurface,
    WebSurface,
)


def test_native_surface_retains_true_viewport_and_opaque_platform_reference() -> None:
    """A native surface is immutable and carries no renderer DTO behavior."""
    surface = NativeWindowSurface(
        window=NativeWindowReference(value=123),
        viewport_size=Size(width=960, height=540),
    )
    assert surface.window.value == 123
    assert surface.viewport_size == Size(width=960, height=540)
    with pytest.raises(FrozenInstanceError):
        surface.window = NativeWindowReference(value=456)  # type: ignore[misc]


@pytest.mark.parametrize("value", [0, -1, True, 1 << 64, "1"])
def test_native_reference_rejects_non_handle_values(value: object) -> None:
    """A platform reference cannot be a null or cross-boundary substitute."""
    with pytest.raises(ValueError):
        NativeWindowReference(value=value)  # type: ignore[arg-type]


def test_web_surface_is_loopback_only_and_redacts_its_credential() -> None:
    """Web preview authorization is never embedded in its URL or repr."""
    credential = "a" * 64
    surface = WebSurface(
        url="http://127.0.0.1:3210/player",
        access_credential=credential,
        viewport_size=Size(width=1280, height=720),
    )
    assert credential not in repr(surface)
    assert surface.url == "http://127.0.0.1:3210/player"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/player",
        "http://localhost:3210/player",
        "http://user@127.0.0.1:3210/player",
        "http://127.0.0.1/player",
        "http://127.0.0.1:3210/player#secret",
        "file:///player",
    ],
)
def test_web_surface_rejects_non_loopback_or_ambiguous_urls(url: str) -> None:
    """No remote origin or authority syntax can enter the preview boundary."""
    with pytest.raises(ValueError):
        WebSurface(
            url=url,
            access_credential="a" * 64,
            viewport_size=Size(width=1, height=1),
        )


@pytest.mark.parametrize("credential", ["", "A" * 64, "a" * 63, "g" * 64])
def test_web_surface_rejects_noncanonical_credentials(credential: str) -> None:
    """The host receives exactly one strong canonical authorization value."""
    with pytest.raises(ValueError):
        WebSurface(
            url="http://127.0.0.1:3210/",
            access_credential=credential,
            viewport_size=Size(width=1, height=1),
        )
