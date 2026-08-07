"""One-shot publication and claim ownership for an authenticated engine bridge."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ..core.bridge import BridgeHandshakeAcceptance
from ..core.errors import BridgeConnectionError
from .bridge_rpc_connection import BridgeRpcConnection


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthenticatedBridge:
    """The accepted owner facts and sole controlled operation handle."""

    acceptance: BridgeHandshakeAcceptance
    connection: BridgeRpcConnection

    def __post_init__(self) -> None:
        """Reject partial or unowned authentication publication."""
        if not isinstance(self.acceptance, BridgeHandshakeAcceptance):
            raise ValueError("authenticated bridge acceptance is invalid")
        if not isinstance(self.connection, BridgeRpcConnection):
            raise ValueError("authenticated bridge connection is invalid")


class BridgeAuthenticationPublication:
    """Own one authentication future and its exactly-once successful claim."""

    def __init__(self) -> None:
        """Create the waiter before the listener can accept a connection."""
        self._future: asyncio.Future[AuthenticatedBridge] = (
            asyncio.get_running_loop().create_future()
        )
        self._claimed = False

    async def claim(self) -> AuthenticatedBridge:
        """Return the sole successful publication to exactly one caller."""
        authenticated = await asyncio.shield(self._future)
        if self._claimed:
            raise RuntimeError("authenticated bridge has already been claimed")
        self._claimed = True
        return authenticated

    def publish(self, authenticated: AuthenticatedBridge) -> bool:
        """Publish one complete controlled connection unless already terminal."""
        if not isinstance(authenticated, AuthenticatedBridge):
            raise TypeError("authenticated bridge publication is invalid")
        if self._future.done():
            return False
        self._future.set_result(authenticated)
        return True

    def fail(self, error: BridgeConnectionError) -> bool:
        """Settle an unpublished waiter with one typed safe bridge failure."""
        if not isinstance(error, BridgeConnectionError):
            raise TypeError("bridge authentication failure is invalid")
        if self._future.done():
            return False
        self._future.set_exception(error)
        self._future.exception()
        return True
