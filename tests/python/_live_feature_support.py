"""Complete in-memory focused ports for live feature service tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar, cast

from toqraq.core.bridge import BridgeOwnerKey
from toqraq.core.capability_ids import MANDATORY_BRIDGE_CAPABILITY_IDS
from toqraq.core.diagnostics import DiagnosticsPage, DiagnosticsQuery
from toqraq.core.frame_capture import FrameCaptureQuery, FrameCaptureResult
from toqraq.core.hierarchy import HierarchyPage, HierarchyQuery
from toqraq.core.input_control import (
    GamepadInputCommand,
    InputAcknowledgement,
    InputCommand,
    KeyboardInputCommand,
    PointerInputCommand,
    SemanticInputCommand,
    TextInputCommand,
    input_command_event_count,
)
from toqraq.core.metrics import MetricsQuery, MetricsSnapshot
from toqraq.core.object_inspection import ObjectReadQuery, ObjectSnapshot
from toqraq.core.runtime_features import RuntimeFeaturePorts
from toqraq.core.session import EngineSession
from toqraq.core.session_registry import SessionRegistry
from toqraq.services.session_gate import SessionOperationGate

from _bridge_feature_values import (
    diagnostics_values,
    frame_values,
    hierarchy_values,
    metrics_values,
    object_values,
)
from _session_domain_support import FakeFeaturePorts, make_session

QueryT = TypeVar("QueryT")
ResultT = TypeVar("ResultT")


class RecordingReader(Generic[QueryT, ResultT]):
    """Return one exact result while retaining every focused query."""

    def __init__(self, result: ResultT) -> None:
        self.result = result
        self.queries: list[QueryT] = []

    async def read(self, query: QueryT) -> ResultT:
        """Record the exact query and return the configured result."""
        self.queries.append(query)
        return self.result


class RecordingFrameCapture:
    """Return one exact complete frame while retaining every query."""

    def __init__(self, result: FrameCaptureResult) -> None:
        self.result = result
        self.queries: list[FrameCaptureQuery] = []

    async def capture(self, query: FrameCaptureQuery) -> FrameCaptureResult:
        """Record the exact query and return complete verified bytes."""
        self.queries.append(query)
        return self.result


class RecordingInputController:
    """Retain all five engine-neutral commands and acknowledge atomically."""

    def __init__(self) -> None:
        self.commands: list[InputCommand] = []
        self.accepted_event_count: int | None = None

    async def semantic(self, command: SemanticInputCommand) -> InputAcknowledgement:
        """Record one semantic command."""
        return self._record(command)

    async def keyboard(self, command: KeyboardInputCommand) -> InputAcknowledgement:
        """Record one W3C keyboard command."""
        return self._record(command)

    async def pointer(self, command: PointerInputCommand) -> InputAcknowledgement:
        """Record one pointer command."""
        return self._record(command)

    async def text(self, command: TextInputCommand) -> InputAcknowledgement:
        """Record one Unicode text command."""
        return self._record(command)

    async def gamepad(self, command: GamepadInputCommand) -> InputAcknowledgement:
        """Record one standard-layout gamepad command."""
        return self._record(command)

    def _record(self, command: InputCommand) -> InputAcknowledgement:
        """Return the configured or exact command-derived acknowledgement."""
        self.commands.append(command)
        count = self.accepted_event_count
        return InputAcknowledgement(
            accepted_event_count=(input_command_event_count(command) if count is None else count)
        )


@dataclass(frozen=True, slots=True)
class LiveFeatureFixture:
    """One committed current session with all focused test ports ready."""

    registry: SessionRegistry
    gate: SessionOperationGate
    session: EngineSession
    ports: FakeFeaturePorts
    hierarchy: RecordingReader[HierarchyQuery, HierarchyPage]
    objects: RecordingReader[ObjectReadQuery, ObjectSnapshot]
    diagnostics: RecordingReader[DiagnosticsQuery, DiagnosticsPage]
    metrics: RecordingReader[MetricsQuery, MetricsSnapshot]
    frame: RecordingFrameCapture
    input: RecordingInputController

    async def close(self) -> None:
        """Release and discard the complete owner graph."""
        await self.session.close()
        assert self.registry.discard_if(self.session)


def make_live_feature_fixture(
    root: Path,
    *,
    publish_features: bool = True,
    bridge_capability_ids: frozenset[str] = MANDATORY_BRIDGE_CAPABILITY_IDS,
) -> LiveFeatureFixture:
    """Build one exact current run and optionally publish its focused ports."""
    registry = SessionRegistry()
    gate = SessionOperationGate()
    owner: BridgeOwnerKey = registry.issue_owner("hermes-session")
    session, _process, _connection, ports, _runtime_lease = make_session(
        root,
        owner,
        bridge_capability_ids=bridge_capability_ids,
    )

    _hierarchy_query, hierarchy_result = hierarchy_values()
    _object_query, object_result = object_values()
    _diagnostics_query, diagnostics_result = diagnostics_values()
    _metrics_query, metrics_result = metrics_values()
    _frame_query, frame_result = frame_values()
    hierarchy = RecordingReader(hierarchy_result)
    objects = RecordingReader(object_result)
    diagnostics = RecordingReader(diagnostics_result)
    metrics = RecordingReader(metrics_result)
    frame = RecordingFrameCapture(frame_result)
    input_controller = RecordingInputController()
    ports.hierarchy = hierarchy
    ports.objects = objects
    ports.diagnostics = diagnostics
    ports.metrics = metrics
    ports.frame = frame
    ports.input = input_controller

    assert registry.compare_and_swap(None, session)
    if publish_features:
        session.publish_features(cast(RuntimeFeaturePorts, ports))
    return LiveFeatureFixture(
        registry=registry,
        gate=gate,
        session=session,
        ports=ports,
        hierarchy=hierarchy,
        objects=objects,
        diagnostics=diagnostics,
        metrics=metrics,
        frame=frame,
        input=input_controller,
    )
