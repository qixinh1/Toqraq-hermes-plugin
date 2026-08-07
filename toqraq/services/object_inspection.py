"""Selected live runtime-object perception use case."""

from __future__ import annotations

from ..contracts.bridge_objects import ObjectReadParams, ObjectReadResult
from ..contracts.identifiers import HermesSessionId
from ..core.capability_ids import OBSERVE_PROPERTIES_CAPABILITY_ID
from ..core.session_registry import SessionRegistry
from .session_feature_access import (
    perception_access,
    validate_feature_dependencies,
    verified_feature_result,
)
from .session_gate import SessionOperationGate


class ObjectInspectionService:
    """Read selected field groups for explicit opaque live-object references."""

    __slots__ = ("_gate", "_registry")

    def __init__(self, registry: SessionRegistry, gate: SessionOperationGate) -> None:
        """Share the exact registry and operation gate with session lifecycle."""
        validate_feature_dependencies(registry, gate)
        self._registry = registry
        self._gate = gate

    async def read(
        self,
        session_id: HermesSessionId,
        request: ObjectReadParams,
    ) -> ObjectReadResult:
        """Read and correlate one bounded selected-object snapshot."""
        query = request.to_core()
        async with perception_access(
            self._registry,
            self._gate,
            session_id,
            OBSERVE_PROPERTIES_CAPABILITY_ID,
        ) as access:
            snapshot = await access.resources.invoke_owned(access.ports.objects.read(query))
            return verified_feature_result(
                OBSERVE_PROPERTIES_CAPABILITY_ID,
                lambda: ObjectReadResult.from_core(snapshot, query=query),
            )
