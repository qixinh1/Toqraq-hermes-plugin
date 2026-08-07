"""One owned aggregate of the seven common Bridge feature adapters."""

from __future__ import annotations

from ...core.diagnostics import DiagnosticsReader
from ...core.frame_capture import FrameCapture
from ...core.hierarchy import HierarchyReader
from ...core.input_control import InputController
from ...core.metrics import MetricsReader
from ...core.object_inspection import ObjectReader
from ...core.runtime_features import RuntimeFeaturePorts
from ...core.simulation_control import SimulationController
from ..bridge_authentication import AuthenticatedBridge
from ..bridge_rpc_connection import BridgeRpcConnection
from .diagnostics import BridgeDiagnosticsReader
from .frame import BridgeFrameCapture
from .hierarchy import BridgeHierarchyReader
from .input import BridgeInputController
from .metrics import BridgeMetricsReader
from .objects import BridgeObjectReader
from .simulation import BridgeSimulationController


class _BridgeFeaturePorts:
    """Hide the controlled connection behind seven focused Core properties."""

    __slots__ = (
        "_diagnostics",
        "_frame",
        "_hierarchy",
        "_input",
        "_metrics",
        "_objects",
        "_simulation",
    )

    def __init__(
        self,
        connection: BridgeRpcConnection,
    ) -> None:
        """Construct every adapter exactly once for one authenticated connection."""
        self._hierarchy = BridgeHierarchyReader(connection)
        self._objects = BridgeObjectReader(connection)
        self._diagnostics = BridgeDiagnosticsReader(connection)
        self._metrics = BridgeMetricsReader(connection)
        self._simulation = BridgeSimulationController(connection)
        self._input = BridgeInputController(connection)
        self._frame = BridgeFrameCapture(connection)

    @property
    def hierarchy(self) -> HierarchyReader:
        """Return the shared hierarchy adapter."""
        return self._hierarchy

    @property
    def objects(self) -> ObjectReader:
        """Return the shared object adapter."""
        return self._objects

    @property
    def diagnostics(self) -> DiagnosticsReader:
        """Return the shared diagnostics adapter."""
        return self._diagnostics

    @property
    def metrics(self) -> MetricsReader:
        """Return the shared metrics adapter."""
        return self._metrics

    @property
    def simulation(self) -> SimulationController:
        """Return the shared simulation adapter."""
        return self._simulation

    @property
    def input(self) -> InputController:
        """Return the shared input adapter."""
        return self._input

    @property
    def frame(self) -> FrameCapture:
        """Return the shared frame-capture adapter."""
        return self._frame


def create_bridge_feature_ports(
    authenticated: AuthenticatedBridge,
) -> RuntimeFeaturePorts:
    """Expose borrowed capabilities while the connection remains owner."""
    if not isinstance(authenticated, AuthenticatedBridge):
        raise TypeError("authenticated Bridge value is invalid")
    return _BridgeFeaturePorts(authenticated.connection)
