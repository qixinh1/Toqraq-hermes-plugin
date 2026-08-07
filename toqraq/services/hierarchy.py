"""Bounded live hierarchy perception use case."""

from __future__ import annotations

from ..contracts.bridge_hierarchy import HierarchyReadParams, HierarchyReadResult
from ..contracts.identifiers import HermesSessionId
from ..core.capability_ids import OBSERVE_HIERARCHY_CAPABILITY_ID
from ..core.session_registry import SessionRegistry
from .session_feature_access import (
    perception_access,
    validate_feature_dependencies,
    verified_feature_result,
)
from .session_gate import SessionOperationGate


class HierarchyService:
    """Read one revision-consistent flat hierarchy page from the current run."""

    __slots__ = ("_gate", "_registry")

    def __init__(self, registry: SessionRegistry, gate: SessionOperationGate) -> None:
        """Share the exact registry and operation gate with session lifecycle."""
        validate_feature_dependencies(registry, gate)
        self._registry = registry
        self._gate = gate

    async def read(
        self,
        session_id: HermesSessionId,
        request: HierarchyReadParams,
    ) -> HierarchyReadResult:
        """Read and correlate one bounded hierarchy page."""
        query = request.to_core()
        async with perception_access(
            self._registry,
            self._gate,
            session_id,
            OBSERVE_HIERARCHY_CAPABILITY_ID,
        ) as access:
            page = await access.resources.invoke_owned(access.ports.hierarchy.read(query))
            return verified_feature_result(
                OBSERVE_HIERARCHY_CAPABILITY_ID,
                lambda: HierarchyReadResult.from_core(page, query=query),
            )
