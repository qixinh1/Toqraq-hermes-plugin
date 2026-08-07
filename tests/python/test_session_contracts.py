"""Stable public requests and immutable session-snapshot mapping."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from pydantic import ValidationError
from toqraq.contracts.sessions import (
    FeatureReadinessResult,
    GameStartRequest,
    PreviewReadinessResult,
    SessionListResult,
    SessionResult,
    StepFramesRequest,
)
from toqraq.core.errors import BridgeConnectionError
from toqraq.core.session_capacity import MAX_CONCURRENT_GAME_SESSIONS
from toqraq.core.session_readiness import (
    FeatureReadiness,
    FeatureReadinessSnapshot,
    ReadinessFailure,
    ReadinessFeature,
)
from toqraq.core.session_snapshot import SessionProcessState
from toqraq.core.simulation_control import MAX_SIMULATION_STEP_FRAMES

from _session_contract_support import session_snapshot


def test_start_has_no_engine_default_and_accepts_an_exact_optional_version() -> None:
    request = GameStartRequest(project_dir="D:/game")
    selected = GameStartRequest(
        project_dir="D:/game",
        engine="godot",
        version="4.7.1-stable",
    )

    assert request.engine is None
    assert request.version is None
    assert (selected.engine, selected.version) == ("godot", "4.7.1-stable")
    with pytest.raises(ValidationError):
        GameStartRequest.model_validate({"project_dir": "D:/game", "channel": "toqraq"})


def test_public_session_list_uses_the_shared_lifecycle_capacity(tmp_path) -> None:
    result = SessionResult.from_snapshot(session_snapshot(tmp_path))

    assert len(SessionListResult(root=(result,) * MAX_CONCURRENT_GAME_SESSIONS).root) == (
        MAX_CONCURRENT_GAME_SESSIONS
    )
    with pytest.raises(ValidationError):
        SessionListResult(root=(result,) * (MAX_CONCURRENT_GAME_SESSIONS + 1))


@pytest.mark.parametrize("frame_count", [1, MAX_SIMULATION_STEP_FRAMES])
def test_step_request_uses_the_common_simulation_bound(frame_count: int) -> None:
    assert StepFramesRequest(frame_count=frame_count).frame_count == frame_count


@pytest.mark.parametrize("frame_count", [True, 0, MAX_SIMULATION_STEP_FRAMES + 1])
def test_step_request_rejects_non_work_and_unbounded_work(frame_count: object) -> None:
    with pytest.raises(ValidationError):
        StepFramesRequest.model_validate({"frame_count": frame_count})


def test_snapshot_mapping_preserves_exact_identity_and_redacts_preview(tmp_path) -> None:
    result = SessionResult.from_snapshot(session_snapshot(tmp_path))
    payload = result.model_dump(mode="json")
    encoded = json.dumps(payload)

    assert result.id == "hermes-1"
    assert result.run_revision == 7
    assert result.runtime.model_dump() == {
        "engine": "godot",
        "version": "4.7.1-stable",
        "build_id": "toqraq.windows.x86_64.release",
        "distribution_id": "toqraq.godot.windows.x86_64",
        "platform": "windows",
        "architecture": "x86_64",
    }
    assert result.project_dir == str(tmp_path)
    assert result.root_pid == 4_242
    assert result.process_state is SessionProcessState.RUNNING
    assert result.alive
    assert result.exit_code is None
    assert result.started_at == 1_722_000_000.25
    assert result.bridge.id == "toqraq.godot.bridge"
    assert result.bridge.protocol == "1.0"
    assert result.bridge.capabilities == tuple(sorted(result.bridge.capabilities))
    assert result.capabilities == tuple(sorted(result.capabilities))
    assert result.preview.surface is not None
    assert result.preview.surface.kind == "native_window"
    assert result.preview.surface.viewport_size.model_dump() == {"width": 960, "height": 540}
    assert set(payload) == {
        "id",
        "run_revision",
        "runtime",
        "project_dir",
        "root_pid",
        "process_state",
        "alive",
        "exit_code",
        "started_at",
        "bridge",
        "capabilities",
        "preview",
        "perception",
        "control",
    }
    assert set(payload["preview"]["surface"]) == {"kind", "viewport_size"}
    assert all(name not in encoded for name in ("access_credential", "native_handle", "url"))


def test_readiness_failure_maps_only_registered_public_safe_facts(tmp_path) -> None:
    error = BridgeConnectionError(
        parameters={"feature": "perception"},
        details={"reason": "disconnected"},
        cause=OSError("private cause"),
    )
    failure = ReadinessFailure.from_error(
        error,
        features=frozenset({ReadinessFeature.PERCEPTION}),
    )
    snapshot = replace(
        session_snapshot(tmp_path),
        perception=FeatureReadinessSnapshot(
            state=FeatureReadiness.FAILED,
            failure=failure,
        ),
    )

    public = SessionResult.from_snapshot(snapshot).perception
    payload = public.model_dump(mode="json")

    assert payload == {
        "state": "failed",
        "error": {
            "code": "bridge.unavailable",
            "category": "unavailable",
            "parameters": {"feature": "perception"},
            "details": {"reason": "disconnected"},
            "trace_id": str(error.trace_id),
        },
    }
    assert "cause" not in json.dumps(payload)
    assert "features" not in json.dumps(payload)


def test_terminal_snapshot_requires_exit_and_preview_requires_safe_surface(tmp_path) -> None:
    running = SessionResult.from_snapshot(session_snapshot(tmp_path)).model_dump(mode="python")

    with pytest.raises(ValidationError, match="terminal session"):
        SessionResult.model_validate(
            {
                **running,
                "process_state": SessionProcessState.ENDED,
                "alive": False,
            }
        )
    with pytest.raises(ValidationError, match="safe surface"):
        PreviewReadinessResult(state=FeatureReadiness.READY, surface=None)
    with pytest.raises(ValidationError, match="exactly one error"):
        FeatureReadinessResult(state=FeatureReadiness.FAILED)
    with pytest.raises(ValidationError, match="unique and sorted"):
        SessionResult.model_validate(
            {
                **running,
                "capabilities": (
                    "toqraq.play.pause",
                    "toqraq.play.pause",
                ),
            }
        )


def test_terminal_snapshot_retains_exact_exit_facts(tmp_path) -> None:
    result = SessionResult.from_snapshot(
        session_snapshot(
            tmp_path,
            process_state=SessionProcessState.CRASHED,
            exit_code=23,
            preview_state=FeatureReadiness.UNAVAILABLE,
        )
    )

    assert not result.alive
    assert result.process_state is SessionProcessState.CRASHED
    assert result.exit_code == 23
    assert result.preview.surface is None


def test_stopping_snapshot_can_retain_an_observed_exit_during_cleanup(tmp_path) -> None:
    result = SessionResult.from_snapshot(
        session_snapshot(
            tmp_path,
            process_state=SessionProcessState.STOPPING,
            exit_code=11,
            preview_state=FeatureReadiness.UNAVAILABLE,
        )
    )

    assert result.process_state is SessionProcessState.STOPPING
    assert result.exit_code == 11
    assert not result.alive
