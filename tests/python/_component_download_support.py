from __future__ import annotations

import hashlib
import json
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from toqraq.components.download import ComponentDownloader
from toqraq.components.download_models import (
    ComponentDownloadPolicy,
    ComponentDownloadProgress,
    DownloadedComponentPackage,
)
from toqraq.components.layout import ComponentStoreLayout
from toqraq.components.lock import ComponentLockPolicy
from toqraq.components.mutation import ComponentMutationOwner
from toqraq.components.release import ComponentRelease

URL = "https://downloads.example.test/component.zip"
POLICY = ComponentDownloadPolicy(
    io_timeout_seconds=1,
    idle_timeout_seconds=2,
    total_timeout_seconds=5,
    chunk_bytes=3,
    checkpoint_bytes=6,
    max_redirects=2,
    user_agent="toqraq-tests/1",
)
LOCK_POLICY = ComponentLockPolicy(timeout_seconds=2, poll_seconds=0.01)


class Headers:
    def __init__(self, values: dict[str, list[str]] | None = None) -> None:
        self._values = {name.lower(): items for name, items in (values or {}).items()}

    def get_all(self, name: str) -> list[str] | None:
        return self._values.get(name.lower())


class Response:
    def __init__(
        self,
        body: bytes,
        *,
        status: object = 200,
        headers: dict[str, list[str]] | None = None,
        url: object = URL,
        failure_after: int | None = None,
        non_bytes: bool = False,
    ) -> None:
        self.status = status
        self.headers = Headers(headers)
        self._body = body
        self._url = url
        self._failure_after = failure_after
        self._non_bytes = non_bytes
        self._offset = 0
        self.closed = False

    def read(self, size: int = -1) -> Any:
        if self._failure_after is not None and self._offset >= self._failure_after:
            raise OSError("private transport failure")
        if self._non_bytes:
            return "not bytes"
        end = len(self._body) if size < 0 else min(len(self._body), self._offset + size)
        chunk = self._body[self._offset : end]
        self._offset = end
        return chunk

    def geturl(self) -> Any:
        return self._url

    def close(self) -> None:
        self.closed = True


class OpenSequence:
    def __init__(self, *events: object) -> None:
        self.events = list(events)
        self.requests: list[urllib.request.Request] = []
        self.timeouts: list[float] = []

    def build(self, *_handlers: object) -> OpenSequence:
        return self

    def open(self, request: urllib.request.Request, *, timeout: float) -> object:
        self.requests.append(request)
        self.timeouts.append(timeout)
        event = self.events.pop(0)
        if isinstance(event, BaseException):
            raise event
        return event


def release(package: bytes) -> ComponentRelease:
    digest = hashlib.sha256(package).hexdigest()
    return ComponentRelease.model_validate_json(
        json.dumps(
            {
                "record_version": 1,
                "kind": "engine",
                "plugin_version": "0.1.0",
                "identity": {
                    "component_id": "engine.godot",
                    "version": "4.7.1-stable",
                    "build_id": "toqraq.windows.x86_64.release",
                    "platform": "windows",
                    "architecture": "x86_64",
                    "package_sha256": digest,
                },
                "label": "Godot 4.7.1",
                "source": {
                    "publisher": "Toqraq",
                    "package_url": URL,
                    "provenance_url": "https://builds.example.test/godot/4.7.1",
                    "allowed_origins": ["https://downloads.example.test"],
                },
                "package_bytes": len(package),
                "installed_bytes": len(package) * 2,
                "install_strategy": "archive.zip",
                "expected_tree_sha256": "2" * 64,
                "entry_points": [
                    {
                        "name": "editor",
                        "relative_path": "bin/editor.exe",
                        "executable": True,
                    }
                ],
                "dependencies": [],
                "capabilities": [],
                "bridge": None,
                "license": {
                    "identifier": "MIT",
                    "name": "MIT License",
                    "url": "https://godotengine.org/license/",
                    "acceptance_required": False,
                },
                "authentication_required": False,
            }
        )
    )


def full_response(
    body: bytes,
    *,
    headers: dict[str, list[str]] | None = None,
    **changes: object,
) -> Response:
    values = {"Content-Length": [str(len(body))]} if headers is None else headers
    return Response(body, headers=values, **changes)


def range_response(package: bytes, offset: int, **changes: object) -> Response:
    body = package[offset:]
    return Response(
        body,
        status=206,
        headers={
            "Content-Length": [str(len(body))],
            "Content-Range": [f"bytes {offset}-{len(package) - 1}/{len(package)}"],
        },
        **changes,
    )


def downloader_fixture(
    tmp_path: Path,
) -> tuple[ComponentStoreLayout, ComponentDownloader, ComponentMutationOwner]:
    layout = ComponentStoreLayout(tmp_path / "toqraq")
    layout.initialize()
    return (
        layout,
        ComponentDownloader(layout, POLICY),
        ComponentMutationOwner(layout, LOCK_POLICY),
    )


def download(
    downloader: ComponentDownloader,
    owner: ComponentMutationOwner,
    selected_release: ComponentRelease,
    *,
    cancellation: threading.Event | None = None,
    progress: Callable[[ComponentDownloadProgress], None] | None = None,
    require_capacity: Callable[[int], None] | None = None,
) -> DownloadedComponentPackage:
    with owner.acquire(selected_release.identity, cancellation=cancellation) as mutation:
        return downloader.download(
            selected_release,
            mutation,
            cancellation=cancellation,
            progress=progress,
            require_capacity=require_capacity,
        )


def install_opener(monkeypatch: pytest.MonkeyPatch, sequence: OpenSequence) -> None:
    monkeypatch.setattr(
        "toqraq.components.download_http.urllib.request.build_opener",
        sequence.build,
    )
