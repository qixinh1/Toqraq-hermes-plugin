"""Host-provided WebSocket runtime boundary for the engine bridge."""

from __future__ import annotations

import logging
import socket
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from http import HTTPStatus
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from typing import Protocol, cast

from ..core.bridge import BRIDGE_ENDPOINT_PATH, BRIDGE_LOOPBACK_HOST, BridgeListenerEndpoint
from ..core.errors import BridgeConnectionError

_transport_logger = logging.getLogger(f"{__name__}.transport")
HERMES_WEBSOCKETS_VERSION = "15.0.1"


class BridgeSocket(Protocol):
    """Subset of one host-provided WebSocket connection owned by the listener."""

    async def recv(self, decode: bool | None = None) -> str | bytes:
        """Receive one complete application message."""

    async def send(self, message: str) -> None:
        """Send one complete text message."""

    async def close(self, code: int = 1000, reason: str = "") -> None:
        """Perform a closing handshake."""

    async def wait_closed(self) -> None:
        """Wait until the transport is closed."""

    def respond(self, status: HTTPStatus, text: str) -> object:
        """Create an HTTP response before a WebSocket upgrade."""


class UpgradeRequest(Protocol):
    """Only upgrade-request value inspected by the listener."""

    path: str


class BridgeServer(Protocol):
    """Subset of the host-provided WebSocket server owned by the listener."""

    @property
    def sockets(self) -> Iterable[socket.socket]:
        """Return bound listening sockets."""

    def close(self, close_connections: bool = True) -> None:
        """Stop accepting connections and optionally close existing ones."""

    async def wait_closed(self) -> None:
        """Wait for the listener and every handler to finish."""

    async def start_serving(self) -> None:
        """Begin accepting after listener ownership is fully constructed."""


ConnectionHandler = Callable[[BridgeSocket], Awaitable[None]]


class ServeFactory(Protocol):
    """Typed external boundary for ``websockets.asyncio.server.serve``."""

    def __call__(
        self,
        handler: ConnectionHandler,
        host: str,
        port: int,
        **kwargs: object,
    ) -> Awaitable[BridgeServer]:
        """Create one not-yet-serving listener."""


@dataclass(frozen=True, slots=True)
class WebSocketRuntime:
    """Host transport types loaded only when a listener is needed."""

    serve: ServeFactory
    connection_closed: type[Exception]


class FrameSafeLogger(logging.LoggerAdapter[logging.Logger]):
    """Prevent the transport's DEBUG frame formatter from seeing credentials."""

    def isEnabledFor(self, level: int) -> bool:  # noqa: N802 - logging API name
        """Disable DEBUG before ``websockets`` stores its frame-log flag."""
        return level > logging.DEBUG and super().isEnabledFor(level)

    def debug(self, msg: object, *args: object, **kwargs: object) -> None:
        """Keep frame content out of logs even if a caller bypasses the flag."""


def load_websocket_runtime() -> WebSocketRuntime:
    """Load the exact Hermes dependency without making plugin import depend on it."""
    try:
        websockets_version = package_version("websockets")
    except PackageNotFoundError as exc:
        raise _dependency_unavailable(exc) from None
    try:
        from websockets.asyncio.server import serve
        from websockets.exceptions import ConnectionClosed
    except ImportError as exc:
        raise _dependency_unavailable(exc) from None
    if websockets_version != HERMES_WEBSOCKETS_VERSION:
        raise BridgeConnectionError(
            details={
                "reason": "websockets_version_mismatch",
                "expected_version": HERMES_WEBSOCKETS_VERSION,
            }
        ) from None
    return WebSocketRuntime(
        serve=cast(ServeFactory, serve),
        connection_closed=ConnectionClosed,
    )


def _dependency_unavailable(cause: BaseException) -> BridgeConnectionError:
    """Translate absent distribution metadata or imports without source text."""
    return BridgeConnectionError(
        details={"reason": "websockets_dependency_unavailable"},
        cause=cause,
    )


def frame_safe_logger() -> FrameSafeLogger:
    """Create a per-server adapter with DEBUG payload formatting disabled."""
    return FrameSafeLogger(_transport_logger, {})


def endpoint_from(server: BridgeServer) -> BridgeListenerEndpoint:
    """Require the single bound socket promised by the explicit IPv4 host."""
    sockets = tuple(server.sockets)
    if len(sockets) != 1 or sockets[0].family != socket.AF_INET:
        raise RuntimeError("bridge listener did not bind one IPv4 socket")
    address = sockets[0].getsockname()
    if (
        not isinstance(address, tuple)
        or len(address) < 2
        or address[0] != BRIDGE_LOOPBACK_HOST
        or isinstance(address[1], bool)
        or not isinstance(address[1], int)
    ):
        raise RuntimeError("bridge listener returned an invalid address")
    return BridgeListenerEndpoint(port=address[1])


def require_bridge_path(connection: BridgeSocket, request: UpgradeRequest) -> object | None:
    """Reject every HTTP target outside the one non-secret bridge endpoint."""
    if request.path == BRIDGE_ENDPOINT_PATH:
        return None
    return connection.respond(HTTPStatus.NOT_FOUND, "Not Found\n")
