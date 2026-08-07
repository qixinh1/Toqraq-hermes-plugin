"""Transport-hidden runtime feature connection and factory adapters."""

from __future__ import annotations

import asyncio

from ..core.bridge import BridgeHandshakeExpectation, BridgeListenerEndpoint, BridgeOwnerKey
from ..core.errors import BridgeConnectionError, ToqraqError
from ..core.runtime_features import RuntimeFeatureConnection, RuntimeFeaturePorts
from .bridge_features.aggregate import create_bridge_feature_ports
from .bridge_listener import BridgeListener
from .bridge_listener_policy import BridgeListenerPolicy
from .bridge_rpc_connection import BridgeRpcConnection
from .bridge_rpc_observability import observe_bridge_failure


class BridgeRuntimeFeatureConnectionFactory:
    """Create one listener-backed Core connection owner per game launch."""

    __slots__ = ("_policy",)

    def __init__(self, policy: BridgeListenerPolicy | None = None) -> None:
        """Retain one immutable listener policy for explicit composition."""
        selected = policy or BridgeListenerPolicy()
        if not isinstance(selected, BridgeListenerPolicy):
            raise TypeError("Bridge listener policy is invalid")
        self._policy = selected

    async def open(
        self,
        expectation: BridgeHandshakeExpectation,
    ) -> RuntimeFeatureConnection:
        """Bind one listener and hide every transport value behind its owner."""
        listener = await BridgeListener.open(expectation, self._policy)
        return _BridgeRuntimeFeatureConnection(listener, expectation.owner)


class _BridgeRuntimeFeatureConnection:
    """Own listener, one authentication claim, feature ports, and close."""

    __slots__ = ("_features", "_listener", "_owner", "_ready_task", "_rpc")

    def __init__(self, listener: BridgeListener, owner: BridgeOwnerKey) -> None:
        """Accept sole ownership of one already-bound listener."""
        if not isinstance(listener, BridgeListener):
            raise TypeError("Bridge listener is invalid")
        if not isinstance(owner, BridgeOwnerKey):
            raise TypeError("Bridge owner is invalid")
        self._listener = listener
        self._owner = owner
        self._features: RuntimeFeaturePorts | None = None
        self._ready_task: asyncio.Task[RuntimeFeaturePorts] | None = None
        self._rpc: BridgeRpcConnection | None = None

    @property
    def endpoint(self) -> BridgeListenerEndpoint:
        """Return the launch-safe endpoint without authentication internals."""
        return self._listener.endpoint

    @property
    def owner(self) -> BridgeOwnerKey:
        """Return the exact run identity bound before listener acquisition."""
        return self._owner

    async def wait_ready(self) -> RuntimeFeaturePorts:
        """Claim authentication once and share its immutable focused aggregate."""
        if self._listener.closed:
            raise BridgeConnectionError(details={"reason": "connection_closed"})
        if self._features is not None:
            return self._features
        task = self._ready_task
        if task is None:
            task = asyncio.create_task(
                self._authenticate(),
                name="toqraq-bridge-feature-readiness",
            )
            task.add_done_callback(_observe_ready_task)
            self._ready_task = task
        return await asyncio.shield(task)

    async def wait_unavailable(self) -> ToqraqError:
        """Wait until the authenticated feature connection becomes unusable."""
        await self.wait_ready()
        rpc = self._rpc
        if rpc is None:
            raise RuntimeError("authenticated Bridge connection was not retained")
        return await rpc.wait_failure()

    async def close(self) -> None:
        """Close listener, controlled connection, handler, and readiness idempotently."""
        await self._listener.close()

    async def _authenticate(self) -> RuntimeFeaturePorts:
        """Convert the sole private authentication publication into focused ports."""
        authenticated = await self._listener.claim_authenticated()
        features = create_bridge_feature_ports(authenticated)
        self._rpc = authenticated.connection
        self._features = features
        return features


def _observe_ready_task(task: asyncio.Task[RuntimeFeaturePorts]) -> None:
    """Observe orphaned readiness failure without formatting its exception data."""
    if task.cancelled():
        return
    failure = task.exception()
    if failure is not None:
        observe_bridge_failure(failure)
