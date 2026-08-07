"""Pure simulation commands, acknowledgements, and focused control port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .observation import ObservationRevision

MAX_SIMULATION_STEP_FRAMES = 120


@dataclass(frozen=True, slots=True, kw_only=True)
class SetPausedCommand:
    """Desired simulation state; repeated application is idempotent."""

    paused: bool

    def __post_init__(self) -> None:
        """Reject truthy substitutes at the pure boundary."""
        if type(self.paused) is not bool:
            raise ValueError("simulation paused state is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class SetPausedAcknowledgement:
    """Resulting pause state and authoritative control revisions."""

    paused: bool
    changed: bool
    simulation_revision: ObservationRevision
    frame_revision: ObservationRevision

    def __post_init__(self) -> None:
        """Require an exact state acknowledgement with two run-scoped revisions."""
        if type(self.paused) is not bool or type(self.changed) is not bool:
            raise ValueError("simulation pause acknowledgement is invalid")
        _validate_revisions(
            simulation=self.simulation_revision,
            frame=self.frame_revision,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class StepFramesCommand:
    """Bounded exact frame count to advance while simulation is paused."""

    frame_count: int

    def __post_init__(self) -> None:
        """Reject booleans, zero work, and unbounded frame advancement."""
        if (
            isinstance(self.frame_count, bool)
            or not isinstance(self.frame_count, int)
            or not 1 <= self.frame_count <= MAX_SIMULATION_STEP_FRAMES
        ):
            raise ValueError("simulation step frame count is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class StepFramesAcknowledgement:
    """Exact completed step that leaves simulation paused."""

    frame_count: int
    paused: bool
    simulation_revision: ObservationRevision
    frame_revision: ObservationRevision

    def __post_init__(self) -> None:
        """Reject partial-success and resume-shaped acknowledgements."""
        StepFramesCommand(frame_count=self.frame_count)
        if self.paused is not True:
            raise ValueError("simulation step acknowledgement must remain paused")
        _validate_revisions(
            simulation=self.simulation_revision,
            frame=self.frame_revision,
        )


def validate_set_paused_acknowledgement(
    acknowledgement: SetPausedAcknowledgement,
    command: SetPausedCommand,
) -> None:
    """Correlate the resulting state with the exact requested state."""
    if not isinstance(acknowledgement, SetPausedAcknowledgement):
        raise TypeError("simulation pause acknowledgement is invalid")
    if not isinstance(command, SetPausedCommand):
        raise TypeError("simulation pause command is invalid")
    if acknowledgement.paused != command.paused:
        raise ValueError("simulation pause acknowledgement does not match its command")


def validate_step_frames_acknowledgement(
    acknowledgement: StepFramesAcknowledgement,
    command: StepFramesCommand,
) -> None:
    """Correlate completed frame work with the exact requested count."""
    if not isinstance(acknowledgement, StepFramesAcknowledgement):
        raise TypeError("simulation step acknowledgement is invalid")
    if not isinstance(command, StepFramesCommand):
        raise TypeError("simulation step command is invalid")
    if acknowledgement.frame_count != command.frame_count:
        raise ValueError("simulation step acknowledgement does not match its command")


@runtime_checkable
class SimulationController(Protocol):
    """Engine boundary for immediate pause state and bounded frame stepping."""

    async def set_paused(self, command: SetPausedCommand) -> SetPausedAcknowledgement:
        """Set, rather than toggle, the desired simulation state."""
        ...

    async def step(self, command: StepFramesCommand) -> StepFramesAcknowledgement:
        """Advance the exact requested frames or fail without partial success."""
        ...


def _validate_revisions(
    *,
    simulation: ObservationRevision,
    frame: ObservationRevision,
) -> None:
    """Require both independently authoritative observation families."""
    if not isinstance(simulation, ObservationRevision):
        raise ValueError("simulation revision is invalid")
    if not isinstance(frame, ObservationRevision):
        raise ValueError("simulation frame revision is invalid")
