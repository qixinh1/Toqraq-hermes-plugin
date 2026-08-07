"""Transport-neutral structured application failures."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import ClassVar

from .error_values import ErrorFields, freeze_error_fields
from .trace import TraceId, error_trace_id

_ERROR_CODE = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*)+$")


class ErrorCategory(StrEnum):
    """Closed transport-neutral error semantics."""

    INVALID = "invalid"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    UPSTREAM = "upstream"
    INTERNAL = "internal"


class ToqraqError(Exception):
    """Base value for an expected application failure."""

    code: ClassVar[str]
    category: ClassVar[ErrorCategory]

    def __init__(
        self,
        *,
        parameters: ErrorFields | None = None,
        details: ErrorFields | None = None,
        cause: BaseException | None = None,
        trace_id: TraceId | None = None,
    ) -> None:
        """Create an immutable, bounded failure.

        Args:
            parameters: Safe localization parameters.
            details: Safe structured recovery facts.
            cause: Original failure retained only for diagnostics.
            trace_id: Existing operation trace, when one is already owned.
        """
        if type(self) is ToqraqError:
            raise TypeError("ToqraqError is an abstract failure boundary")
        if not _ERROR_CODE.fullmatch(self.code):
            raise TypeError("application error code is invalid")
        self.parameters = freeze_error_fields(parameters)
        self.details = freeze_error_fields(details)
        self.cause = cause
        self.trace_id = trace_id or error_trace_id()
        super().__init__(self.code)


class UnsupportedPlatformError(ToqraqError):
    """The current OS provides no implementation for an operation."""

    code = "platform.unsupported"
    category = ErrorCategory.UNAVAILABLE


class PlatformOperationError(ToqraqError):
    """A supported host-platform operation failed."""

    code = "platform.operation_failed"
    category = ErrorCategory.UPSTREAM


class EngineNotFoundError(ToqraqError):
    """No engine adapter is registered for a requested identifier."""

    code = "engine.not_found"
    category = ErrorCategory.NOT_FOUND


class EngineChoiceRequiredError(ToqraqError):
    """Several project probes matched and require one explicit engine choice."""

    code = "engine.choice_required"
    category = ErrorCategory.CONFLICT


class EngineUnavailableError(ToqraqError):
    """This plugin build offers no certified engine contribution."""

    code = "engine.unavailable"
    category = ErrorCategory.UNAVAILABLE


class RuntimeNotInstalledError(ToqraqError):
    """A required managed runtime is absent."""

    code = "runtime.not_installed"
    category = ErrorCategory.UNAVAILABLE


class RuntimeReleaseNotFoundError(ToqraqError):
    """The complete runtime selection is not certified by this plugin build."""

    code = "runtime.release_not_found"
    category = ErrorCategory.NOT_FOUND


class RuntimeVersionChoiceRequiredError(ToqraqError):
    """Several certified releases require one explicit public version choice."""

    code = "runtime.version_choice_required"
    category = ErrorCategory.CONFLICT


class ComponentReleaseInvalidError(ToqraqError):
    """A certified component record shipped with the plugin is unusable."""

    code = "component.release_invalid"
    category = ErrorCategory.INTERNAL


class ComponentReleaseNotFoundError(ToqraqError):
    """The requested release is not certified by this plugin build."""

    code = "component.release_not_found"
    category = ErrorCategory.NOT_FOUND


class ComponentJobNotFoundError(ToqraqError):
    """The requested component operation is absent or no longer retained."""

    code = "component.job_not_found"
    category = ErrorCategory.NOT_FOUND


class ComponentOperationConflictError(ToqraqError):
    """Another mutation currently owns the selected component release."""

    code = "component.operation_conflict"
    category = ErrorCategory.CONFLICT


class ComponentJobLimitError(ToqraqError):
    """The bounded process-wide component job capacity is exhausted."""

    code = "component.job_limit"
    category = ErrorCategory.UNAVAILABLE


class ComponentStorageError(ToqraqError):
    """Managed storage cannot satisfy a component operation."""

    code = "component.storage_unavailable"
    category = ErrorCategory.UNAVAILABLE


class ComponentDownloadError(ToqraqError):
    """An exact component package could not be acquired."""

    code = "component.download_failed"
    category = ErrorCategory.UPSTREAM


class ComponentInstallError(ToqraqError):
    """A package could not produce its certified component tree."""

    code = "component.install_failed"
    category = ErrorCategory.UPSTREAM


class ComponentPublicationError(ToqraqError):
    """A verified component tree could not be published atomically."""

    code = "component.publication_failed"
    category = ErrorCategory.UNAVAILABLE


class ComponentOperationTimeoutError(ToqraqError):
    """Exclusive component mutation ownership was not obtained in time."""

    code = "component.operation_timeout"
    category = ErrorCategory.TIMEOUT


class ComponentOperationError(ToqraqError):
    """A local component operation failed outside a narrower category."""

    code = "component.operation_failed"
    category = ErrorCategory.INTERNAL


class ComponentInUseError(ToqraqError):
    """A running owner prevents removal of the selected component."""

    code = "component.in_use"
    category = ErrorCategory.CONFLICT


class ProjectIntrospectionError(ToqraqError):
    """A project directory cannot be understood safely."""

    code = "project.invalid"
    category = ErrorCategory.INVALID


class ProjectNotBoundError(ToqraqError):
    """The caller owns no recognized live or workspace project."""

    code = "project.not_bound"
    category = ErrorCategory.NOT_FOUND


class LaunchError(ToqraqError):
    """A game process failed during startup."""

    code = "runtime.launch_failed"
    category = ErrorCategory.UPSTREAM


class ProcessTerminationError(ToqraqError):
    """A running game process could not be terminated safely."""

    code = "runtime.termination_failed"
    category = ErrorCategory.UPSTREAM


class SessionNotFoundError(ToqraqError):
    """The requested Hermes-owned game session is absent."""

    code = "session.not_found"
    category = ErrorCategory.NOT_FOUND


class SessionStateError(ToqraqError):
    """Current session ownership or state prevents an operation."""

    code = "session.invalid_state"
    category = ErrorCategory.CONFLICT


class SessionCleanupError(ToqraqError):
    """A session resource failed bounded cleanup and remains owned for retry."""

    code = "session.cleanup_failed"
    category = ErrorCategory.UPSTREAM


class CapabilityUnavailableError(ToqraqError):
    """The launched engine session does not provide a requested feature."""

    code = "perception.capability_unavailable"
    category = ErrorCategory.UNAVAILABLE


class PerceptionStaleError(ToqraqError):
    """A run-scoped revision, cursor, or object reference is no longer current."""

    code = "perception.stale"
    category = ErrorCategory.CONFLICT


class PerceptionObjectNotFoundError(ToqraqError):
    """A requested run-scoped object reference does not identify a live object."""

    code = "perception.object_not_found"
    category = ErrorCategory.NOT_FOUND


class PerceptionFrameUnavailableError(ToqraqError):
    """The running engine cannot provide a frame for its current state."""

    code = "perception.frame_unavailable"
    category = ErrorCategory.UNAVAILABLE


class SimulationStateError(ToqraqError):
    """The live simulation state prevents the requested control operation."""

    code = "simulation.invalid_state"
    category = ErrorCategory.CONFLICT


class InputRejectedError(ToqraqError):
    """The live game state rejects an otherwise valid input batch."""

    code = "input.rejected"
    category = ErrorCategory.CONFLICT


class EmbedError(ToqraqError):
    """A native preview attachment could not be established."""

    code = "preview.attach_failed"
    category = ErrorCategory.UPSTREAM


class HostWindowNotFoundError(EmbedError):
    """The Hermes host window could not be resolved."""

    code = "preview.host_window_not_found"
    category = ErrorCategory.NOT_FOUND


class GameWindowNotFoundError(EmbedError):
    """The game did not expose a usable window before its deadline."""

    code = "preview.game_window_not_found"
    category = ErrorCategory.TIMEOUT


class BridgeConnectionError(ToqraqError):
    """The engine observation and control connection is unavailable."""

    code = "bridge.unavailable"
    category = ErrorCategory.UNAVAILABLE


class ProtocolError(BridgeConnectionError):
    """External request or engine data violates its current protocol."""

    code = "bridge.protocol_invalid"
    category = ErrorCategory.INVALID


class InvalidRequestError(ToqraqError):
    """FastAPI or Pydantic rejected an external HTTP request."""

    code = "request.invalid"
    category = ErrorCategory.INVALID


class RequestCancelledError(ToqraqError):
    """Owned work reached its explicit terminal cancellation state."""

    code = "request.cancelled"
    category = ErrorCategory.CONFLICT


class UnexpectedError(ToqraqError):
    """An implementation failure caught only at an outer boundary."""

    code = "internal.unexpected"
    category = ErrorCategory.INTERNAL


APPLICATION_ERROR_TYPES: tuple[type[ToqraqError], ...] = (
    UnsupportedPlatformError,
    PlatformOperationError,
    EngineNotFoundError,
    EngineChoiceRequiredError,
    EngineUnavailableError,
    RuntimeNotInstalledError,
    RuntimeReleaseNotFoundError,
    RuntimeVersionChoiceRequiredError,
    ComponentReleaseInvalidError,
    ComponentReleaseNotFoundError,
    ComponentJobNotFoundError,
    ComponentOperationConflictError,
    ComponentJobLimitError,
    ComponentStorageError,
    ComponentDownloadError,
    ComponentInstallError,
    ComponentPublicationError,
    ComponentOperationTimeoutError,
    ComponentOperationError,
    ComponentInUseError,
    ProjectIntrospectionError,
    ProjectNotBoundError,
    LaunchError,
    ProcessTerminationError,
    SessionNotFoundError,
    SessionStateError,
    SessionCleanupError,
    CapabilityUnavailableError,
    PerceptionStaleError,
    PerceptionObjectNotFoundError,
    PerceptionFrameUnavailableError,
    SimulationStateError,
    InputRejectedError,
    EmbedError,
    HostWindowNotFoundError,
    GameWindowNotFoundError,
    BridgeConnectionError,
    ProtocolError,
    InvalidRequestError,
    RequestCancelledError,
    UnexpectedError,
)
