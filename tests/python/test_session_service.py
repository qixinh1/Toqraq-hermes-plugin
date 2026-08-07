"""End-to-end application tests for exact session lifecycle ownership."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from toqraq.contracts.events import SessionEvent, SessionEventType
from toqraq.contracts.sessions import GameStartRequest, SetPausedRequest, StepFramesRequest
from toqraq.core.bridge import BridgeOwnerKey
from toqraq.core.capability_ids import PLAY_PAUSE_CAPABILITY_ID, PLAY_STEP_CAPABILITY_ID
from toqraq.core.errors import (
    ProjectIntrospectionError,
    ProtocolError,
    SessionCleanupError,
    SessionNotFoundError,
    SessionStateError,
)
from toqraq.core.process_tree import ProcessEnvironment
from toqraq.core.session_readiness import FeatureReadiness
from toqraq.core.session_registry import SessionRegistry
from toqraq.core.session_snapshot import SessionProcessState
from toqraq.services.events import SessionEventStream
from toqraq.services.session_gate import SessionOperationGate
from toqraq.services.sessions import SessionService
from toqraq.services.simulation import SimulationService

from _session_service_support import CREDENTIAL, HOST, SessionFixture, make_fixture


def _services(
    fixture: SessionFixture,
) -> tuple[SessionService, SimulationService, SessionRegistry, list[SessionEvent]]:
    registry = SessionRegistry()
    events = SessionEventStream(clock=lambda: 100.0)
    observed: list[SessionEvent] = []
    events.subscribe(observed.append)
    gate = SessionOperationGate()
    lifecycle = SessionService(
        selection=fixture.selection,
        registry=registry,
        events=events,
        host=HOST,
        connection_factory=fixture.connections,
        launcher=fixture.launcher,
        environment=ProcessEnvironment(variables=()),
        gate=gate,
        credential_factory=lambda: CREDENTIAL,
        clock=lambda: 200.0,
    )
    return lifecycle, SimulationService(registry, gate, events), registry, observed


def _request(root: Path) -> GameStartRequest:
    return GameStartRequest(project_dir=str(root))


async def _wait_for(predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(2):
        while not predicate():
            await asyncio.sleep(0.01)


def test_start_readiness_stop_and_launcher_cleanup_form_one_owner_graph(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        fixture = make_fixture(tmp_path)
        service, _simulation, registry, events = _services(fixture)

        started = await service.start("hermes-session", _request(tmp_path))
        await _wait_for(
            lambda: (
                service.get("hermes-session").preview.state is FeatureReadiness.READY
                and service.get("hermes-session").control.state is FeatureReadiness.READY
            )
        )
        ready = service.get("hermes-session")

        assert started.run_revision == 1
        assert ready.runtime.build_id == fixture.release.identity.build_id
        assert ready.preview.surface is not None
        assert ready.preview.surface.viewport_size.width == 960
        assert fixture.provisioner.selected == [fixture.release]
        assert fixture.provisioner.runtimes[0].release is fixture.release
        assert fixture.planner.runtimes == [fixture.provisioner.runtimes[0]]
        expectation_owner = fixture.connections.expectations[0].owner
        assert expectation_owner.session_id == ready.id
        assert expectation_owner.run_revision == ready.run_revision

        stopped = await service.stop("hermes-session")

        assert stopped.process_state is SessionProcessState.ENDED
        assert stopped.exit_code == 0
        assert fixture.launcher.processes[0].closed == 1
        assert fixture.connections.connections[0].closed == 1
        assert fixture.provisioner.leases[0].closed == 1
        with pytest.raises(SessionNotFoundError):
            registry.get("hermes-session")
        assert events[0].type is SessionEventType.STARTED
        assert events[-1].type is SessionEventType.STOPPED

        await service.close()
        assert fixture.launcher.closed == 1

    asyncio.run(scenario())


def test_replacement_releases_exact_prior_owner_before_atomic_commit(tmp_path: Path) -> None:
    async def scenario() -> None:
        fixture = make_fixture(tmp_path)
        service, _simulation, registry, events = _services(fixture)

        first = await service.start("hermes-session", _request(tmp_path))
        first_process = fixture.launcher.processes[0]
        second = await service.start("hermes-session", _request(tmp_path))

        assert first.run_revision == 1
        assert second.run_revision == 2
        assert first_process.closed == 1
        assert registry.get("hermes-session").owner.run_revision == 2
        assert fixture.provisioner.selected == [fixture.release, fixture.release]
        lifecycle_types = [event.type for event in events]
        first_stopped = lifecycle_types.index(SessionEventType.STOPPED)
        second_started = (
            len(lifecycle_types) - 1 - lifecycle_types[::-1].index(SessionEventType.STARTED)
        )
        assert first_stopped < second_started

        with pytest.raises(SessionStateError) as stale_stop:
            await service.stop(
                "hermes-session",
                expected_owner=BridgeOwnerKey(
                    session_id="hermes-session",
                    run_revision=first.run_revision,
                ),
            )
        assert stale_stop.value.details == {
            "reason": "run_replaced",
            "expected_run_revision": first.run_revision,
            "current_run_revision": second.run_revision,
            "retryable": True,
        }
        assert registry.get("hermes-session").owner.run_revision == second.run_revision
        await service.stop(
            "hermes-session",
            expected_owner=BridgeOwnerKey(
                session_id="hermes-session",
                run_revision=second.run_revision,
            ),
        )
        await service.close()

    asyncio.run(scenario())


def test_rejected_selection_does_not_allocate_a_run_identity(tmp_path: Path) -> None:
    async def scenario() -> None:
        fixture = make_fixture(tmp_path)
        service, _simulation, registry, _events = _services(fixture)

        with pytest.raises(ProjectIntrospectionError):
            await service.start("hermes-session", _request(tmp_path / "missing"))

        assert registry.sessions() == ()
        started = await service.start("hermes-session", _request(tmp_path))
        assert started.run_revision == 1
        await service.stop("hermes-session")
        await service.close()

    asyncio.run(scenario())


def test_finalize_cancels_pending_start_and_seals_the_hermes_identity(tmp_path: Path) -> None:
    async def scenario() -> None:
        entered = threading.Event()
        unblock = threading.Event()
        fixture = make_fixture(tmp_path, provisioner_events=(entered, unblock))
        service, _simulation, registry, _events = _services(fixture)
        starting = asyncio.create_task(service.start("hermes-session", _request(tmp_path)))
        assert await asyncio.to_thread(entered.wait, 1)

        finalizing = asyncio.create_task(service.finalize("hermes-session"))
        await _wait_for(lambda: fixture.provisioner.cancellations[0].is_set())
        unblock.set()

        with pytest.raises(SessionStateError) as captured:
            await starting
        assert captured.value.details == {"reason": "session_finalized"}
        await finalizing
        assert registry.sessions() == ()
        assert fixture.launcher.processes == []
        assert fixture.connections.connections[0].closed == 1
        assert fixture.provisioner.leases[0].closed == 1
        with pytest.raises(SessionStateError):
            await service.start("hermes-session", _request(tmp_path))

        await service.close()

    asyncio.run(scenario())


def test_cleanup_failure_remains_registered_and_succeeds_on_retry(tmp_path: Path) -> None:
    async def scenario() -> None:
        fixture = make_fixture(tmp_path, process_close_failures=1)
        service, _simulation, registry, events = _services(fixture)
        started = await service.start("hermes-session", _request(tmp_path))
        expected_owner = BridgeOwnerKey(
            session_id="hermes-session",
            run_revision=started.run_revision,
        )

        with pytest.raises(SessionCleanupError):
            await service.stop("hermes-session", expected_owner=expected_owner)

        retained = service.get("hermes-session")
        assert retained.process_state is SessionProcessState.STOPPING
        assert registry.get("hermes-session").resources.process_tree is not None
        assert events[-1].type is SessionEventType.FAILED

        stopped = await service.stop("hermes-session", expected_owner=expected_owner)
        assert stopped.process_state is SessionProcessState.ENDED
        assert registry.sessions() == ()
        assert fixture.provisioner.leases[0].closed == 1
        await service.close()

    asyncio.run(scenario())


def test_start_failure_with_incomplete_rollback_is_stable_and_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        fixture = make_fixture(tmp_path)
        service, _simulation, registry, _events = _services(fixture)
        original_open = fixture.connections.open

        async def open_with_retryable_close(expectation):
            connection = await original_open(expectation)
            original_close = connection.close
            attempts = 0

            async def close() -> None:
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise OSError("connection cleanup failed")
                await original_close()

            monkeypatch.setattr(connection, "close", close)
            return connection

        def fail_launch(_command) -> None:
            raise RuntimeError("launch failed")

        monkeypatch.setattr(fixture.connections, "open", open_with_retryable_close)
        monkeypatch.setattr(fixture.launcher, "launch", fail_launch)

        with pytest.raises(SessionCleanupError) as captured:
            await service.start("hermes-session", _request(tmp_path))

        assert captured.value.parameters == {
            "session_id": "hermes-session",
            "run_revision": 1,
        }
        assert captured.value.details == {
            "reason": "start_rollback_incomplete",
            "retryable": True,
        }
        assert isinstance(captured.value.cause, ExceptionGroup)
        assert len(captured.value.cause.exceptions) == 2
        assert registry.sessions() == ()
        assert fixture.connections.connections[0].closed == 0

        await service.finalize("hermes-session")
        assert fixture.connections.connections[0].closed == 1
        assert fixture.provisioner.leases[0].closed == 1
        await service.close()

    asyncio.run(scenario())


def test_natural_crash_publishes_terminal_state_and_releases_every_owner(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        fixture = make_fixture(tmp_path)
        service, _simulation, registry, events = _services(fixture)
        await service.start("hermes-session", _request(tmp_path))

        fixture.launcher.processes[0].exit(23)
        await _wait_for(lambda: registry.sessions() == ())

        process_events = [event for event in events if event.type is SessionEventType.PROCESS_STATE]
        assert process_events[-1].payload.process_state is SessionProcessState.CRASHED
        assert process_events[-1].payload.exit_code == 23
        assert events[-1].type is SessionEventType.STOPPED
        assert fixture.connections.connections[0].closed == 1
        assert fixture.provisioner.leases[0].closed == 1
        await service.close()

    asyncio.run(scenario())


def test_simulation_service_uses_ready_control_port_and_shared_gate(tmp_path: Path) -> None:
    async def scenario() -> None:
        fixture = make_fixture(tmp_path)
        service, simulation, _registry, _events = _services(fixture)
        await service.start("hermes-session", _request(tmp_path))
        await _wait_for(
            lambda: service.get("hermes-session").control.state is FeatureReadiness.READY
        )

        paused = await simulation.set_paused(
            "hermes-session",
            SetPausedRequest(paused=True),
        )
        stepped = await simulation.step(
            "hermes-session",
            StepFramesRequest(frame_count=3),
        )
        resumed = await simulation.set_paused(
            "hermes-session",
            SetPausedRequest(paused=False),
        )

        controller = fixture.connections.connections[0].ports.simulation
        assert paused.process_state is SessionProcessState.PAUSED
        assert stepped.process_state is SessionProcessState.PAUSED
        assert controller.steps == [3]
        assert resumed.process_state is SessionProcessState.RUNNING
        await service.stop("hermes-session")
        await service.close()

    asyncio.run(scenario())


def test_simulation_adapter_contract_failures_are_stable_protocol_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        fixture = make_fixture(tmp_path)
        service, simulation, _registry, _events = _services(fixture)
        await service.start("hermes-session", _request(tmp_path))
        await _wait_for(
            lambda: service.get("hermes-session").control.state is FeatureReadiness.READY
        )
        controller = fixture.connections.connections[0].ports.simulation
        original_set_paused = controller.set_paused

        async def mismatched_pause(command):
            acknowledgement = await original_set_paused(command)
            return replace(acknowledgement, paused=not command.paused)

        monkeypatch.setattr(controller, "set_paused", mismatched_pause)
        with pytest.raises(ProtocolError) as pause_error:
            await simulation.set_paused("hermes-session", SetPausedRequest(paused=True))
        assert pause_error.value.code == "bridge.protocol_invalid"
        assert pause_error.value.parameters == {"operation": PLAY_PAUSE_CAPABILITY_ID}
        assert pause_error.value.details == {"reason": "result_contract_invalid"}

        monkeypatch.setattr(controller, "set_paused", original_set_paused)
        await simulation.set_paused("hermes-session", SetPausedRequest(paused=True))
        original_step = controller.step

        async def mismatched_step(command):
            acknowledgement = await original_step(command)
            return replace(acknowledgement, frame_count=command.frame_count + 1)

        monkeypatch.setattr(controller, "step", mismatched_step)
        with pytest.raises(ProtocolError) as step_error:
            await simulation.step("hermes-session", StepFramesRequest(frame_count=3))
        assert step_error.value.code == "bridge.protocol_invalid"
        assert step_error.value.parameters == {"operation": PLAY_STEP_CAPABILITY_ID}
        assert step_error.value.details == {"reason": "result_contract_invalid"}

        await service.stop("hermes-session")
        await service.close()

    asyncio.run(scenario())


def test_concurrent_plugin_close_releases_launcher_exactly_once(tmp_path: Path) -> None:
    async def scenario() -> None:
        fixture = make_fixture(tmp_path)
        service, _simulation, registry, _events = _services(fixture)
        await service.start("hermes-session", _request(tmp_path))

        await asyncio.gather(service.close(), service.close())

        assert registry.sessions() == ()
        assert fixture.launcher.processes[0].closed == 1
        assert fixture.connections.connections[0].closed == 1
        assert fixture.provisioner.leases[0].closed == 1
        assert fixture.launcher.closed == 1

    asyncio.run(scenario())
