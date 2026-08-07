"""Hermes tool intentions routed to the focused application services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..contracts.base import EmptyRequest
from ..contracts.bridge_diagnostics import DiagnosticsReadParams, DiagnosticsReadResult
from ..contracts.bridge_frame import FrameCaptureParams
from ..contracts.bridge_hierarchy import HierarchyReadParams, HierarchyReadResult
from ..contracts.bridge_input import (
    GamepadInputParams,
    InputAcknowledgementValue,
    KeyboardInputParams,
    PointerInputParams,
    SemanticInputParams,
    TextInputParams,
)
from ..contracts.bridge_metrics import MetricsReadParams, MetricsReadResult
from ..contracts.bridge_objects import ObjectReadParams, ObjectReadResult
from ..contracts.frame_capture import FrameCaptureResult
from ..contracts.identifiers import HermesSessionId
from ..contracts.process_output import ProcessOutputResult
from ..contracts.project_inventory import ProjectInventoryRequest, ProjectInventoryResult
from ..contracts.sessions import (
    GameStartRequest,
    SessionResult,
    SetPausedRequest,
    StepFramesRequest,
)
from ..contracts.setup import SetupRequest, SetupResult
from ..contracts.validation import invalid_request

if TYPE_CHECKING:
    from ..services.container import Container


@dataclass(frozen=True)
class ToolCall:
    """Host facts attached to one tool invocation."""

    owner_id: HermesSessionId | None

    def require_owner(self) -> HermesSessionId:
        """Return the owning Hermes task ID for a game operation."""
        if self.owner_id is None:
            raise invalid_request(({"loc": ("task_id",), "type": "missing"},))
        return self.owner_id


class ToolOperations:
    """Route tool-specific commands through one injected service graph."""

    def __init__(self, container: Container) -> None:
        """Bind every operation to the registered focused services."""
        self._container = container

    async def project_setup(self, request: SetupRequest, _call: ToolCall) -> SetupResult:
        """Inspect project and exact managed-runtime readiness without mutation."""
        return await self._container.setup_service.check(request)

    async def project_inventory(
        self,
        request: ProjectInventoryRequest,
        call: ToolCall,
    ) -> ProjectInventoryResult:
        """Read one bounded inventory page from the caller's preferred project."""
        return await self._container.project_inventory_service.read(
            call.require_owner(),
            request,
        )

    async def game_start(self, request: GameStartRequest, call: ToolCall) -> SessionResult:
        """Start the game owned by the calling Hermes session."""
        return await self._container.session_service.start(call.require_owner(), request)

    async def game_stop(self, _request: EmptyRequest, call: ToolCall) -> SessionResult:
        """Stop the game owned by the calling Hermes session."""
        return await self._container.session_service.stop(call.require_owner())

    async def game_pause(self, _request: EmptyRequest, call: ToolCall) -> SessionResult:
        """Pause the game owned by the calling Hermes session."""
        request = SetPausedRequest(paused=True)
        return await self._container.simulation_service.set_paused(call.require_owner(), request)

    async def game_resume(self, _request: EmptyRequest, call: ToolCall) -> SessionResult:
        """Resume the game owned by the calling Hermes session."""
        request = SetPausedRequest(paused=False)
        return await self._container.simulation_service.set_paused(call.require_owner(), request)

    async def game_step(self, request: StepFramesRequest, call: ToolCall) -> SessionResult:
        """Advance an exact bounded frame count while the game is paused."""
        return await self._container.simulation_service.step(call.require_owner(), request)

    async def read_hierarchy(
        self,
        request: HierarchyReadParams,
        call: ToolCall,
    ) -> HierarchyReadResult:
        """Read one bounded hierarchy page from the caller's game."""
        return await self._container.hierarchy_service.read(call.require_owner(), request)

    async def read_objects(
        self,
        request: ObjectReadParams,
        call: ToolCall,
    ) -> ObjectReadResult:
        """Read selected field groups for explicit live-object references."""
        return await self._container.object_inspection_service.read(call.require_owner(), request)

    async def read_diagnostics(
        self,
        request: DiagnosticsReadParams,
        call: ToolCall,
    ) -> DiagnosticsReadResult:
        """Read one filtered diagnostics page from the caller's game."""
        return await self._container.diagnostics_service.read(call.require_owner(), request)

    async def read_process_output(
        self,
        _request: EmptyRequest,
        call: ToolCall,
    ) -> ProcessOutputResult:
        """Read the latest bounded process-output tail from the caller's game."""
        return await self._container.process_output_service.read(call.require_owner())

    async def read_metrics(
        self,
        request: MetricsReadParams,
        call: ToolCall,
    ) -> MetricsReadResult:
        """Read one selected performance snapshot from the caller's game."""
        return await self._container.metrics_service.read(call.require_owner(), request)

    async def capture_frame(
        self,
        request: FrameCaptureParams,
        call: ToolCall,
    ) -> FrameCaptureResult:
        """Capture one verified PNG frame from the caller's game."""
        return await self._container.frame_capture_service.capture(call.require_owner(), request)

    async def input_semantic(
        self,
        request: SemanticInputParams,
        call: ToolCall,
    ) -> InputAcknowledgementValue:
        """Apply one ordered semantic-action batch to the caller's game."""
        return await self._container.input_service.semantic(call.require_owner(), request)

    async def input_keyboard(
        self,
        request: KeyboardInputParams,
        call: ToolCall,
    ) -> InputAcknowledgementValue:
        """Apply one ordered W3C keyboard batch to the caller's game."""
        return await self._container.input_service.keyboard(call.require_owner(), request)

    async def input_pointer(
        self,
        request: PointerInputParams,
        call: ToolCall,
    ) -> InputAcknowledgementValue:
        """Apply one pointer batch in an explicit coordinate space."""
        return await self._container.input_service.pointer(call.require_owner(), request)

    async def input_text(
        self,
        request: TextInputParams,
        call: ToolCall,
    ) -> InputAcknowledgementValue:
        """Commit one bounded Unicode text event to the caller's game."""
        return await self._container.input_service.text(call.require_owner(), request)

    async def input_gamepad(
        self,
        request: GamepadInputParams,
        call: ToolCall,
    ) -> InputAcknowledgementValue:
        """Apply one standard-layout gamepad batch to the caller's game."""
        return await self._container.input_service.gamepad(call.require_owner(), request)
