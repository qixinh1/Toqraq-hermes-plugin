"""Minimal sequenced events for authoritative session snapshots."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, TypeAlias

from pydantic import Field, TypeAdapter, model_validator

from .base import ContractModel
from .errors import PublicError
from .identifiers import MAX_JSON_INTEGER, HermesSessionId
from .sessions import MAX_UNIX_TIMESTAMP, SessionResult


class SessionEventType(StrEnum):
    """Closed lifecycle and independent-state notification vocabulary."""

    STARTED = "session.started"
    READINESS = "session.readiness"
    PROCESS_STATE = "session.process_state"
    STOPPED = "session.stopped"
    FAILED = "session.failed"


SessionStateEventType: TypeAlias = Literal[
    SessionEventType.STARTED,
    SessionEventType.READINESS,
    SessionEventType.PROCESS_STATE,
    SessionEventType.STOPPED,
]


class SessionStateEvent(ContractModel):
    """State notification carrying the same authoritative REST snapshot."""

    session_id: HermesSessionId
    sequence: int = Field(gt=0, le=MAX_JSON_INTEGER)
    timestamp: float = Field(ge=0, le=MAX_UNIX_TIMESTAMP, allow_inf_nan=False)
    type: SessionStateEventType
    payload: SessionResult

    @model_validator(mode="after")
    def validate_owner(self) -> SessionStateEvent:
        """Keep envelope ownership identical to its session snapshot."""
        if self.payload.id != self.session_id:
            raise ValueError("event session identity does not match its payload")
        return self


class SessionFailurePayload(ContractModel):
    """Retained authoritative state plus one shared public-safe error."""

    session: SessionResult
    error: PublicError


class SessionFailedEvent(ContractModel):
    """Lifecycle operation failure whose session remains authoritative."""

    session_id: HermesSessionId
    sequence: int = Field(gt=0, le=MAX_JSON_INTEGER)
    timestamp: float = Field(ge=0, le=MAX_UNIX_TIMESTAMP, allow_inf_nan=False)
    type: Literal[SessionEventType.FAILED]
    payload: SessionFailurePayload

    @model_validator(mode="after")
    def validate_owner(self) -> SessionFailedEvent:
        """Keep envelope ownership identical to its retained session."""
        if self.payload.session.id != self.session_id:
            raise ValueError("event session identity does not match its payload")
        return self


SessionEvent: TypeAlias = Annotated[
    SessionStateEvent | SessionFailedEvent,
    Field(discriminator="type"),
]
SESSION_EVENT_ADAPTER: TypeAdapter[SessionEvent] = TypeAdapter(SessionEvent)
