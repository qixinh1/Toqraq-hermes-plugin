"""Typed host WebSocket dependency loading tests."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError

import pytest
import toqraq.bridge.bridge_websocket as bridge_websocket_module
from toqraq.bridge.bridge_websocket import (
    HERMES_WEBSOCKETS_VERSION,
    WebSocketRuntime,
    load_websocket_runtime,
)
from toqraq.core.errors import BridgeConnectionError


def test_runtime_loader_uses_distribution_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bridge_websocket_module,
        "package_version",
        lambda package: HERMES_WEBSOCKETS_VERSION if package == "websockets" else "",
    )

    runtime = load_websocket_runtime()

    assert isinstance(runtime, WebSocketRuntime)


def test_runtime_loader_classifies_missing_distribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = PackageNotFoundError("websockets")

    def fail_metadata(_package: str) -> str:
        raise missing

    monkeypatch.setattr(bridge_websocket_module, "package_version", fail_metadata)

    with pytest.raises(BridgeConnectionError) as raised:
        load_websocket_runtime()

    assert raised.value.details == {"reason": "websockets_dependency_unavailable"}
    assert raised.value.cause is missing
    assert raised.value.__cause__ is None


def test_runtime_loader_rejects_nonhermes_distribution_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge_websocket_module, "package_version", lambda _package: "99.0")

    with pytest.raises(BridgeConnectionError) as raised:
        load_websocket_runtime()

    assert raised.value.details == {
        "reason": "websockets_version_mismatch",
        "expected_version": HERMES_WEBSOCKETS_VERSION,
    }
    assert raised.value.cause is None
