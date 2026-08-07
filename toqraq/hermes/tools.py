"""Generated-schema Hermes tools over injected application services."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, ValidationError

from ..contracts.base import ContractModel, EmptyRequest
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
from ..contracts.errors import error_envelope
from ..contracts.frame_capture import FrameCaptureResult
from ..contracts.identifiers import HermesSessionId
from ..contracts.process_output import ProcessOutputResult
from ..contracts.project_inventory import ProjectInventoryRequest, ProjectInventoryResult
from ..contracts.sessions import (
    GameStartRequest,
    SessionResult,
    StepFramesRequest,
)
from ..contracts.setup import SetupRequest, SetupResult
from ..contracts.validation import invalid_request
from ..core.errors import ToqraqError, UnexpectedError
from ..core.failure_diagnostics import failure_diagnostic
from ..core.trace import trace_scope
from .tool_operations import ToolCall, ToolOperations

if TYPE_CHECKING:
    from ..services.container import Container

logger = logging.getLogger(__name__)
RequestT = TypeVar("RequestT", bound=ContractModel)
ResultT = TypeVar("ResultT", bound=BaseModel)
ToolHandler = Callable[..., Awaitable[str]]
ToolOperation = Callable[[RequestT, ToolCall], Awaitable[ResultT]]


class _OwnerContext(ContractModel):
    """Validated Hermes-owned identity outside the model-visible schema."""

    task_id: HermesSessionId


@dataclass(frozen=True)
class ToolRegistration:
    """One generated Hermes tool declaration and bound handler."""

    name: str
    description: str
    request_model: type[ContractModel]
    result_model: type[BaseModel]
    schema: dict[str, Any]
    handler: ToolHandler


@dataclass(frozen=True)
class ToolSpec:
    """Single source for one tool's identity, schema, and bound operation."""

    name: str
    description: str
    bind: Callable[[ToolOperations], ToolRegistration]


def _tool_spec(
    name: str,
    description: str,
    request_model: type[RequestT],
    result_model: type[ResultT],
    operation: Callable[[ToolOperations], ToolOperation[RequestT, ResultT]],
    *,
    owner: bool = False,
) -> ToolSpec:
    """Keep a heterogeneous typed operation attached to its declaration."""

    def bind(operations: ToolOperations) -> ToolRegistration:
        return _tool(
            name,
            description,
            request_model,
            result_model,
            operation(operations),
            owner=owner,
        )

    return ToolSpec(name=name, description=description, bind=bind)


TOOL_SPECS = (
    _tool_spec(
        "toqraq_project_setup",
        "Inspect a game project and its exact managed-runtime setup state without changing it.",
        SetupRequest,
        SetupResult,
        lambda operations: operations.project_setup,
    ),
    _tool_spec(
        "toqraq_project_read_inventory",
        "Read bounded scene, script, resource, setting, dependency, and input "
        "metadata for this task's project.",
        ProjectInventoryRequest,
        ProjectInventoryResult,
        lambda operations: operations.project_inventory,
        owner=True,
    ),
    _tool_spec(
        "toqraq_game_start",
        "Start a project as the game owned by this Hermes session.",
        GameStartRequest,
        SessionResult,
        lambda operations: operations.game_start,
        owner=True,
    ),
    _tool_spec(
        "toqraq_game_stop",
        "Stop the game owned by this Hermes session.",
        EmptyRequest,
        SessionResult,
        lambda operations: operations.game_stop,
        owner=True,
    ),
    _tool_spec(
        "toqraq_game_pause",
        "Pause the current game's simulation.",
        EmptyRequest,
        SessionResult,
        lambda operations: operations.game_pause,
        owner=True,
    ),
    _tool_spec(
        "toqraq_game_resume",
        "Resume the current game's simulation.",
        EmptyRequest,
        SessionResult,
        lambda operations: operations.game_resume,
        owner=True,
    ),
    _tool_spec(
        "toqraq_game_step",
        "Advance an exact bounded frame count while the current game is paused.",
        StepFramesRequest,
        SessionResult,
        lambda operations: operations.game_step,
        owner=True,
    ),
    _tool_spec(
        "toqraq_game_read_hierarchy",
        "Read a bounded, revision-consistent live hierarchy page from the current game.",
        HierarchyReadParams,
        HierarchyReadResult,
        lambda operations: operations.read_hierarchy,
        owner=True,
    ),
    _tool_spec(
        "toqraq_game_read_objects",
        "Read selected field groups for explicit live-object references in the current game.",
        ObjectReadParams,
        ObjectReadResult,
        lambda operations: operations.read_objects,
        owner=True,
    ),
    _tool_spec(
        "toqraq_game_read_diagnostics",
        "Read a bounded, filtered diagnostics page from the current game.",
        DiagnosticsReadParams,
        DiagnosticsReadResult,
        lambda operations: operations.read_diagnostics,
        owner=True,
    ),
    _tool_spec(
        "toqraq_game_read_process_output",
        "Read the latest bounded stdout/stderr tail from the current game process.",
        EmptyRequest,
        ProcessOutputResult,
        lambda operations: operations.read_process_output,
        owner=True,
    ),
    _tool_spec(
        "toqraq_game_read_metrics",
        "Read selected live performance metrics from the current game.",
        MetricsReadParams,
        MetricsReadResult,
        lambda operations: operations.read_metrics,
        owner=True,
    ),
    _tool_spec(
        "toqraq_game_capture_frame",
        "Capture one verified, size-bounded PNG frame from the current game.",
        FrameCaptureParams,
        FrameCaptureResult,
        lambda operations: operations.capture_frame,
        owner=True,
    ),
    _tool_spec(
        "toqraq_game_input_semantic",
        "Apply an ordered batch of project-defined semantic actions to the current game.",
        SemanticInputParams,
        InputAcknowledgementValue,
        lambda operations: operations.input_semantic,
        owner=True,
    ),
    _tool_spec(
        "toqraq_game_input_keyboard",
        "Apply an ordered batch of W3C keyboard events to the current game.",
        KeyboardInputParams,
        InputAcknowledgementValue,
        lambda operations: operations.input_keyboard,
        owner=True,
    ),
    _tool_spec(
        "toqraq_game_input_pointer",
        "Apply an ordered pointer batch in an explicit viewport coordinate space.",
        PointerInputParams,
        InputAcknowledgementValue,
        lambda operations: operations.input_pointer,
        owner=True,
    ),
    _tool_spec(
        "toqraq_game_input_text",
        "Commit one bounded Unicode text event to the current game's focused surface.",
        TextInputParams,
        InputAcknowledgementValue,
        lambda operations: operations.input_text,
        owner=True,
    ),
    _tool_spec(
        "toqraq_game_input_gamepad",
        "Apply an ordered standard-layout gamepad batch to the current game.",
        GamepadInputParams,
        InputAcknowledgementValue,
        lambda operations: operations.input_gamepad,
        owner=True,
    ),
)


def build_tools(container: Container) -> tuple[ToolRegistration, ...]:
    """Build all tool schemas and handlers from the single declaration table."""
    operations = ToolOperations(container)
    return tuple(spec.bind(operations) for spec in TOOL_SPECS)


def _tool(
    name: str,
    description: str,
    request_model: type[RequestT],
    result_model: type[ResultT],
    operation: ToolOperation[RequestT, ResultT],
    *,
    owner: bool = False,
) -> ToolRegistration:
    """Generate one declaration directly from its request model."""
    schema = {
        "name": name,
        "description": description,
        "parameters": request_model.model_json_schema(),
    }
    return ToolRegistration(
        name=name,
        description=description,
        request_model=request_model,
        result_model=result_model,
        schema=schema,
        handler=_handler(request_model, result_model, operation, owner=owner),
    )


def _handler(
    request_model: type[RequestT],
    result_model: type[ResultT],
    operation: ToolOperation[RequestT, ResultT],
    *,
    owner: bool,
) -> ToolHandler:
    """Validate, execute, and serialize one generated-schema tool."""

    async def handle(arguments: object, **kwargs: object) -> str:
        candidate = kwargs.get("trace_id")
        with trace_scope(candidate if isinstance(candidate, str) else None):
            try:
                try:
                    request = request_model.model_validate(arguments)
                    owner_id = _owner(kwargs) if owner else None
                except ValidationError as exc:
                    return _error_json(invalid_request(exc.errors()))

                result = await operation(request, ToolCall(owner_id))
                if type(result) is not result_model:
                    raise TypeError("Hermes tool operation returned an invalid result contract")
                return _json(result)
            except ToqraqError as exc:
                return _error_json(exc)
            except Exception as exc:
                error = UnexpectedError(cause=exc)
                _log_unexpected(error, exc)
                return _error_json(error)

    return handle


def _owner(kwargs: dict[str, object]) -> HermesSessionId:
    """Validate the host-owned session ID outside model-visible arguments."""
    payload = {"task_id": kwargs["task_id"]} if "task_id" in kwargs else {}
    context = _OwnerContext.model_validate(payload)
    return context.task_id


def _json(result: BaseModel) -> str:
    """Serialize one successful result model using its public aliases."""
    payload = result.model_dump(mode="json", by_alias=True)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _error_json(error: ToqraqError) -> str:
    """Serialize one shared safe error envelope."""
    payload = error_envelope(error).model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _log_unexpected(error: UnexpectedError, exception: BaseException) -> None:
    """Log reviewed fields for an unexpected Hermes tool failure."""
    diagnostic = failure_diagnostic(exception)
    logger.error(
        "unexpected Hermes tool failure trace_id=%s exception_type=%s stack_locations=%s",
        error.trace_id,
        diagnostic.exception_type,
        ",".join(diagnostic.stack_locations),
    )
