"""Bounded asynchronous use cases for managed component operations."""

from __future__ import annotations

import asyncio
import logging
import math
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from ..contracts.components import (
    ACTIVE_COMPONENT_JOB_STATES,
    MAX_ACTIVE_COMPONENT_JOB_RESULTS,
    ComponentActiveJobsResult,
    ComponentJobResult,
    ComponentLicenseResult,
    ComponentListResult,
    ComponentReleaseResult,
    ComponentSourceResult,
)
from ..contracts.errors import error_envelope
from ..core.component import (
    ComponentInventory,
    ComponentJobAction,
    ComponentPreparation,
    ComponentRemoval,
    ComponentWorkCancelledError,
    ManagedComponent,
)
from ..core.errors import (
    ComponentJobLimitError,
    ComponentJobNotFoundError,
    ComponentOperationConflictError,
    ComponentOperationError,
    ComponentOperationTimeoutError,
    ToqraqError,
    UnexpectedError,
)
from ..core.failure_diagnostics import failure_diagnostic
from ..core.tasks import wait_owned_tasks
from .component_job_state import ComponentJob

logger = logging.getLogger(__name__)

MAX_ACTIVE_COMPONENT_JOBS = MAX_ACTIVE_COMPONENT_JOB_RESULTS
MAX_RETAINED_COMPONENT_JOBS = 1_024
MAX_COMPONENT_SHUTDOWN_SECONDS = 300.0
DEFAULT_ACTIVE_COMPONENT_JOBS = 4
DEFAULT_RETAINED_COMPONENT_JOBS = 128
DEFAULT_COMPONENT_SHUTDOWN_SECONDS = 35.0
_OPERATION_ID_ATTEMPTS = 8


@dataclass(frozen=True, slots=True)
class ComponentJobPolicy:
    """Injected process-wide concurrency, retention, and shutdown bounds."""

    max_active_jobs: int
    max_terminal_jobs: int
    shutdown_timeout_seconds: float

    def __post_init__(self) -> None:
        """Reject ineffective or unbounded process ownership policy."""
        integer_limits = (
            (self.max_active_jobs, MAX_ACTIVE_COMPONENT_JOBS),
            (self.max_terminal_jobs, MAX_RETAINED_COMPONENT_JOBS),
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum
            for value, maximum in integer_limits
        ):
            raise ValueError("component job limits are outside their supported bounds")
        timeout = self.shutdown_timeout_seconds
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or not 0 < timeout <= MAX_COMPONENT_SHUTDOWN_SECONDS
        ):
            raise ValueError("component shutdown timeout is outside its supported bounds")


def component_job_policy() -> ComponentJobPolicy:
    """Return the production process ownership and retention policy."""
    return ComponentJobPolicy(
        max_active_jobs=DEFAULT_ACTIVE_COMPONENT_JOBS,
        max_terminal_jobs=DEFAULT_RETAINED_COMPONENT_JOBS,
        shutdown_timeout_seconds=DEFAULT_COMPONENT_SHUTDOWN_SECONDS,
    )


class ComponentJobService:
    """Own background component mutations and their bounded public snapshots."""

    def __init__(
        self,
        inventory: ComponentInventory,
        preparation: ComponentPreparation,
        removal: ComponentRemoval,
        policy: ComponentJobPolicy,
        *,
        operation_id_factory: Callable[[], str] | None = None,
    ) -> None:
        """Bind component ports and all process-level ownership policy."""
        self._inventory = inventory
        self._preparation = preparation
        self._removal = removal
        self._policy = policy
        self._operation_id_factory = operation_id_factory or _new_operation_id
        self._jobs: OrderedDict[str, ComponentJob] = OrderedDict()
        self._active_releases: dict[str, str] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._lock = threading.RLock()
        self._closing = False

    async def list_components(self) -> ComponentListResult:
        """Read the potentially filesystem-backed inventory off the event loop."""
        components = await asyncio.to_thread(self._inventory.list_components)
        return ComponentListResult(releases=tuple(_release_result(item) for item in components))

    async def start_job(
        self,
        release_id: str,
        action: ComponentJobAction,
    ) -> ComponentJobResult:
        """Start, or idempotently join, one exact active release mutation."""
        with self._lock:
            self._require_accepting()
        component = await asyncio.to_thread(self._inventory.require_component, release_id)
        with self._lock:
            self._require_accepting()
            active_id = self._active_releases.get(release_id)
            if active_id is not None:
                active = self._jobs[active_id]
                if active.action is action:
                    return active.snapshot()
                raise ComponentOperationConflictError(
                    parameters={"release_id": release_id},
                    details={"active_action": active.action.value},
                )
            if len(self._active_releases) >= self._policy.max_active_jobs:
                raise ComponentJobLimitError(
                    parameters={"maximum": self._policy.max_active_jobs},
                    details={"reason": "active_job_limit"},
                )
            operation_id = self._allocate_operation_id()
            job = ComponentJob(operation_id, component, action)
            self._jobs[operation_id] = job
            self._active_releases[release_id] = operation_id
            task = asyncio.create_task(
                self._run_job(job),
                name=f"toqraq-component-{operation_id}",
            )
            self._tasks[operation_id] = task
            return job.snapshot()

    def get_job(self, operation_id: str) -> ComponentJobResult:
        """Return one retained authoritative job snapshot."""
        with self._lock:
            job = self._jobs.get(operation_id)
            if job is None:
                raise ComponentJobNotFoundError(parameters={"operation_id": operation_id})
            return job.snapshot()

    def list_active_jobs(self) -> ComponentActiveJobsResult:
        """Return active public snapshots in deterministic creation order."""
        with self._lock:
            snapshots = tuple(
                self._jobs[operation_id].snapshot()
                for operation_id in self._active_releases.values()
            )
        return ComponentActiveJobsResult(
            jobs=tuple(job for job in snapshots if job.state in ACTIVE_COMPONENT_JOB_STATES)
        )

    def cancel_job(self, operation_id: str) -> ComponentJobResult:
        """Request cooperative cancellation and return the resulting snapshot."""
        with self._lock:
            job = self._jobs.get(operation_id)
            if job is None:
                raise ComponentJobNotFoundError(parameters={"operation_id": operation_id})
            job.request_cancellation()
            return job.snapshot()

    async def close(self) -> None:
        """Cancel owned work and wait a bounded time without abandoning workers."""
        self.begin_close()
        with self._lock:
            tasks = tuple(self._tasks.values())
        if not tasks:
            return
        try:
            await wait_owned_tasks(
                tasks,
                cancel=False,
                timeout=self._policy.shutdown_timeout_seconds,
            )
        except TimeoutError as exc:
            pending = sum(not task.done() for task in tasks)
            raise ComponentOperationTimeoutError(
                parameters={"pending_jobs": pending},
                details={"reason": "shutdown_deadline"},
                cause=exc,
            ) from exc
        except RuntimeError as exc:
            raise ComponentOperationError(
                details={"reason": "task_owner_loop_unavailable", "retryable": True},
                cause=exc,
            ) from exc

    def begin_close(self) -> None:
        """Reject new jobs and request cancellation for every current owner."""
        with self._lock:
            self._closing = True
            for operation_id in self._tasks:
                self._jobs[operation_id].request_cancellation()

    def _require_accepting(self) -> None:
        """Reject work after the plugin instance begins disposal."""
        if self._closing:
            raise ComponentOperationError(details={"reason": "plugin_closing", "retryable": True})

    async def _run_job(self, job: ComponentJob) -> None:
        """Run one synchronous adapter behind the service-owned task."""
        try:
            job.mark_running()
            await asyncio.to_thread(self._execute, job)
            job.mark_ready()
        except ComponentWorkCancelledError:
            job.mark_cancelled()
        except ToqraqError as exc:
            job.mark_failed(error_envelope(exc).error)
        except asyncio.CancelledError:
            job.request_cancellation()
            raise
        except Exception as exc:
            error = UnexpectedError(cause=exc)
            diagnostic = failure_diagnostic(exc)
            logger.error(
                "unexpected component job failure trace_id=%s operation_id=%s "
                "exception_type=%s stack_locations=%s",
                error.trace_id,
                job.operation_id,
                diagnostic.exception_type,
                ",".join(diagnostic.stack_locations),
            )
            job.mark_failed(error_envelope(error).error)
        finally:
            with self._lock:
                if job.terminal:
                    self._active_releases.pop(job.component.release_id, None)
                self._tasks.pop(job.operation_id, None)
                self._prune_terminal_jobs()

    def _execute(self, job: ComponentJob) -> None:
        """Invoke the action-specific port on a worker thread."""
        if job.action is ComponentJobAction.PREPARE:
            self._preparation.prepare_component(
                job.component.release_id,
                job.cancellation,
                job.update,
            )
            return
        self._removal.remove_component(
            job.component.release_id,
            job.cancellation,
            job.update,
        )

    def _allocate_operation_id(self) -> str:
        """Allocate a unique opaque operation identity within the retention set."""
        for _ in range(_OPERATION_ID_ATTEMPTS):
            operation_id = self._operation_id_factory()
            if operation_id not in self._jobs:
                return operation_id
        raise ComponentOperationError(details={"reason": "operation_id_exhausted"})

    def _prune_terminal_jobs(self) -> None:
        """Retain only the newest bounded terminal snapshots."""
        terminal_ids = [operation_id for operation_id, job in self._jobs.items() if job.terminal]
        overflow = len(terminal_ids) - self._policy.max_terminal_jobs
        for operation_id in terminal_ids[: max(0, overflow)]:
            self._jobs.pop(operation_id, None)


def _new_operation_id() -> str:
    """Return one canonical UUID4 operation identifier."""
    return str(uuid4())


def _release_result(component: ManagedComponent) -> ComponentReleaseResult:
    """Translate one pure inventory value into the strict public contract."""
    return ComponentReleaseResult(
        release_id=component.release_id,
        component_id=component.component_id,
        kind=component.kind,
        label=component.label,
        version=component.version,
        build_id=component.build_id,
        platform=component.platform,
        architecture=component.architecture,
        package_bytes=component.package_bytes,
        installed_bytes=component.installed_bytes,
        package_sha256=component.package_sha256,
        source=ComponentSourceResult(
            publisher=component.source.publisher,
            package_url=component.source.package_url,
            provenance_url=component.source.provenance_url,
        ),
        license=ComponentLicenseResult(
            identifier=component.license.identifier,
            name=component.license.name,
            url=component.license.url,
            acceptance_required=component.license.acceptance_required,
        ),
        authentication_required=component.authentication_required,
        capabilities=component.capabilities,
        readiness=component.readiness,
        in_use=component.in_use,
    )
