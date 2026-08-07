"""Public request immutability and safe session-result surface."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError
from toqraq.contracts.sessions import SessionResult
from toqraq.contracts.setup import SetupRequest


def _session() -> SessionResult:
    """Build one compact valid engine-neutral session result."""
    return SessionResult.model_validate_json(
        json.dumps(
            {
                "id": "session-1",
                "run_revision": 1,
                "runtime": {
                    "engine": "godot",
                    "version": "4.7.1-stable",
                    "build_id": "toqraq.windows.x86_64.release",
                    "distribution_id": "toqraq.godot.windows.x86_64",
                    "platform": "windows",
                    "architecture": "x86_64",
                },
                "project_dir": "D:/game",
                "root_pid": 123,
                "process_state": "running",
                "alive": True,
                "exit_code": None,
                "started_at": 1_722_000_000.25,
                "bridge": {
                    "id": "toqraq.godot.bridge",
                    "protocol": "1.0",
                    "capabilities": ["toqraq.play.pause"],
                },
                "capabilities": ["toqraq.play.pause", "toqraq.preview.display"],
                "preview": {
                    "state": "ready",
                    "error": None,
                    "surface": {
                        "kind": "native_window",
                        "viewport_size": {"width": 960, "height": 540},
                    },
                },
                "perception": {"state": "ready", "error": None},
                "control": {"state": "ready", "error": None},
            }
        )
    )


def test_request_models_are_strict_frozen_and_extra_forbid() -> None:
    request = SetupRequest.model_validate({"engine": "godot"})
    with pytest.raises(ValidationError):
        request.engine = "unity"
    with pytest.raises(ValidationError):
        SetupRequest.model_validate({"engine": 1})
    with pytest.raises(ValidationError):
        SetupRequest.model_validate({"channel": "official"})


def test_session_result_exposes_no_native_or_runtime_selection_secret() -> None:
    session = _session().model_dump(mode="json")

    assert "window" not in session
    assert "url" not in session
    assert "credential" not in session
    assert "channel" not in json.dumps(session)
    assert "executable" not in json.dumps(session)
