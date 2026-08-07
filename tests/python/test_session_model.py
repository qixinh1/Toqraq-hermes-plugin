"""Pure tests for promoted session identity, state, and readiness."""

from __future__ import annotations

import asyncio
from threading import Event, Thread
from types import MappingProxyType
from typing import cast

import pytest
from toqraq.core.bridge import BridgeOwnerKey
from toqraq.core.errors import BridgeConnectionError, ErrorCategory, SessionStateError
from toqraq.core.geometry import Size
from toqraq.core.preview import (
    NativeWindowReference,
    NativeWindowSurface,
    PreviewSurfaceKind,
    PreviewSurfaceSnapshot,
    WebSurface,
)
from toqraq.core.runtime_features import RuntimeFeaturePorts
from toqraq.core.session_readiness import (
    FeatureReadiness,
    ReadinessFailure,
    ReadinessFeature,
)
from toqraq.core.session_snapshot import SessionProcessState

from _session_domain_support import make_session


def _owner(revision: int = 1) -> BridgeOwnerKey:
    return BridgeOwnerKey(session_id="hermes-session", run_revision=revision)


def _failure(
    features: frozenset[ReadinessFeature] | None = None,
) -> tuple[BridgeConnectionError, ReadinessFailure]:
    error = BridgeConnectionError(
        parameters={"feature": "perception"},
        details={"reason": "disconnected", "attempt": 1},
        cause=OSError("private transport detail"),
    )
    return error, ReadinessFailure.from_error(
        error,
        features=features or frozenset(ReadinessFeature),
    )


def _preview() -> NativeWindowSurface:
    return NativeWindowSurface(
        window=NativeWindowReference(value=1_234),
        viewport_size=Size(width=960, height=540),
    )


def test_promoted_session_caches_exact_launch_and_independent_readiness(tmp_path) -> None:
    session, process, connection, _ports, _lease = make_session(tmp_path, _owner(7))

    snapshot = session.snapshot()

    assert snapshot.owner == _owner(7)
    assert snapshot.project.project_root == tmp_path
    assert snapshot.runtime_identity.engine_id == "godot"
    assert snapshot.runtime_identity.version == "4.7.1-stable"
    assert snapshot.bridge_id == "toqraq.godot.bridge"
    assert snapshot.bridge_protocol == "1.0"
    assert snapshot.capability_ids > snapshot.bridge_capability_ids
    assert snapshot.root_pid == process.root_pid
    assert snapshot.started_at == 1_722_000_000.25
    assert snapshot.process_state is SessionProcessState.RUNNING
    assert snapshot.exit_code is None
    assert snapshot.alive
    assert snapshot.preview.state is FeatureReadiness.CONNECTING
    assert snapshot.preview_surface is None
    assert snapshot.perception.state is FeatureReadiness.CONNECTING
    assert snapshot.control.state is FeatureReadiness.CONNECTING
    assert session.resources.connection is connection


def test_session_rejects_a_bridge_connection_owned_by_another_run(tmp_path) -> None:
    with pytest.raises(ValueError, match="connection owners differ"):
        make_session(
            tmp_path,
            _owner(1),
            connection_owner=_owner(2),
        )


def test_web_preview_snapshot_removes_url_and_credential() -> None:
    surface = WebSurface(
        url="http://127.0.0.1:49152/game",
        access_credential="c" * 64,
        viewport_size=Size(width=1280, height=720),
    )

    snapshot = PreviewSurfaceSnapshot.from_surface(surface)

    assert snapshot.kind is PreviewSurfaceKind.WEB
    assert snapshot.viewport_size == surface.viewport_size
    assert not hasattr(snapshot, "url")
    assert not hasattr(snapshot, "access_credential")


def test_pause_transition_only_accepts_running_paused_edges(tmp_path) -> None:
    session, *_ = make_session(tmp_path, _owner())

    session.mark_paused(True)
    assert session.process_state is SessionProcessState.PAUSED
    with pytest.raises(SessionStateError):
        session.mark_paused(True)
    session.mark_paused(False)
    assert session.process_state is SessionProcessState.RUNNING
    with pytest.raises(SessionStateError):
        session.mark_paused(False)
    with pytest.raises(ValueError):
        session.mark_paused(cast(bool, 1))


def test_feature_publication_retains_only_ports_below_connection_owner(tmp_path) -> None:
    session, _process, connection, ports, _lease = make_session(tmp_path, _owner())

    session.publish_features(cast(RuntimeFeaturePorts, ports))

    assert session.feature_ports is ports
    assert session.resources.connection is connection
    assert connection.close_count == 0
    assert not hasattr(ports, "close")
    snapshot = session.snapshot()
    assert snapshot.perception.state is FeatureReadiness.READY
    assert snapshot.control.state is FeatureReadiness.READY
    assert snapshot.preview.state is FeatureReadiness.CONNECTING
    with pytest.raises(SessionStateError):
        session.publish_features(cast(RuntimeFeaturePorts, ports))


def test_readiness_failures_are_safe_immutable_and_cause_free(tmp_path) -> None:
    session, *_ = make_session(tmp_path, _owner())
    source, failure = _failure()

    session.fail_features(failure)

    observed = session.snapshot().perception.failure
    assert observed is failure
    assert failure.code == "bridge.unavailable"
    assert failure.category is ErrorCategory.UNAVAILABLE
    assert failure.trace_id is source.trace_id
    assert failure.parameters == {"feature": "perception"}
    assert isinstance(failure.parameters, MappingProxyType)
    assert not hasattr(failure, "cause")
    with pytest.raises(TypeError):
        failure.details["reason"] = "changed"  # type: ignore[index]
    with pytest.raises(ValueError):
        session.publish_features(cast(RuntimeFeaturePorts, object()))
    with pytest.raises(ValueError, match="code or category"):
        ReadinessFailure(
            code=failure.code,
            category=ErrorCategory.INVALID,
            features=frozenset({ReadinessFeature.PERCEPTION}),
            trace_id=failure.trace_id,
        )


def test_bridge_and_preview_fail_independently(tmp_path) -> None:
    session, *_ = make_session(tmp_path, _owner())
    _source, failure = _failure()

    surface = _preview()
    session.publish_preview(surface)
    session.fail_features(failure)

    snapshot = session.snapshot()
    assert snapshot.perception.state is FeatureReadiness.FAILED
    assert snapshot.control.state is FeatureReadiness.FAILED
    assert snapshot.preview.state is FeatureReadiness.READY
    assert session.preview_surface is surface
    public_surface = session.snapshot().preview_surface
    assert public_surface is not None
    assert public_surface.kind is PreviewSurfaceKind.NATIVE_WINDOW
    assert public_surface.viewport_size == Size(width=960, height=540)
    assert not hasattr(public_surface, "window")
    assert not hasattr(public_surface, "url")
    assert not hasattr(public_surface, "access_credential")
    with pytest.raises(SessionStateError):
        session.publish_preview(_preview())
    session.fail_preview(failure)
    assert session.snapshot().preview.state is FeatureReadiness.FAILED
    assert session.preview_surface is None
    with pytest.raises(SessionStateError):
        session.fail_preview(failure)


def test_failure_fact_cannot_be_published_for_another_feature(tmp_path) -> None:
    session, *_ = make_session(tmp_path, _owner())
    _source, perception_failure = _failure(
        frozenset({ReadinessFeature.PERCEPTION}),
    )

    with pytest.raises(ValueError, match="does not match"):
        session.fail_features(perception_failure)


@pytest.mark.parametrize(
    ("exit_code", "expected"),
    [
        (0, SessionProcessState.ENDED),
        (3, SessionProcessState.CRASHED),
        (-9, SessionProcessState.CRASHED),
    ],
)
def test_natural_exit_is_classified_and_same_code_is_idempotent(
    tmp_path,
    exit_code: int,
    expected: SessionProcessState,
) -> None:
    session, process, *_ = make_session(tmp_path, _owner())
    process.exit(exit_code)

    session.record_exit(exit_code)
    session.record_exit(exit_code)

    snapshot = session.snapshot()
    assert snapshot.process_state is expected
    assert snapshot.exit_code == exit_code
    assert not snapshot.alive
    with pytest.raises(SessionStateError, match=r"session\.invalid_state"):
        session.record_exit(exit_code + 1)


def test_explicit_close_keeps_failed_cleanup_owned_then_forms_terminal_snapshot(tmp_path) -> None:
    async def run() -> None:
        session, process, connection, _ports, lease = make_session(
            tmp_path,
            _owner(),
            process_close_failures=1,
            stop_exit_code=9,
        )

        with pytest.raises(ExceptionGroup):
            await session.close()

        assert session.process_state is SessionProcessState.STOPPING
        assert session.resources.process_tree is process
        assert session.resources.runtime is not None
        assert session.resources.connection is None

        await session.close()

        snapshot = session.snapshot()
        assert session.resources.empty
        assert snapshot.process_state is SessionProcessState.ENDED
        assert snapshot.exit_code == 9
        assert snapshot.root_pid == process.root_pid
        assert snapshot.runtime_identity.version == "4.7.1-stable"
        assert connection.close_count == 1
        assert lease.close_count == 1

    asyncio.run(run())


def test_stop_exit_survives_a_later_connection_cleanup_failure(tmp_path) -> None:
    async def run() -> None:
        session, process, connection, _ports, _lease = make_session(
            tmp_path,
            _owner(),
            connection_close_failures=1,
            stop_exit_code=11,
        )

        with pytest.raises(ExceptionGroup):
            await session.close()

        assert process.poll() == 11
        assert session.process_state is SessionProcessState.STOPPING
        failed_cleanup_snapshot = session.snapshot()
        assert failed_cleanup_snapshot.exit_code == 11
        assert not failed_cleanup_snapshot.alive
        assert session.resources.process_tree is None
        assert session.resources.connection is connection

        await session.close()
        assert session.snapshot().process_state is SessionProcessState.ENDED
        assert session.snapshot().exit_code == 11

    asyncio.run(run())


def test_natural_crash_cleanup_preserves_the_recorded_terminal_result(tmp_path) -> None:
    async def run() -> None:
        session, process, *_ = make_session(tmp_path, _owner())
        process.exit(23)
        session.record_exit(23)

        await session.close()

        assert session.resources.empty
        assert session.snapshot().process_state is SessionProcessState.CRASHED
        assert session.snapshot().exit_code == 23

    asyncio.run(run())


def test_close_observes_an_unreported_natural_crash_before_marking_stopping(tmp_path) -> None:
    async def run() -> None:
        session, process, *_ = make_session(tmp_path, _owner())
        process.exit(23)

        await session.close()

        snapshot = session.snapshot()
        assert snapshot.process_state is SessionProcessState.CRASHED
        assert snapshot.exit_code == 23

    asyncio.run(run())


def test_stop_atomically_withdraws_borrowed_ports_preview_and_ready_states(tmp_path) -> None:
    async def run() -> None:
        session, _process, connection, ports, _lease = make_session(tmp_path, _owner())
        session.publish_features(cast(RuntimeFeaturePorts, ports))
        session.publish_preview(_preview())

        await session.close()

        snapshot = session.snapshot()
        assert session.feature_ports is None
        assert session.preview_surface is None
        assert snapshot.preview.state is FeatureReadiness.UNAVAILABLE
        assert snapshot.perception.state is FeatureReadiness.UNAVAILABLE
        assert snapshot.control.state is FeatureReadiness.UNAVAILABLE
        assert connection.close_count == 1
        assert not hasattr(ports, "close")

    asyncio.run(run())


def test_cross_thread_feature_publication_cannot_cross_the_stopping_edge(tmp_path) -> None:
    async def run() -> None:
        close_started = Event()
        close_release = Event()
        session, _process, _connection, ports, _lease = make_session(
            tmp_path,
            _owner(),
            process_close_started=close_started,
            process_close_release=close_release,
        )
        failures: list[BaseException] = []

        def publish() -> None:
            try:
                session.publish_features(cast(RuntimeFeaturePorts, ports))
            except BaseException as error:
                failures.append(error)

        cleanup = asyncio.create_task(session.close())
        assert await asyncio.to_thread(close_started.wait, 2)
        thread = Thread(target=publish)
        thread.start()
        thread.join(timeout=2)
        close_release.set()
        await cleanup

        assert len(failures) == 1
        assert isinstance(failures[0], SessionStateError)
        assert session.feature_ports is None

    asyncio.run(run())
