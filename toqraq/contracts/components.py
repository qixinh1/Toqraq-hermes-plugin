"""Managed component catalog and asynchronous job contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from ..core.component import (
    ComponentJobAction,
    ComponentKind,
    ComponentReadiness,
    ComponentWorkPhase,
)
from .base import ContractModel
from .errors import PublicError
from .identifiers import (
    MAX_JSON_INTEGER,
    CapabilityId,
    ComponentBuildId,
    ComponentId,
    ComponentOperationId,
    ComponentReleaseId,
    ComponentVersion,
    DisplayName,
    HttpsUrlValue,
    PlatformId,
    Sha256Value,
)

MAX_ACTIVE_COMPONENT_JOB_RESULTS = 64


class ComponentJobState(StrEnum):
    """Lifecycle of one process-owned component operation."""

    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE_COMPONENT_JOB_STATES = frozenset(
    {
        ComponentJobState.QUEUED,
        ComponentJobState.RUNNING,
        ComponentJobState.CANCELLING,
    }
)


class ComponentSourceResult(ContractModel):
    """Reviewed provenance displayed before component preparation."""

    publisher: DisplayName
    package_url: HttpsUrlValue
    provenance_url: HttpsUrlValue


class ComponentLicenseResult(ContractModel):
    """License facts and whether user acceptance is required."""

    identifier: ComponentVersion
    name: DisplayName
    url: HttpsUrlValue
    acceptance_required: bool


class ComponentReleaseResult(ContractModel):
    """One selectable certified release without local filesystem details."""

    release_id: ComponentReleaseId
    component_id: ComponentId
    kind: ComponentKind
    label: DisplayName
    version: ComponentVersion
    build_id: ComponentBuildId
    platform: PlatformId
    architecture: PlatformId
    package_bytes: int = Field(gt=0, le=MAX_JSON_INTEGER)
    installed_bytes: int = Field(gt=0, le=MAX_JSON_INTEGER)
    package_sha256: Sha256Value
    source: ComponentSourceResult
    license: ComponentLicenseResult
    authentication_required: bool
    capabilities: tuple[CapabilityId, ...] = Field(max_length=64)
    readiness: ComponentReadiness
    in_use: bool


class ComponentListResult(ContractModel):
    """Complete bounded release catalog available to this plugin build."""

    releases: tuple[ComponentReleaseResult, ...] = Field(max_length=512)


class ComponentJobStartRequest(ContractModel):
    """Start or join one exact component mutation."""

    release_id: ComponentReleaseId
    action: ComponentJobAction

    @field_validator("action", mode="before")
    @classmethod
    def decode_action(cls, value: object) -> ComponentJobAction:
        """Decode one exact JSON string without enabling general coercion."""
        if isinstance(value, ComponentJobAction):
            return value
        if type(value) is str:
            try:
                return ComponentJobAction(value)
            except ValueError:
                pass
        raise ValueError("component job action is invalid")


class ComponentJobResult(ContractModel):
    """Authoritative reconciled snapshot of one asynchronous component job."""

    operation_id: ComponentOperationId
    release_id: ComponentReleaseId
    component_id: ComponentId
    action: ComponentJobAction
    state: ComponentJobState
    phase: ComponentWorkPhase
    completed_bytes: int = Field(ge=0, le=MAX_JSON_INTEGER)
    total_bytes: int = Field(ge=0, le=MAX_JSON_INTEGER)
    revision: int = Field(gt=0, le=MAX_JSON_INTEGER)
    error: PublicError | None = None

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        """Require coherent progress, terminal phase, and failure payload."""
        if self.completed_bytes > self.total_bytes:
            raise ValueError("component job progress exceeds its total")
        if (self.state is ComponentJobState.FAILED) != (self.error is not None):
            raise ValueError("only a failed component job carries an error")
        if self.state is ComponentJobState.READY:
            if self.phase is not ComponentWorkPhase.READY:
                raise ValueError("ready component job must be in the ready phase")
            if self.completed_bytes != self.total_bytes:
                raise ValueError("ready component job must complete its byte total")
        elif self.phase is ComponentWorkPhase.READY:
            raise ValueError("ready phase requires ready component job state")
        return self


class ComponentActiveJobsResult(ContractModel):
    """Bounded creation-ordered snapshots of currently active jobs."""

    jobs: tuple[ComponentJobResult, ...] = Field(max_length=MAX_ACTIVE_COMPONENT_JOB_RESULTS)

    @model_validator(mode="after")
    def validate_jobs(self) -> Self:
        """Reject terminal, duplicate-operation, or duplicate-release entries."""
        if any(job.state not in ACTIVE_COMPONENT_JOB_STATES for job in self.jobs):
            raise ValueError("active component job result contains a terminal job")
        if len({job.operation_id for job in self.jobs}) != len(self.jobs):
            raise ValueError("active component job operations must be unique")
        if len({job.release_id for job in self.jobs}) != len(self.jobs):
            raise ValueError("active component job releases must be unique")
        return self
