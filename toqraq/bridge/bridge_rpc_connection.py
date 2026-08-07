"""Single-reader ownership for one authenticated engine Bridge RPC socket."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeAlias, TypeVar, cast

from ..contracts.base import ContractModel
from ..contracts.bridge_cancellation import RequestCancelRequest, RequestCancelResponse
from ..contracts.bridge_rpc import BridgeRpcSuccessEnvelope, BridgeStateFamily
from ..core.bridge import BridgeHandshakeAcceptance, BridgeRequestReference
from ..core.errors import BridgeConnectionError, ProtocolError
from ..core.request_cancellation import CancelRequestCommand
from .bridge_binary_transfer import (
    BridgeBinaryAnnouncementDecoder,
    BridgeBinaryProtocolReason,
    binary_protocol_error,
)
from .bridge_rpc_codec import (
    decode_bridge_rpc_message,
    decode_expected_success,
    encode_bridge_rpc_request,
)
from .bridge_rpc_dispatcher import BridgeRpcDispatcher
from .bridge_rpc_observability import (
    observe_bridge_failure,
    observe_bridge_ownership_task,
)
from .bridge_rpc_registry import BridgeRequestRegistry
from .bridge_rpc_sender import BridgeRpcSender
from .bridge_rpc_state import (
    BridgeDisconnection,
    BridgeDisconnectionKind,
    BridgeRemoteErrorMapper,
    BridgeResponseDecoder,
    BridgeRpcPolicy,
    PendingBridgeRequest,
    copy_connection_failure,
    reject_unmapped_remote_error,
)
from .bridge_rpc_termination import BridgeConnectionTermination
from .bridge_websocket import BridgeSocket

ResponseT = TypeVar("ResponseT", bound=ContractModel)
BridgeRequestFactory: TypeAlias = Callable[[str], ContractModel]


class BridgeRpcConnection:
    """Own one socket reader, pending registry, deadlines, and close path."""

    def __init__(
        self,
        *,
        socket: BridgeSocket,
        acceptance: BridgeHandshakeAcceptance,
        policy: BridgeRpcPolicy,
        connection_closed: type[Exception],
    ) -> None:
        """Start the sole reader only after every owned field exists."""
        if not isinstance(acceptance, BridgeHandshakeAcceptance):
            raise ValueError("bridge RPC acceptance is invalid")
        if not isinstance(policy, BridgeRpcPolicy):
            raise ValueError("bridge RPC policy is invalid")
        if not isinstance(connection_closed, type) or not issubclass(connection_closed, Exception):
            raise ValueError("bridge connection-closed type is invalid")
        self._socket = socket
        self._acceptance = acceptance
        self._policy = policy
        self._connection_closed = connection_closed
        self._maximum_text_bytes = min(acceptance.limits.max_text_message_bytes, 262_144)
        self._cancel_slot = asyncio.Lock()
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._termination = BridgeConnectionTermination(
            socket=socket,
            close_timeout_seconds=policy.close_timeout_seconds,
        )
        self._registry = BridgeRequestRegistry(
            maximum_work=acceptance.limits.max_in_flight_requests,
            termination=self._termination.started_event,
            expire_work=self._expire_work,
        )
        self._dispatcher = BridgeRpcDispatcher(
            registry=self._registry,
            maximum_binary_bytes=acceptance.limits.max_binary_transfer_bytes,
        )
        self._sender = BridgeRpcSender(
            socket=socket,
            send_timeout_seconds=policy.send_timeout_seconds,
            transport_failed=self._begin_transport_failure,
        )
        self._close_task: asyncio.Task[None] | None = None
        self._cleanup_complete = False
        self._reader_task = asyncio.create_task(
            self._read_frames(),
            name="toqraq-bridge-rpc-reader",
        )
        self._reader_task.add_done_callback(observe_bridge_ownership_task)

    @property
    def disconnected(self) -> bool:
        """Report whether transport teardown reached a terminal fact."""
        return self._termination.disconnected

    @property
    def closed(self) -> bool:
        """Report whether transport, reader, and child tasks were reclaimed."""
        return self._cleanup_complete

    async def call(
        self,
        request_factory: BridgeRequestFactory,
        response_decoder: Callable[[BridgeRpcSuccessEnvelope], ResponseT],
        *,
        map_remote_error: BridgeRemoteErrorMapper | None = None,
        timeout_seconds: float | None = None,
    ) -> ResponseT:
        """Send one internally composed typed operation within its total deadline."""
        result = await self._call(
            request_factory,
            response_decoder=cast(BridgeResponseDecoder, response_decoder),
            binary_decoder=None,
            map_remote_error=map_remote_error,
            timeout_seconds=timeout_seconds,
        )
        return cast(ResponseT, result)

    async def call_binary(
        self,
        request_factory: BridgeRequestFactory,
        announcement_decoder: BridgeBinaryAnnouncementDecoder,
        *,
        map_remote_error: BridgeRemoteErrorMapper | None = None,
        timeout_seconds: float | None = None,
    ) -> ContractModel:
        """Send one request that completes only after its announced binary."""
        return await self._call(
            request_factory,
            response_decoder=None,
            binary_decoder=announcement_decoder,
            map_remote_error=map_remote_error,
            timeout_seconds=timeout_seconds,
        )

    async def _call(
        self,
        request_factory: BridgeRequestFactory,
        *,
        response_decoder: BridgeResponseDecoder | None,
        binary_decoder: BridgeBinaryAnnouncementDecoder | None,
        map_remote_error: BridgeRemoteErrorMapper | None,
        timeout_seconds: float | None,
    ) -> ContractModel:
        """Own the shared deadline, registration, send, wait, and cancellation path."""
        if (response_decoder is None) == (binary_decoder is None):
            raise TypeError("bridge call must own exactly one response decoder")
        timeout = self._policy.validate_work_timeout(timeout_seconds)
        loop = asyncio.get_running_loop()
        expires_at = loop.time() + timeout
        await self._acquire_work_slot(expires_at)
        try:
            request_id = self._registry.issue_id()
            request = request_factory(request_id)
            payload = encode_bridge_rpc_request(
                request,
                request_id=request_id,
                maximum_bytes=self._maximum_text_bytes,
            )
            mapper = reject_unmapped_remote_error if map_remote_error is None else map_remote_error
            if response_decoder is not None:
                pending = self._registry.register_work(
                    request_id=request_id,
                    decoder=response_decoder,
                    map_remote_error=mapper,
                    expires_at=expires_at,
                )
            else:
                if binary_decoder is None:
                    raise RuntimeError("bridge binary decoder ownership was lost")
                pending = self._registry.register_binary_work(
                    request_id=request_id,
                    decoder=binary_decoder,
                    map_remote_error=mapper,
                    expires_at=expires_at,
                )
        except BaseException:
            self._registry.release_unregistered_work()
            raise

        send_task = self._sender.start(pending, payload, expires_at)
        try:
            await asyncio.shield(send_task)
            result = await asyncio.shield(pending.future)
            return result
        except asyncio.CancelledError:
            if self._dispatcher.binary_owned_by(pending.request_id):
                self._begin_termination(
                    BridgeDisconnectionKind.PROTOCOL,
                    binary_protocol_error(BridgeBinaryProtocolReason.CALLER_CANCELLED),
                )
                raise
            cancel_task = self._ensure_cancel_task(pending)
            if cancel_task is not None:
                await asyncio.shield(cancel_task)
            raise

    def take_state_changes(self) -> tuple[BridgeStateFamily, ...]:
        """Return and clear one canonical merged dirty-family snapshot."""
        return self._dispatcher.take_state_changes()

    async def wait_disconnected(self) -> BridgeDisconnection:
        """Wait for natural, policy, transport, or owner disconnection."""
        return await self._termination.wait()

    async def wait_failure(self) -> BridgeConnectionError:
        """Return a safe copy of the first failure after transport teardown."""
        await self.wait_disconnected()
        return copy_connection_failure(self._termination.failure)

    async def close(self) -> None:
        """Idempotently settle all waiters and reclaim every owned async task."""
        self._begin_termination(
            BridgeDisconnectionKind.OWNER,
            BridgeConnectionError(details={"reason": "connection_closed"}),
        )
        if self._cleanup_complete:
            return
        task = self._close_task
        if task is None:
            task = asyncio.create_task(
                self._close_attempt(),
                name="toqraq-bridge-rpc-close",
            )
            task.add_done_callback(observe_bridge_ownership_task)
            self._close_task = task
        try:
            await asyncio.shield(task)
        finally:
            if task.done() and self._close_task is task:
                self._close_task = None

    def __repr__(self) -> str:
        """Expose only non-secret owner and bounded connection state."""
        owner = self._acceptance.owner
        state = "closed" if self.closed else "disconnected" if self.disconnected else "active"
        return (
            "BridgeRpcConnection("
            f"session_id={owner.session_id!r}, run_revision={owner.run_revision!r}, "
            f"state={state!r}, pending={self._registry.count!r})"
        )

    async def _read_frames(self) -> None:
        """Decode every post-authentication frame from the sole recv owner."""
        try:
            while not self._termination.started:
                frame = await self._socket.recv()
                if isinstance(frame, bytes):
                    self._dispatcher.dispatch_binary(frame)
                    continue
                if not isinstance(frame, str):
                    raise ProtocolError(details={"reason": "invalid_rpc_message"})
                envelope = decode_bridge_rpc_message(
                    frame,
                    maximum_bytes=self._maximum_text_bytes,
                )
                self._dispatcher.dispatch_text(envelope)
        except asyncio.CancelledError:
            if not self._termination.started:
                self._begin_transport_failure("reader_cancelled")
            raise
        except self._connection_closed:
            self._begin_termination(
                BridgeDisconnectionKind.REMOTE,
                BridgeConnectionError(details={"reason": "connection_closed"}),
            )
        except ProtocolError as exc:
            self._begin_termination(BridgeDisconnectionKind.PROTOCOL, exc)
        except Exception as exc:
            observe_bridge_failure(exc)
            self._begin_transport_failure("reader_failed")

    def _expire_work(self, request_id: str) -> None:
        """Release one ordinary owner at its hard deadline and signal cancellation."""
        pending = self._registry.find(request_id)
        if pending is None:
            return
        if self._dispatcher.binary_owned_by(request_id):
            self._begin_termination(
                BridgeDisconnectionKind.PROTOCOL,
                binary_protocol_error(BridgeBinaryProtocolReason.DEADLINE),
            )
            return
        pending.expired = True
        self._registry.complete(
            pending,
            error=BridgeConnectionError(details={"reason": "request_deadline"}),
        )
        self._ensure_cancel_task(pending)

    def _ensure_cancel_task(
        self,
        pending: PendingBridgeRequest,
    ) -> asyncio.Task[None] | None:
        """Create at most one independent cancellation owner for one work request."""
        if pending.cancel_task is not None:
            return pending.cancel_task
        if pending.terminal and not pending.expired:
            return None
        task = asyncio.create_task(
            self._cancel_work(pending),
            name=f"toqraq-bridge-cancel-{pending.request_id}",
        )
        pending.cancel_task = task
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        task.add_done_callback(observe_bridge_ownership_task)
        return task

    async def _cancel_work(self, target: PendingBridgeRequest) -> None:
        """Use the independent control slot and fail closed when its grace expires."""
        try:
            if target.send_task is not None:
                await asyncio.shield(target.send_task)
            if not target.dispatched or (target.terminal and not target.expired):
                return
            loop = asyncio.get_running_loop()
            expires_at = loop.time() + self._policy.cancellation_grace_seconds
            async with asyncio.timeout_at(expires_at):
                async with self._cancel_slot:
                    await self._send_cancel_request(target.request_id, expires_at)
        except asyncio.CancelledError:
            if self._termination.started:
                return
            raise
        except Exception:
            self._begin_termination(
                BridgeDisconnectionKind.CANCELLATION_CONTROL,
                BridgeConnectionError(details={"reason": "cancellation_control_failed"}),
            )

    async def _send_cancel_request(
        self,
        target_request_id: str,
        expires_at: float,
    ) -> RequestCancelResponse:
        """Register and await exactly one cancellation acknowledgement."""
        request_id = self._registry.issue_id()
        request = RequestCancelRequest.from_core(
            request_id=request_id,
            command=CancelRequestCommand(
                target=BridgeRequestReference(value=target_request_id),
            ),
        )
        payload = encode_bridge_rpc_request(
            request,
            request_id=request_id,
            maximum_bytes=self._maximum_text_bytes,
        )
        pending = self._registry.register_control(
            request_id=request_id,
            decoder=cast(
                BridgeResponseDecoder,
                lambda envelope: decode_expected_success(envelope, RequestCancelResponse),
            ),
            map_remote_error=reject_unmapped_remote_error,
        )
        try:
            await self._sender.send(payload, expires_at=expires_at)
            pending.dispatched = True
            response = await asyncio.shield(pending.future)
            return cast(RequestCancelResponse, response)
        finally:
            if self._registry.find(request_id) is pending:
                self._registry.complete(
                    pending,
                    error=BridgeConnectionError(details={"reason": "cancellation_interrupted"}),
                )

    def _begin_transport_failure(self, reason: str) -> None:
        """Start fail-closed transport teardown with one safe reason."""
        self._begin_termination(
            BridgeDisconnectionKind.TRANSPORT,
            BridgeConnectionError(details={"reason": reason}),
        )

    def _begin_termination(
        self,
        kind: BridgeDisconnectionKind,
        failure: BridgeConnectionError,
    ) -> None:
        """Atomically choose the first cause and stop accepting new work."""
        if self._termination.started:
            return
        if not self._termination.begin(kind, failure):
            return
        self._dispatcher.clear_binary()
        self._registry.fail_all(failure)
        current = asyncio.current_task()
        for task in tuple(self._background_tasks):
            if task is not current:
                task.cancel()

    async def _close_attempt(self) -> None:
        """Await socket, reader, and all strongly owned child tasks."""
        transport = self._termination.ensure_transport()
        try:
            async with asyncio.timeout(self._policy.close_timeout_seconds):
                await asyncio.shield(transport)
                await asyncio.shield(self._reader_task)
                children = tuple(self._background_tasks)
                if children:
                    await asyncio.gather(*children, return_exceptions=True)
                await self._sender.wait()
        except TimeoutError as exc:
            raise BridgeConnectionError(
                details={"reason": "connection_cleanup_timeout"},
                cause=exc,
            ) from None
        self._cleanup_complete = True

    async def _acquire_work_slot(self, expires_at: float) -> None:
        """Include queueing for the negotiated work slot in the total deadline."""
        if self._termination.started:
            raise copy_connection_failure(self._termination.failure)
        try:
            acquired = await self._registry.acquire_work(expires_at=expires_at)
        except TimeoutError:
            raise BridgeConnectionError(details={"reason": "request_deadline"}) from None
        if not acquired:
            raise copy_connection_failure(self._termination.failure)
