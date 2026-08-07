"""Session-owned loopback WebSocket listener for engine authentication."""

from __future__ import annotations

import asyncio
import logging
import socket

from ..contracts.bridge import BridgeHandshakeResponse, bridge_error_response
from ..contracts.bridge_codec import decode_handshake_request
from ..core.bridge import (
    BRIDGE_LOOPBACK_HOST,
    MAX_BRIDGE_TEXT_MESSAGE_BYTES,
    BridgeHandshakeExpectation,
    BridgeLimits,
    BridgeListenerEndpoint,
    BridgeOwnerKey,
    validate_bridge_handshake,
)
from ..core.bridge_errors import (
    BridgeCredentialMismatchError,
    BridgeHandshakeMismatchError,
    BridgeWireError,
)
from ..core.errors import BridgeConnectionError
from ..core.failure_diagnostics import failure_diagnostic
from ..core.runtime import RuntimeRelease
from ..core.trace import error_trace_id
from .bridge_authentication import AuthenticatedBridge, BridgeAuthenticationPublication
from .bridge_binary_transfer import bridge_transport_message_limit
from .bridge_listener_policy import BridgeListenerPolicy
from .bridge_rpc_connection import BridgeRpcConnection
from .bridge_websocket import (
    BridgeServer,
    BridgeSocket,
    WebSocketRuntime,
    endpoint_from,
    frame_safe_logger,
    load_websocket_runtime,
    require_bridge_path,
)

logger = logging.getLogger(__name__)

_POLICY_CLOSE_CODE = 1008
_OWNER_CLOSE_CODE = 1001
_REJECT_REASON = "bridge handshake rejected"
_HANDSHAKE_TIMEOUT_REASON = "bridge handshake timeout"
_OWNER_CLOSE_REASON = "bridge listener closing"
_AUTHENTICATED_MISMATCH_REASON = "authenticated_handshake_mismatch"


class BridgeListener:
    """Own one server, its handlers, one credential, and one accepted socket."""

    def __init__(
        self,
        *,
        runtime: WebSocketRuntime,
        credential: str,
        owner: BridgeOwnerKey,
        release: RuntimeRelease,
        limits: BridgeLimits,
        policy: BridgeListenerPolicy,
    ) -> None:
        """Construct ownership before the server starts accepting connections."""
        self._runtime = runtime
        self._credential: str | None = credential
        self._owner = owner
        self._release = release
        self._limits = limits
        self._policy = policy
        self._server: BridgeServer | None = None
        self._endpoint: BridgeListenerEndpoint | None = None
        self._authentication = BridgeAuthenticationPublication()
        self._connections: set[BridgeSocket] = set()
        self._rpc_connection: BridgeRpcConnection | None = None
        self._accepting = False
        self._rejecting = False
        self._cleanup_complete = False
        self._close_task: asyncio.Task[None] | None = None

    @classmethod
    async def open(
        cls,
        expected: BridgeHandshakeExpectation,
        policy: BridgeListenerPolicy | None = None,
    ) -> BridgeListener:
        """Bind an IPv4 loopback listener without accepting before ownership exists."""
        if not isinstance(expected, BridgeHandshakeExpectation):
            raise ValueError("bridge listener expectation is invalid")
        selected_policy = policy or BridgeListenerPolicy()
        if not isinstance(selected_policy, BridgeListenerPolicy):
            raise ValueError("bridge listener policy is invalid")
        runtime = load_websocket_runtime()
        listener = cls(
            runtime=runtime,
            credential=expected.credential,
            owner=expected.owner,
            release=expected.release,
            limits=expected.limits,
            policy=selected_policy,
        )
        try:
            await listener._bind()
        except asyncio.CancelledError:
            await asyncio.shield(listener._close_after_failed_open())
            raise
        except Exception as exc:
            await listener._close_after_failed_open()
            if isinstance(exc, BridgeConnectionError):
                raise
            raise BridgeConnectionError(
                details={"reason": "listener_start_failed"},
                cause=exc,
            ) from None
        return listener

    @property
    def endpoint(self) -> BridgeListenerEndpoint:
        """Return the non-secret URL facts assigned during ``open``."""
        if self._endpoint is None:
            raise RuntimeError("bridge listener is not bound")
        return self._endpoint

    @property
    def accepting(self) -> bool:
        """Report whether a first authenticated connection may still win."""
        return self._accepting and not self._rejecting

    @property
    def closed(self) -> bool:
        """Report whether every transport resource finished cleanup."""
        return self._cleanup_complete

    async def claim_authenticated(self) -> AuthenticatedBridge:
        """Claim the sole published acceptance and controlled connection."""
        return await self._authentication.claim()

    async def close(self) -> None:
        """Reject new work and settle every transport owner within one bound."""
        self._begin_close()
        if self._cleanup_complete:
            return
        task = self._close_task
        if task is None:
            task = asyncio.create_task(
                self._close_attempt(),
                name=f"toqraq-bridge-close-{self.endpoint.port}",
            )
            task.add_done_callback(self._observe_close_task)
            self._close_task = task
        try:
            await asyncio.shield(task)
        finally:
            if task.done() and self._close_task is task:
                self._close_task = None

    def __repr__(self) -> str:
        """Expose only non-secret ownership state for diagnostics."""
        endpoint = self._endpoint.url if self._endpoint is not None else "unbound"
        state = "closed" if self.closed else "accepting" if self.accepting else "owned"
        return f"BridgeListener(endpoint={endpoint!r}, state={state!r})"

    async def _bind(self) -> None:
        """Create, inspect, and then start exactly one IPv4 socket."""
        high_queue = self._limits.max_in_flight_requests
        low_queue = max(1, high_queue // 4)
        write_low = max(1, self._policy.write_buffer_bytes // 4)
        transport_logger = frame_safe_logger()
        async with asyncio.timeout(self._policy.start_timeout_seconds):
            self._server = await self._runtime.serve(
                self._connection_handler,
                BRIDGE_LOOPBACK_HOST,
                0,
                origins=(None,),
                compression=None,
                server_header=None,
                open_timeout=self._policy.open_timeout_seconds,
                ping_interval=self._policy.ping_interval_seconds,
                ping_timeout=self._policy.ping_timeout_seconds,
                close_timeout=self._policy.close_timeout_seconds,
                max_size=bridge_transport_message_limit(
                    maximum_text_bytes=min(
                        self._limits.max_text_message_bytes,
                        MAX_BRIDGE_TEXT_MESSAGE_BYTES,
                    ),
                    maximum_binary_bytes=self._limits.max_binary_transfer_bytes,
                ),
                max_queue=(high_queue, low_queue),
                write_limit=(self._policy.write_buffer_bytes, write_low),
                logger=transport_logger,
                process_request=require_bridge_path,
                family=socket.AF_INET,
                start_serving=False,
            )
            self._endpoint = endpoint_from(self._server)
            await self._server.start_serving()
        self._accepting = True

    async def _connection_handler(self, connection: BridgeSocket) -> None:
        """Authenticate one candidate and keep only the winner's handler alive."""
        self._connections.add(connection)
        try:
            if self._rejecting or self._credential is None:
                await self._close_connection(connection, _REJECT_REASON)
                return
            await self._authenticate(connection)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not isinstance(exc, self._runtime.connection_closed):
                _log_handler_failure(exc)
                await self._close_connection(connection, _REJECT_REASON)
        finally:
            self._connections.discard(connection)

    async def _authenticate(self, connection: BridgeSocket) -> None:
        """Consume exactly one bounded text message and atomically claim success."""
        try:
            async with asyncio.timeout(self._policy.first_message_timeout_seconds):
                message = await connection.recv()
        except TimeoutError:
            await self._close_connection(connection, _HANDSHAKE_TIMEOUT_REASON)
            return
        if not isinstance(message, str):
            await self._close_connection(connection, _REJECT_REASON)
            return

        try:
            request = decode_handshake_request(
                message,
                maximum_bytes=self._limits.max_text_message_bytes,
            )
        except BridgeWireError as exc:
            response = bridge_error_response(
                exc,
                request_id=exc.request_id,
            ).model_dump_json()
            del message
            await self._send_rejection(connection, response)
            return

        credential = self._credential
        if credential is None or self._rejecting:
            del message, request
            await self._close_connection(connection, _REJECT_REASON)
            return
        expectation = BridgeHandshakeExpectation(
            credential=credential,
            owner=self._owner,
            release=self._release,
            limits=self._limits,
        )
        offer = request.params.to_core()
        try:
            acceptance = validate_bridge_handshake(offer, expectation)
        except BridgeHandshakeMismatchError as exc:
            if not isinstance(exc, BridgeCredentialMismatchError):
                self._fail_authenticated_handshake(exc)
            response = bridge_error_response(exc, request_id=request.id).model_dump_json()
            del message, request, offer, credential, expectation
            await self._send_rejection(connection, response)
            return

        success_request_id = request.id
        self._credential = None
        self._accepting = False
        server = self._server
        if server is None:
            self._fail_authentication("listener_closed")
            del message, request, offer, credential, expectation
            await self._close_connection(connection, _REJECT_REASON)
            return
        server.close(close_connections=False)
        del message, request, offer, credential, expectation
        try:
            response = BridgeHandshakeResponse.from_core(
                request_id=success_request_id,
                value=acceptance,
            ).model_dump_json()
            await self._send_text(connection, response)
        except Exception as exc:
            self._rejecting = True
            self._fail_authentication("handshake_response_failed", cause=exc)
            raise
        try:
            rpc_connection = BridgeRpcConnection(
                socket=connection,
                acceptance=acceptance,
                policy=self._policy.rpc,
                connection_closed=self._runtime.connection_closed,
            )
        except Exception as exc:
            self._rejecting = True
            self._fail_authentication("connection_start_failed", cause=exc)
            raise
        self._connections.discard(connection)
        self._rpc_connection = rpc_connection
        self._authentication.publish(
            AuthenticatedBridge(
                acceptance=acceptance,
                connection=rpc_connection,
            )
        )
        await rpc_connection.wait_disconnected()

    async def _send_rejection(self, connection: BridgeSocket, response: str) -> None:
        """Return one safe JSON-RPC error and then close the candidate."""
        try:
            await self._send_text(connection, response)
        finally:
            await self._close_connection(connection, _REJECT_REASON)

    async def _send_text(self, connection: BridgeSocket, response: str) -> None:
        """Bound transport backpressure independently of the close timeout."""
        async with asyncio.timeout(self._policy.send_timeout_seconds):
            await connection.send(response)

    async def _close_connection(self, connection: BridgeSocket, reason: str) -> None:
        """Bound one closing handshake without exposing rejected data."""
        async with asyncio.timeout(self._policy.close_timeout_seconds):
            await connection.close(_POLICY_CLOSE_CODE, reason)

    def _begin_close(self) -> None:
        """Synchronously consume credentials and prevent another winner."""
        self._rejecting = True
        self._accepting = False
        self._credential = None
        self._fail_authentication("listener_closed")

    def _fail_authenticated_handshake(self, error: BridgeHandshakeMismatchError) -> None:
        """Consume a launch whose credential proved contradictory build facts."""
        self._rejecting = True
        self._accepting = False
        self._credential = None
        self._authentication.fail(
            BridgeConnectionError(
                parameters=error.parameters,
                details={
                    "reason": _AUTHENTICATED_MISMATCH_REASON,
                    "wire_code": error.code,
                    "wire_category": error.category.value,
                },
                cause=error,
                trace_id=error.trace_id,
            )
        )
        server = self._server
        if server is not None:
            server.close(close_connections=False)

    def _fail_authentication(
        self,
        reason: str,
        *,
        cause: BaseException | None = None,
    ) -> None:
        """Publish one ordinary listener-owned terminal failure."""
        self._authentication.fail(BridgeConnectionError(details={"reason": reason}, cause=cause))

    async def _close_attempt(self) -> None:
        """Close candidates explicitly because authentication stops accept only."""
        server = self._server
        if server is None:
            self._cleanup_complete = True
            return
        server.close(close_connections=False)
        try:
            async with asyncio.timeout(self._policy.shutdown_timeout_seconds):
                closers = [
                    connection.close(_OWNER_CLOSE_CODE, _OWNER_CLOSE_REASON)
                    for connection in tuple(self._connections)
                ]
                if self._rpc_connection is not None:
                    closers.append(self._rpc_connection.close())
                results = await asyncio.gather(*closers, return_exceptions=True)
                await server.wait_closed()
        except TimeoutError as exc:
            raise BridgeConnectionError(
                details={"reason": "listener_cleanup_timeout"},
                cause=exc,
            ) from None
        except Exception as exc:
            raise BridgeConnectionError(
                details={"reason": "listener_cleanup_failed"},
                cause=exc,
            ) from None
        failures = [result for result in results if isinstance(result, BaseException)]
        if failures:
            raise BridgeConnectionError(
                details={"reason": "listener_cleanup_failed"},
                cause=BaseExceptionGroup("bridge connection cleanup failed", failures),
            )
        self._connections.clear()
        self._rpc_connection = None
        self._server = None
        self._cleanup_complete = True

    async def _close_after_failed_open(self) -> None:
        """Release a bound server that was never published to a caller."""
        self._begin_close()
        server = self._server
        if server is None:
            self._cleanup_complete = True
            return
        server.close()
        try:
            async with asyncio.timeout(self._policy.shutdown_timeout_seconds):
                await server.wait_closed()
        except TimeoutError as exc:
            raise BridgeConnectionError(
                details={"reason": "listener_open_rollback_timeout"},
                cause=exc,
            ) from None
        except Exception as exc:
            raise BridgeConnectionError(
                details={"reason": "listener_open_rollback_failed"},
                cause=exc,
            ) from None
        self._server = None
        self._cleanup_complete = True

    def _observe_close_task(self, task: asyncio.Task[None]) -> None:
        """Observe cancellation or failure even if the awaiting owner is cancelled."""
        if task.cancelled():
            return
        failure = task.exception()
        if failure is None:
            return
        diagnostic = failure_diagnostic(failure)
        logger.error(
            "bridge listener cleanup failure trace_id=%s exception_type=%s stack_locations=%s",
            error_trace_id(),
            diagnostic.exception_type,
            ",".join(diagnostic.stack_locations),
        )


def _log_handler_failure(exception: BaseException) -> None:
    """Observe a handler failure without formatting exception data or frame locals."""
    diagnostic = failure_diagnostic(exception)
    logger.error(
        "bridge connection handler failure trace_id=%s exception_type=%s stack_locations=%s",
        error_trace_id(),
        diagnostic.exception_type,
        ",".join(diagnostic.stack_locations),
    )
