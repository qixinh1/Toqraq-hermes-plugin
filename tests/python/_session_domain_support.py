"""Typed in-memory owners for pure session-domain tests."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import cast

from toqraq.core.bridge import BridgeListenerEndpoint, BridgeOwnerKey
from toqraq.core.capability_ids import (
    MANDATORY_BRIDGE_CAPABILITY_IDS,
    MANDATORY_ENGINE_CAPABILITY_IDS,
)
from toqraq.core.engine_contribution import ProjectDescription
from toqraq.core.errors import BridgeConnectionError, ToqraqError
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
from toqraq.core.session import EngineSession

_COMPONENT_RELEASE_ID = "1" * 64
_POLICY = RunCleanupPolicy(graceful_timeout_seconds=0, forced_timeout_seconds=0)


class FakeRuntimeLease:
    """Record retryable release of one exact prepared runtime."""

    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.close_count = 0

    async def close(self) -> None:
        """Fail the configured number of attempts, then release."""
        self.close_count += 1
        if self.close_count <= self.failures:
            raise OSError("runtime lease close failed")


class FakeFeaturePorts:
    """Structurally complete aggregate of seven focused test ports."""

    hierarchy = object()
    objects = object()
    diagnostics = object()
    metrics = object()
    simulation = object()
    input = object()
    frame = object()


class FakeFeatureConnection:
    """Own one focused-port aggregate and bounded close attempts."""

    endpoint = BridgeListenerEndpoint(port=49_152)

    def __init__(
        self,
        owner: BridgeOwnerKey,
        ports: FakeFeaturePorts,
        failures: int = 0,
    ) -> None:
        self.owner = owner
        self.ports = ports
        self.failures = failures
        self.close_count = 0

    async def wait_ready(self) -> RuntimeFeaturePorts:
        """Return the sole authenticated feature aggregate."""
        return cast(RuntimeFeaturePorts, self.ports)

    async def wait_unavailable(self) -> ToqraqError:
        """Return one safe terminal bridge-unavailable fact."""
        return BridgeConnectionError(details={"reason": "test_connection_closed"})

    async def close(self) -> None:
        """Fail the configured number of attempts, then release ownership."""
        self.close_count += 1
        if self.close_count <= self.failures:
            raise OSError("feature connection close failed")


class FakeProcessTree:
    """Expose one live root and deterministic stop behavior."""

    root_pid = 4_242

    def __init__(
        self,
        *,
        close_failures: int = 0,
        stop_exit_code: int = 7,
        close_started: Event | None = None,
        close_release: Event | None = None,
        output_snapshot: ProcessOutputSnapshot | None = None,
    ) -> None:
        self.close_failures = close_failures
        self.stop_exit_code = stop_exit_code
        self.close_started = close_started
        self.close_release = close_release
        self.close_count = 0
        self.exit_code: int | None = None
        self.output_calls = 0
        self.output_snapshot = output_snapshot or ProcessOutputSnapshot(
            chunks=(),
            next_sequence=1,
            truncated=False,
            failed_streams=frozenset(),
        )

    def poll(self) -> int | None:
        """Return the configured terminal process result."""
        return self.exit_code

    def wait(self, timeout: float) -> int:
        """Return a settled exit or time out while live."""
        del timeout
        if self.exit_code is None:
            raise TimeoutError
        return self.exit_code

    def output(self) -> ProcessOutputSnapshot:
        """Return the configured bounded output tail."""
        self.output_calls += 1
        return self.output_snapshot

    def close(self, *, graceful_timeout: float, forced_timeout: float) -> None:
        """Fail retryably or settle the exact stop result."""
        assert (graceful_timeout, forced_timeout) == (0, 0)
        self.close_count += 1
        if self.close_started is not None:
            self.close_started.set()
        if self.close_release is not None and not self.close_release.wait(2):
            raise TimeoutError("process close release timed out")
        if self.close_count <= self.close_failures:
            raise OSError("process close failed")
        if self.exit_code is None:
            self.exit_code = self.stop_exit_code

    def exit(self, code: int) -> None:
        """Simulate an engine-owned natural exit."""
        self.exit_code = code


def make_session(
    root: Path,
    owner: BridgeOwnerKey,
    *,
    process_close_failures: int = 0,
    connection_close_failures: int = 0,
    stop_exit_code: int = 7,
    process_close_started: Event | None = None,
    process_close_release: Event | None = None,
    connection_owner: BridgeOwnerKey | None = None,
    bridge_capability_ids: frozenset[str] = MANDATORY_BRIDGE_CAPABILITY_IDS,
) -> tuple[
    EngineSession,
    FakeProcessTree,
    FakeFeatureConnection,
    FakeFeaturePorts,
    FakeRuntimeLease,
]:
    """Build one complete promoted run with exact certified facts."""
    lease = FakeRuntimeLease()
    release = RuntimeRelease(
        identity=RuntimeIdentity(
            engine_id="godot",
            version="4.7.1-stable",
            build_id="toqraq.windows.x86_64.release",
            distribution_id="toqraq",
            platform="windows",
            architecture="x86_64",
        ),
        component_release_ids=(_COMPONENT_RELEASE_ID,),
        entry_point_bindings=(
            RuntimeEntryPointBinding(
                name="editor",
                component_release_id=_COMPONENT_RELEASE_ID,
                component_entry_point_name="editor",
            ),
        ),
        bridge_id="toqraq.godot.bridge",
        bridge_protocol="1.0",
        capability_ids=MANDATORY_ENGINE_CAPABILITY_IDS,
        bridge_capability_ids=bridge_capability_ids,
    )
    runtime = PreparedRuntime(
        release=release,
        entry_points=(RuntimeEntryPoint(name="editor", path=root / "godot.exe"),),
        owned_resources=(lease,),
    )
    ports = FakeFeaturePorts()
    connection = FakeFeatureConnection(
        connection_owner or owner,
        ports,
        failures=connection_close_failures,
    )
    process = FakeProcessTree(
        close_failures=process_close_failures,
        stop_exit_code=stop_exit_code,
        close_started=process_close_started,
        close_release=process_close_release,
    )
    resources = GameRunResources(_POLICY)
    resources.retain_runtime(runtime)
    resources.retain_connection(connection)
    resources.retain_process_tree(process)
    project = ProjectDescription(
        engine_id="godot",
        project_root=root,
        marker_path=root / "project.godot",
        confidence=100,
        declared_version="4.7.1-stable",
    )
    return (
        EngineSession(
            owner=owner,
            project=project,
            resources=resources,
            started_at=1_722_000_000.25,
        ),
        process,
        connection,
        ports,
        lease,
    )
