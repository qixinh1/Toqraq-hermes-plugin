"""Strict JSON-RPC contracts for pause state and bounded frame stepping."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..core.observation import ObservationRevision
from ..core.simulation_control import (
    MAX_SIMULATION_STEP_FRAMES,
    SetPausedAcknowledgement,
    SetPausedCommand,
    StepFramesAcknowledgement,
    StepFramesCommand,
    validate_set_paused_acknowledgement,
    validate_step_frames_acknowledgement,
)
from .base import ContractModel
from .bridge import JSON_RPC_VERSION
from .bridge_observation import ObservationRevisionValue
from .bridge_rpc import BridgeHostRequestId

SIMULATION_SET_PAUSED_METHOD: Literal["toqraq.simulation.set_paused"] = (
    "toqraq.simulation.set_paused"
)
SIMULATION_STEP_METHOD: Literal["toqraq.simulation.step"] = "toqraq.simulation.step"


class SimulationSetPausedParams(ContractModel):
    """Desired pause state sent to one authenticated run."""

    paused: bool

    def to_core(self) -> SetPausedCommand:
        """Convert strict params to the idempotent pure command."""
        return SetPausedCommand(paused=self.paused)

    @classmethod
    def from_core(cls, value: SetPausedCommand) -> SimulationSetPausedParams:
        """Create canonical params from one validated pure command."""
        return cls(paused=value.paused)


class SimulationSetPausedResult(ContractModel):
    """Resulting pause state and authoritative observation revisions."""

    paused: bool
    changed: bool
    simulation_revision: ObservationRevisionValue
    frame_revision: ObservationRevisionValue

    def to_core(self, *, command: SetPausedCommand) -> SetPausedAcknowledgement:
        """Convert and correlate a strict result with its owning command."""
        acknowledgement = SetPausedAcknowledgement(
            paused=self.paused,
            changed=self.changed,
            simulation_revision=ObservationRevision(value=self.simulation_revision),
            frame_revision=ObservationRevision(value=self.frame_revision),
        )
        validate_set_paused_acknowledgement(acknowledgement, command)
        return acknowledgement

    @classmethod
    def from_core(
        cls,
        value: SetPausedAcknowledgement,
        *,
        command: SetPausedCommand,
    ) -> SimulationSetPausedResult:
        """Create one exact result after correlating its owning command."""
        validate_set_paused_acknowledgement(value, command)
        return cls(
            paused=value.paused,
            changed=value.changed,
            simulation_revision=value.simulation_revision.value,
            frame_revision=value.frame_revision.value,
        )


class SimulationSetPausedRequest(ContractModel):
    """Exact JSON-RPC set-paused request."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    method: Literal["toqraq.simulation.set_paused"]
    params: SimulationSetPausedParams

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        command: SetPausedCommand,
    ) -> SimulationSetPausedRequest:
        """Bind one pure command to a validated request identity."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            method=SIMULATION_SET_PAUSED_METHOD,
            params=SimulationSetPausedParams.from_core(command),
        )


class SimulationSetPausedResponse(ContractModel):
    """Exact JSON-RPC set-paused success response."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    result: SimulationSetPausedResult

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        value: SetPausedAcknowledgement,
        command: SetPausedCommand,
    ) -> SimulationSetPausedResponse:
        """Bind one request-correlated acknowledgement to its identity."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            result=SimulationSetPausedResult.from_core(value, command=command),
        )


class SimulationStepParams(ContractModel):
    """Exact bounded number of paused frames to advance."""

    frame_count: int = Field(ge=1, le=MAX_SIMULATION_STEP_FRAMES)

    def to_core(self) -> StepFramesCommand:
        """Convert strict params to the pure bounded command."""
        return StepFramesCommand(frame_count=self.frame_count)

    @classmethod
    def from_core(cls, value: StepFramesCommand) -> SimulationStepParams:
        """Create canonical params from one validated pure command."""
        return cls(frame_count=value.frame_count)


class SimulationStepResult(ContractModel):
    """Exact successful step that confirms simulation remains paused."""

    frame_count: int = Field(ge=1, le=MAX_SIMULATION_STEP_FRAMES)
    paused: Literal[True]
    simulation_revision: ObservationRevisionValue
    frame_revision: ObservationRevisionValue

    def to_core(self, *, command: StepFramesCommand) -> StepFramesAcknowledgement:
        """Convert and correlate a strict result with its owning command."""
        acknowledgement = StepFramesAcknowledgement(
            frame_count=self.frame_count,
            paused=self.paused,
            simulation_revision=ObservationRevision(value=self.simulation_revision),
            frame_revision=ObservationRevision(value=self.frame_revision),
        )
        validate_step_frames_acknowledgement(acknowledgement, command)
        return acknowledgement

    @classmethod
    def from_core(
        cls,
        value: StepFramesAcknowledgement,
        *,
        command: StepFramesCommand,
    ) -> SimulationStepResult:
        """Create one exact result after correlating its owning command."""
        validate_step_frames_acknowledgement(value, command)
        return cls(
            frame_count=value.frame_count,
            paused=True,
            simulation_revision=value.simulation_revision.value,
            frame_revision=value.frame_revision.value,
        )


class SimulationStepRequest(ContractModel):
    """Exact JSON-RPC bounded frame-step request."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    method: Literal["toqraq.simulation.step"]
    params: SimulationStepParams

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        command: StepFramesCommand,
    ) -> SimulationStepRequest:
        """Bind one pure step command to a validated request identity."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            method=SIMULATION_STEP_METHOD,
            params=SimulationStepParams.from_core(command),
        )


class SimulationStepResponse(ContractModel):
    """Exact JSON-RPC bounded frame-step success response."""

    jsonrpc: Literal["2.0"]
    id: BridgeHostRequestId
    result: SimulationStepResult

    @classmethod
    def from_core(
        cls,
        *,
        request_id: str,
        value: StepFramesAcknowledgement,
        command: StepFramesCommand,
    ) -> SimulationStepResponse:
        """Bind one request-correlated step acknowledgement to its identity."""
        return cls(
            jsonrpc=JSON_RPC_VERSION,
            id=request_id,
            result=SimulationStepResult.from_core(value, command=command),
        )
