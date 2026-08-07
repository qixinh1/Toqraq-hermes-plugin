"""Aggregate ownership boundary for one authenticated runtime feature set."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .bridge import BridgeHandshakeExpectation, BridgeListenerEndpoint, BridgeOwnerKey
from .diagnostics import DiagnosticsReader
from .errors import ToqraqError
from .frame_capture import FrameCapture
from .hierarchy import HierarchyReader
from .input_control import InputController
from .metrics import MetricsReader
from .object_inspection import ObjectReader
from .resource import AsyncResource
from .simulation_control import SimulationController


@runtime_checkable
class RuntimeFeaturePorts(Protocol):
    """Borrowed aggregate of seven focused live-game capabilities."""

    @property
    def hierarchy(self) -> HierarchyReader:
        """Return the bounded runtime hierarchy reader."""
        ...

    @property
    def objects(self) -> ObjectReader:
        """Return the selected runtime-object reader."""
        ...

    @property
    def diagnostics(self) -> DiagnosticsReader:
        """Return the bounded diagnostic stream reader."""
        ...

    @property
    def metrics(self) -> MetricsReader:
        """Return the selected performance-metric reader."""
        ...

    @property
    def simulation(self) -> SimulationController:
        """Return the immediate pause and frame-step controller."""
        ...

    @property
    def input(self) -> InputController:
        """Return the bounded player-input controller."""
        ...

    @property
    def frame(self) -> FrameCapture:
        """Return the verified single-frame capture port."""
        ...


@runtime_checkable
class RuntimeFeatureConnection(AsyncResource, Protocol):
    """Own listener, authentication, focused ports, and their cleanup."""

    @property
    def endpoint(self) -> BridgeListenerEndpoint:
        """Return the loopback endpoint required by the exact launch plan."""
        ...

    @property
    def owner(self) -> BridgeOwnerKey:
        """Return the exact run identity authenticated by this connection."""
        ...

    async def wait_ready(self) -> RuntimeFeaturePorts:
        """Wait for the sole authenticated feature set without exposing transport."""
        ...

    async def wait_unavailable(self) -> ToqraqError:
        """Wait for terminal feature loss and return its safe application error."""
        ...


@runtime_checkable
class RuntimeFeatureConnectionFactory(Protocol):
    """Open one transport owner for an immutable launch expectation."""

    async def open(
        self,
        expectation: BridgeHandshakeExpectation,
    ) -> RuntimeFeatureConnection:
        """Bind the listener before the game process is launched."""
        ...
