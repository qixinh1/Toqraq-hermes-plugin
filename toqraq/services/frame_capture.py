"""Verified complete live-frame capture use case."""

from __future__ import annotations

from ..contracts.bridge_frame import FrameCaptureParams
from ..contracts.frame_capture import FrameCaptureResult
from ..contracts.identifiers import HermesSessionId
from ..core.capability_ids import OBSERVE_FRAME_CAPABILITY_ID
from ..core.session_registry import SessionRegistry
from .session_feature_access import (
    perception_access,
    validate_feature_dependencies,
    verified_feature_result,
)
from .session_gate import SessionOperationGate


class FrameCaptureService:
    """Capture one verified PNG and convert only its public JSON representation."""

    __slots__ = ("_gate", "_registry")

    def __init__(self, registry: SessionRegistry, gate: SessionOperationGate) -> None:
        """Share the exact registry and operation gate with session lifecycle."""
        validate_feature_dependencies(registry, gate)
        self._registry = registry
        self._gate = gate

    async def capture(
        self,
        session_id: HermesSessionId,
        request: FrameCaptureParams,
    ) -> FrameCaptureResult:
        """Capture, correlate, and expose one complete canonical base64 PNG."""
        query = request.to_core()
        async with perception_access(
            self._registry,
            self._gate,
            session_id,
            OBSERVE_FRAME_CAPABILITY_ID,
        ) as access:
            frame = await access.resources.invoke_owned(access.ports.frame.capture(query))
            return verified_feature_result(
                OBSERVE_FRAME_CAPABILITY_ID,
                lambda: FrameCaptureResult.from_core(frame, query=query),
            )
