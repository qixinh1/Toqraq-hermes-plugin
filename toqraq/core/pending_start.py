"""Single-transfer owner for resources acquired during one game start."""

from __future__ import annotations

from threading import Event

from .bridge import BridgeOwnerKey
from .bridge_launch import BridgeLaunchBootstrap
from .engine_contribution import ProjectDescription
from .process_tree import ProcessTree
from .run_resources import GameRunResources, RunCleanupPolicy
from .runtime import PreparedRuntime
from .runtime_features import RuntimeFeatureConnection
from .session import EngineSession


class PendingStart:
    """Own cancellation, private bootstrap, and resources until promotion."""

    __slots__ = ("_bootstrap", "_cancelled", "_owner", "_resources", "_transferred")

    def __init__(
        self,
        bootstrap: BridgeLaunchBootstrap,
        policy: RunCleanupPolicy | None = None,
    ) -> None:
        """Create ownership before the first resource is acquired."""
        if not isinstance(bootstrap, BridgeLaunchBootstrap):
            raise ValueError("pending start bootstrap is invalid")
        self._bootstrap: BridgeLaunchBootstrap | None = bootstrap
        self._owner = BridgeOwnerKey(
            session_id=bootstrap.session_id,
            run_revision=bootstrap.run_revision,
        )
        self._cancelled = Event()
        self._resources: GameRunResources | None = GameRunResources(
            policy,
            cancellation=self._cancelled,
        )
        self._transferred = False

    @property
    def owner(self) -> BridgeOwnerKey:
        """Return the exact Hermes session and internal run revision."""
        return self._owner

    @property
    def cancellation(self) -> Event:
        """Return the one token shared by every cancellable acquisition."""
        return self._cancelled

    @property
    def resources(self) -> GameRunResources:
        """Return the current owner before promotion."""
        if self._resources is None:
            raise ValueError("pending start resources were transferred")
        return self._resources

    def cancel(self) -> None:
        """Request cooperative cancellation idempotently."""
        self._cancelled.set()

    def take_bootstrap(self) -> BridgeLaunchBootstrap:
        """Consume the private launch value exactly once."""
        self._require_active()
        bootstrap = self._require_bootstrap()
        self._bootstrap = None
        return bootstrap

    def retain_runtime(self, runtime: PreparedRuntime) -> None:
        """Retain a completed acquisition even after cancellation was requested."""
        self._require_untransferred()
        self.resources.retain_runtime(runtime)

    def retain_connection(self, connection: RuntimeFeatureConnection) -> None:
        """Retain one connection before validating its exact run identity."""
        self._require_untransferred()
        if not isinstance(connection, RuntimeFeatureConnection):
            raise ValueError("runtime feature connection is invalid")
        self.resources.retain_connection(connection)
        if connection.owner != self._owner:
            raise ValueError("runtime feature connection owner differs")

    def retain_process_tree(self, process_tree: ProcessTree) -> None:
        """Retain a completed process acquisition for promotion or cleanup."""
        self._require_untransferred()
        self.resources.retain_process_tree(process_tree)

    def promote(
        self,
        *,
        project: ProjectDescription,
        started_at: float,
    ) -> EngineSession:
        """Construct the active owner before transferring a complete live run."""
        self._require_active()
        resources = self.resources
        process_tree = resources.process_tree
        if self._transferred or self._bootstrap is not None or not resources.complete:
            raise ValueError("pending start is not promotable")
        if process_tree is None or process_tree.poll() is not None:
            raise ValueError("pending start process tree is not running")
        if resources.sealed:
            raise ValueError("pending start cleanup is active")
        session = EngineSession(
            owner=self._owner,
            project=project,
            resources=resources,
            started_at=started_at,
        )
        self._resources = None
        self._transferred = True
        return session

    async def close(self) -> None:
        """Cancel and release every resource not transferred to a session."""
        if self._transferred:
            return
        self.cancel()
        self._bootstrap = None
        resources = self._resources
        if resources is not None:
            await resources.close()

    def _require_bootstrap(self) -> BridgeLaunchBootstrap:
        """Return an unconsumed private value without exposing it in errors."""
        if self._bootstrap is None:
            raise ValueError("pending start bootstrap was consumed")
        return self._bootstrap

    def _require_active(self) -> None:
        """Reject acquisition or transfer after cancellation."""
        if self._cancelled.is_set() or self._transferred:
            raise ValueError("pending start is not active")

    def _require_untransferred(self) -> None:
        """Permit late acquisition transfer only while this owner still exists."""
        if self._transferred:
            raise ValueError("pending start resources were transferred")
