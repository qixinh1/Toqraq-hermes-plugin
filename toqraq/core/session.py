"""Run identity, process state, and independent feature readiness."""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager
from threading import RLock

from .bridge import BridgeOwnerKey
from .engine_contribution import ProjectDescription
from .errors import SessionStateError
from .preview import (
    NativeWindowSurface,
    PreviewSurface,
    PreviewSurfaceSnapshot,
    WebSurface,
)
from .run_resources import GameRunResources
from .runtime_features import RuntimeFeaturePorts
from .session_readiness import (
    CONNECTING_READINESS,
    FeatureReadiness,
    FeatureReadinessSnapshot,
    ReadinessFailure,
    ReadinessFeature,
    failed_readiness,
    ready_readiness,
    unavailable_readiness,
)
from .session_snapshot import EngineSessionSnapshot, SessionProcessState

MAX_SESSION_EXIT_CODE = (1 << 53) - 1


class EngineSession:
    """Strong owner and mutable state for one promoted live game run."""

    __slots__ = (
        "_bridge_capability_ids",
        "_bridge_id",
        "_bridge_protocol",
        "_capability_ids",
        "_control",
        "_exit_code",
        "_feature_ports",
        "_lock",
        "_owner",
        "_perception",
        "_preview",
        "_preview_surface",
        "_process_state",
        "_project",
        "_registry_committed",
        "_resources",
        "_root_pid",
        "_runtime_identity",
        "_started_at",
    )

    def __init__(
        self,
        *,
        owner: BridgeOwnerKey,
        project: ProjectDescription,
        resources: GameRunResources,
        started_at: float,
    ) -> None:
        """Take one complete live run and cache its immutable launch facts."""
        if not isinstance(owner, BridgeOwnerKey):
            raise ValueError("session owner is invalid")
        if not isinstance(project, ProjectDescription):
            raise ValueError("session project is invalid")
        if not isinstance(resources, GameRunResources):
            raise ValueError("session resources are invalid")
        if not resources.complete or resources.sealed:
            raise ValueError("session requires complete mutable run resources")
        if not isinstance(started_at, float) or not math.isfinite(started_at) or started_at < 0:
            raise ValueError("session start time is invalid")

        runtime = resources.runtime
        connection = resources.connection
        process_tree = resources.process_tree
        if runtime is None or connection is None or process_tree is None:
            raise ValueError("session resources are incomplete")
        if connection.owner != owner:
            raise ValueError("session and bridge connection owners differ")
        if process_tree.poll() is not None:
            raise ValueError("session process is not alive")
        release = runtime.release
        if project.engine_id != release.identity.engine_id:
            raise ValueError("session project and runtime engines differ")
        root_pid = process_tree.root_pid
        if isinstance(root_pid, bool) or not isinstance(root_pid, int) or root_pid < 1:
            raise ValueError("session root process ID is invalid")

        self._owner = owner
        self._lock = RLock()
        self._project = project
        self._resources = resources
        self._started_at = started_at
        self._runtime_identity = release.identity
        self._bridge_id = release.bridge_id
        self._bridge_protocol = release.bridge_protocol
        self._capability_ids = release.capability_ids
        self._bridge_capability_ids = release.bridge_capability_ids
        self._root_pid = root_pid
        self._process_state = SessionProcessState.RUNNING
        self._exit_code: int | None = None
        self._registry_committed = False
        self._preview = CONNECTING_READINESS
        self._preview_surface: PreviewSurface | None = None
        self._perception = CONNECTING_READINESS
        self._control = CONNECTING_READINESS
        self._feature_ports: RuntimeFeaturePorts | None = None

    @property
    def owner(self) -> BridgeOwnerKey:
        """Return the exact Hermes-session and run-revision identity."""
        return self._owner

    @property
    def project(self) -> ProjectDescription:
        """Return immutable facts for the launched engine project."""
        return self._project

    @property
    def resources(self) -> GameRunResources:
        """Return the sole retryable owner of live run resources."""
        return self._resources

    @property
    def process_state(self) -> SessionProcessState:
        """Return the current process or simulation state."""
        with self._lock:
            return self._process_state

    @property
    def feature_ports(self) -> RuntimeFeaturePorts | None:
        """Return authenticated focused ports without their connection owner."""
        with self._lock:
            if self._process_state not in {
                SessionProcessState.RUNNING,
                SessionProcessState.PAUSED,
            }:
                return None
            if not any(
                readiness.state is FeatureReadiness.READY
                for readiness in (self._perception, self._control)
            ):
                return None
            return self._feature_ports

    @property
    def preview_surface(self) -> PreviewSurface | None:
        """Return the immutable engine-located surface when published."""
        with self._lock:
            return self._preview_surface

    @property
    def perception_readiness(self) -> FeatureReadinessSnapshot:
        """Return current observation readiness for focused service access."""
        with self._lock:
            return self._perception

    @property
    def control_readiness(self) -> FeatureReadinessSnapshot:
        """Return current input and simulation readiness for focused service access."""
        with self._lock:
            return self._control

    def mark_paused(self, paused: bool) -> None:
        """Apply only a running-to-paused or paused-to-running transition."""
        if not isinstance(paused, bool):
            raise ValueError("pause state is invalid")
        expected = SessionProcessState.RUNNING if paused else SessionProcessState.PAUSED
        target = SessionProcessState.PAUSED if paused else SessionProcessState.RUNNING
        with self._lock:
            if self._process_state is not expected:
                self._invalid_process_transition(target)
            self._process_state = target

    def _mark_stopping_locked(self) -> None:
        """Enter stopping while the session state lock is held."""
        if self._process_state is SessionProcessState.STOPPING:
            return
        if self._process_state not in {
            SessionProcessState.RUNNING,
            SessionProcessState.PAUSED,
        }:
            self._invalid_process_transition(SessionProcessState.STOPPING)
        self._process_state = SessionProcessState.STOPPING
        self._withdraw_live_features_locked()

    def record_exit(self, exit_code: int) -> None:
        """Cache one exact exit and classify natural versus requested termination."""
        with self._lock:
            self._record_exit_locked(_validate_exit_code(exit_code))

    def _record_exit_locked(self, exit_code: int) -> None:
        """Settle one exit while the session state lock is held."""
        if self._process_state in {SessionProcessState.ENDED, SessionProcessState.CRASHED}:
            if self._exit_code == exit_code:
                return
            raise SessionStateError(details={"reason": "exit_code_changed"})
        if self._process_state not in {
            SessionProcessState.RUNNING,
            SessionProcessState.PAUSED,
            SessionProcessState.STOPPING,
        }:
            self._invalid_process_transition(SessionProcessState.ENDED)
        stopping = self._process_state is SessionProcessState.STOPPING
        self._exit_code = exit_code
        self._process_state = (
            SessionProcessState.ENDED if stopping or exit_code == 0 else SessionProcessState.CRASHED
        )
        self._withdraw_live_features_locked()

    async def close(self) -> None:
        """Run the common retryable cleanup and retain explicit-stop failure state."""
        with self._lock:
            process_tree = self._resources.process_tree
            if not self._resources.empty and self._process_state in {
                SessionProcessState.RUNNING,
                SessionProcessState.PAUSED,
            }:
                observed_exit = process_tree.poll() if process_tree is not None else None
                if observed_exit is None:
                    self._mark_stopping_locked()
                else:
                    self._record_exit_locked(_validate_exit_code(observed_exit))
        try:
            await self._resources.close()
        finally:
            with self._lock:
                if self._exit_code is None:
                    exit_code = self._resources.process_exit_code
                    if exit_code is None and process_tree is not None:
                        exit_code = process_tree.poll()
                    if exit_code is not None:
                        self._exit_code = _validate_exit_code(exit_code)
                if (
                    self._resources.empty
                    and self._process_state is SessionProcessState.STOPPING
                    and self._exit_code is not None
                ):
                    self._record_exit_locked(self._exit_code)
        with self._lock:
            if self._resources.empty and self._process_state is SessionProcessState.STOPPING:
                raise SessionStateError(details={"reason": "released_process_has_no_exit_code"})

    def publish_preview(self, surface: PreviewSurface) -> None:
        """Publish one immutable engine-located surface for this live run."""
        if not isinstance(surface, NativeWindowSurface | WebSurface):
            raise ValueError("preview surface is invalid")
        with self._lock:
            self._require_live_feature_publication()
            if self._preview_surface is not None:
                raise SessionStateError(details={"reason": "preview_already_published"})
            readiness = ready_readiness(self._preview)
            self._preview_surface = surface
            self._preview = readiness

    def fail_preview(self, failure: ReadinessFailure) -> None:
        """Publish a safe terminal preview failure."""
        _require_failure_feature(failure, ReadinessFeature.PREVIEW)
        with self._lock:
            self._require_live_feature_publication()
            self._preview = failed_readiness(self._preview, failure)
            self._preview_surface = None

    def publish_features(self, ports: RuntimeFeaturePorts) -> None:
        """Publish focused ports while their connection remains resource-owned."""
        if not isinstance(ports, RuntimeFeaturePorts):
            raise ValueError("runtime feature ports are invalid")
        with self._lock:
            self._require_live_feature_publication()
            if self._feature_ports is not None:
                raise SessionStateError(details={"reason": "features_already_published"})
            perception = ready_readiness(self._perception)
            control = ready_readiness(self._control)
            self._feature_ports = ports
            self._perception = perception
            self._control = control

    def fail_features(self, failure: ReadinessFailure) -> None:
        """Publish one shared bridge failure for both focused feature groups."""
        _require_failure_feature(failure, ReadinessFeature.PERCEPTION)
        _require_failure_feature(failure, ReadinessFeature.CONTROL)
        with self._lock:
            self._require_live_feature_publication()
            perception = (
                self._perception
                if self._perception.state is FeatureReadiness.FAILED
                else failed_readiness(self._perception, failure)
            )
            control = (
                self._control
                if self._control.state is FeatureReadiness.FAILED
                else failed_readiness(self._control, failure)
            )
            self._feature_ports = None
            self._perception = perception
            self._control = control

    def snapshot(self) -> EngineSessionSnapshot:
        """Return cached identity and terminal facts without touching resources."""
        with self._lock:
            return EngineSessionSnapshot(
                owner=self._owner,
                project=self._project,
                runtime_identity=self._runtime_identity,
                bridge_id=self._bridge_id,
                bridge_protocol=self._bridge_protocol,
                capability_ids=self._capability_ids,
                bridge_capability_ids=self._bridge_capability_ids,
                root_pid=self._root_pid,
                started_at=self._started_at,
                process_state=self._process_state,
                exit_code=self._exit_code,
                preview=self._preview,
                preview_surface=(
                    PreviewSurfaceSnapshot.from_surface(self._preview_surface)
                    if self._preview_surface is not None
                    else None
                ),
                perception=self._perception,
                control=self._control,
            )

    @contextmanager
    def _registry_commit_claim(self) -> Iterator[bool]:
        """Hold state stable while a registry atomically commits this live run."""
        with self._lock:
            process_tree = self._resources.process_tree
            eligible = (
                not self._registry_committed
                and self._process_state is SessionProcessState.RUNNING
                and self._resources.complete
                and not self._resources.sealed
                and process_tree is not None
                and process_tree.poll() is None
            )
            if eligible:
                self._registry_committed = True
            yield eligible

    def _released_registry_owner(self) -> bool:
        """Return whether cleanup completed for one previously committed owner."""
        with self._lock:
            return (
                self._registry_committed
                and self._resources.empty
                and self._process_state in {SessionProcessState.ENDED, SessionProcessState.CRASHED}
            )

    def _require_live_feature_publication(self) -> None:
        """Reject readiness writes after stop ownership begins."""
        if self._process_state not in {
            SessionProcessState.RUNNING,
            SessionProcessState.PAUSED,
        }:
            raise SessionStateError(details={"reason": "session_not_live"})

    def _withdraw_live_features_locked(self) -> None:
        """Revoke borrowed live values while retaining safe failure evidence."""
        self._feature_ports = None
        self._preview_surface = None
        self._preview = unavailable_readiness(self._preview)
        self._perception = unavailable_readiness(self._perception)
        self._control = unavailable_readiness(self._control)

    def _invalid_process_transition(self, target: SessionProcessState) -> None:
        """Raise one stable conflict for a forbidden process transition."""
        raise SessionStateError(
            parameters={
                "current_state": self._process_state.value,
                "requested_state": target.value,
            },
            details={"reason": "transition_not_allowed"},
        )


def _require_failure_feature(
    failure: ReadinessFailure,
    feature: ReadinessFeature,
) -> None:
    """Reject safe failures created for another readiness group."""
    if not isinstance(failure, ReadinessFailure):
        raise ValueError("readiness failure is invalid")
    if feature not in failure.features:
        raise ValueError("readiness failure feature does not match")


def _validate_exit_code(value: int) -> int:
    """Require one signed cross-language-safe process exit code."""
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not -MAX_SESSION_EXIT_CODE <= value <= MAX_SESSION_EXIT_CODE
    ):
        raise ValueError("session exit code is invalid")
    return value
