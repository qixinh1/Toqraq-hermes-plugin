"""Focused pause, resume, and frame-step use cases."""

from __future__ import annotations

from ..contracts.events import SessionEventType
from ..contracts.identifiers import HermesSessionId
from ..contracts.sessions import SessionResult, SetPausedRequest, StepFramesRequest
from ..core.capability_ids import PLAY_PAUSE_CAPABILITY_ID, PLAY_STEP_CAPABILITY_ID
from ..core.errors import SessionStateError
from ..core.session_registry import SessionRegistry
from ..core.session_snapshot import SessionProcessState
from ..core.simulation_control import (
    SetPausedCommand,
    StepFramesCommand,
    validate_set_paused_acknowledgement,
    validate_step_frames_acknowledgement,
)
from .events import SessionEventStream
from .session_feature_access import (
    control_access,
    validate_feature_dependencies,
    verified_feature_result,
)
from .session_gate import SessionOperationGate


class SimulationService:
    """Apply immediate simulation commands to one current session owner."""

    __slots__ = ("_events", "_gate", "_registry")

    def __init__(
        self,
        registry: SessionRegistry,
        gate: SessionOperationGate,
        events: SessionEventStream,
    ) -> None:
        """Share the exact registry and mutation gate with lifecycle use cases."""
        validate_feature_dependencies(registry, gate)
        if not isinstance(events, SessionEventStream):
            raise ValueError("simulation event stream is invalid")
        self._registry = registry
        self._gate = gate
        self._events = events

    async def set_paused(
        self,
        session_id: HermesSessionId,
        request: SetPausedRequest,
    ) -> SessionResult:
        """Set an idempotent simulation pause state through the focused port."""
        command = SetPausedCommand(paused=request.paused)
        async with control_access(
            self._registry,
            self._gate,
            session_id,
            PLAY_PAUSE_CAPABILITY_ID,
        ) as access:
            snapshot = access.session.snapshot()
            target = SessionProcessState.PAUSED if request.paused else SessionProcessState.RUNNING
            if snapshot.process_state is target:
                return SessionResult.from_snapshot(snapshot)
            acknowledgement = await access.resources.invoke_owned(
                access.ports.simulation.set_paused(command)
            )
            verified_feature_result(
                PLAY_PAUSE_CAPABILITY_ID,
                lambda: validate_set_paused_acknowledgement(acknowledgement, command),
            )
            access.session.mark_paused(request.paused)
            result = SessionResult.from_snapshot(access.session.snapshot())
            self._events.publish(SessionEventType.PROCESS_STATE, result)
            return result

    async def step(
        self,
        session_id: HermesSessionId,
        request: StepFramesRequest,
    ) -> SessionResult:
        """Advance an exact bounded frame count while simulation remains paused."""
        command = StepFramesCommand(frame_count=request.frame_count)
        async with control_access(
            self._registry,
            self._gate,
            session_id,
            PLAY_STEP_CAPABILITY_ID,
        ) as access:
            if access.session.process_state is not SessionProcessState.PAUSED:
                raise SessionStateError(
                    parameters={
                        "current_state": access.session.process_state.value,
                        "requested_state": SessionProcessState.PAUSED.value,
                    },
                    details={"reason": "step_requires_paused_simulation"},
                )
            acknowledgement = await access.resources.invoke_owned(
                access.ports.simulation.step(command)
            )
            verified_feature_result(
                PLAY_STEP_CAPABILITY_ID,
                lambda: validate_step_frames_acknowledgement(acknowledgement, command),
            )
            return SessionResult.from_snapshot(access.session.snapshot())
