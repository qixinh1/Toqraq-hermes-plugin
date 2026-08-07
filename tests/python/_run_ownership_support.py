"""Test doubles and builders for run-resource ownership tests."""

from __future__ import annotations

import threading
from pathlib import Path

from toqraq.core.bridge import BridgeListenerEndpoint, BridgeOwnerKey
from toqraq.core.bridge_launch import BridgeLaunchBootstrap
from toqraq.core.engine_contribution import ProjectDescription
from toqraq.core.pending_start import PendingStart
from toqraq.core.process_tree import ProcessOutputSnapshot
from toqraq.core.run_resources import GameRunResources, RunCleanupPolicy
from toqraq.core.runtime import (
    PreparedRuntime,
    RuntimeEntryPoint,
    RuntimeEntryPointBinding,
    RuntimeIdentity,
    RuntimeRelease,
)
from toqraq.core.runtime_features import RuntimeFeaturePorts

CREDENTIAL = "a" * 64
COMPONENT_RELEASE_ID = "1" * 64
POLICY = RunCleanupPolicy(graceful_timeout_seconds=0, forced_timeout_seconds=0)


class RuntimeResource:
    """Retry-aware runtime lease double."""

    def __init__(self, order: list[str], *, failures: int = 0) -> None:
        self._order = order
        self._failures = failures
        self.close_count = 0

    async def close(self) -> None:
        self.close_count += 1
        self._order.append("runtime")
        if self.close_count <= self._failures:
            raise OSError("runtime close failed")


class PreviewAttachment:
    """Retry-aware native preview mutation double."""

    def __init__(self, order: list[str], *, failures: int = 0) -> None:
        self._order = order
        self._failures = failures
        self.close_count = 0

    async def close(self) -> None:
        self.close_count += 1
        self._order.append("preview")
        if self.close_count <= self._failures:
            raise OSError("preview close failed")


class Connection:
    """Retry-aware bridge connection double."""

    endpoint = BridgeListenerEndpoint(port=49152)

    def __init__(
        self,
        order: list[str],
        *,
        failures: int = 0,
        owner: BridgeOwnerKey | None = None,
    ) -> None:
        self._order = order
        self._failures = failures
        self.owner = owner or BridgeOwnerKey(
            session_id="hermes-session",
            run_revision=7,
        )
        self.close_count = 0

    async def wait_ready(self) -> RuntimeFeaturePorts:
        raise AssertionError("ownership tests do not authenticate")

    async def wait_unavailable(self) -> Exception:
        raise AssertionError("ownership tests do not monitor feature loss")

    async def close(self) -> None:
        self.close_count += 1
        self._order.append("connection")
        if self.close_count <= self._failures:
            raise OSError("connection close failed")


class ProcessTree:
    """Controllable synchronous process-tree double."""

    root_pid = 42

    def __init__(
        self,
        order: list[str],
        *,
        failures: int = 0,
        started: threading.Event | None = None,
        release: threading.Event | None = None,
        observable_after_close: bool = True,
    ) -> None:
        self._order = order
        self._failures = failures
        self._started = started
        self._release = release
        self._observable_after_close = observable_after_close
        self._exit_code: int | None = None
        self.close_count = 0

    def poll(self) -> int | None:
        return self._exit_code

    def wait(self, timeout: float) -> int:
        del timeout
        if self._exit_code is None:
            raise TimeoutError
        return self._exit_code

    def output(self) -> ProcessOutputSnapshot:
        return ProcessOutputSnapshot(
            chunks=(),
            next_sequence=1,
            truncated=False,
            failed_streams=frozenset(),
        )

    def close(self, *, graceful_timeout: float, forced_timeout: float) -> None:
        assert (graceful_timeout, forced_timeout) == (0, 0)
        self.close_count += 1
        self._order.append("process")
        if self._started is not None:
            self._started.set()
        if self._release is not None and not self._release.wait(2):
            raise TimeoutError("test release timed out")
        if self.close_count <= self._failures:
            raise OSError("process close failed")
        if self._observable_after_close:
            self._exit_code = 0

    def exit(self, code: int) -> None:
        self._exit_code = code


def bootstrap() -> BridgeLaunchBootstrap:
    """Build the one private bootstrap used by ownership tests."""
    return BridgeLaunchBootstrap(
        credential=CREDENTIAL,
        session_id="hermes-session",
        run_revision=7,
    )


def runtime(root: Path, resource: RuntimeResource) -> PreparedRuntime:
    """Build a prepared runtime retaining the supplied lease."""
    release = RuntimeRelease(
        identity=RuntimeIdentity(
            engine_id="godot",
            version="4.7.1-stable",
            build_id="toqraq.windows.x86_64.release",
            distribution_id="toqraq",
            platform="windows",
            architecture="x86_64",
        ),
        component_release_ids=(COMPONENT_RELEASE_ID,),
        entry_point_bindings=(
            RuntimeEntryPointBinding(
                name="editor",
                component_release_id=COMPONENT_RELEASE_ID,
                component_entry_point_name="editor",
            ),
        ),
        bridge_id="toqraq.godot.bridge",
        bridge_protocol="1.0",
    )
    return PreparedRuntime(
        release=release,
        entry_points=(RuntimeEntryPoint(name="editor", path=root / "godot.exe"),),
        owned_resources=(resource,),
    )


def project(root: Path) -> ProjectDescription:
    """Build the project selected for promotion."""
    return ProjectDescription(
        engine_id="godot",
        project_root=root,
        marker_path=root / "project.godot",
        confidence=100,
        declared_version="4.7.1-stable",
    )


def promote(pending: PendingStart, root: Path) -> GameRunResources:
    """Promote a complete pending start and return its resource owner."""
    return pending.promote(project=project(root), started_at=1.0).resources


def complete_pending(
    root: Path,
    *,
    process_failures: int = 0,
    connection_failures: int = 0,
    runtime_failures: int = 0,
) -> tuple[PendingStart, ProcessTree, Connection, RuntimeResource, list[str]]:
    """Build a completely acquired pending start."""
    order: list[str] = []
    process = ProcessTree(order, failures=process_failures)
    connection = Connection(order, failures=connection_failures)
    resource = RuntimeResource(order, failures=runtime_failures)
    pending = PendingStart(bootstrap(), POLICY)
    pending.retain_runtime(runtime(root, resource))
    pending.retain_connection(connection)
    pending.retain_process_tree(process)
    pending.take_bootstrap()
    return pending, process, connection, resource, order
