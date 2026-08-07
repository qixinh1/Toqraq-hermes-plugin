"""Atomic access to borrowed live feature ports for one current session owner."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TypeVar

from ..contracts.identifiers import HermesSessionId
from ..core.errors import CapabilityUnavailableError, ProtocolError
from ..core.run_resources import GameRunResources
from ..core.runtime_features import RuntimeFeaturePorts
from ..core.session import EngineSession
from ..core.session_readiness import FeatureReadiness
from ..core.session_registry import SessionRegistry
from .session_gate import SessionOperationGate

ResultT = TypeVar("ResultT")


@dataclass(frozen=True, slots=True)
class BorrowedFeatureAccess:
    """Current session, ports, and resource owner held by one operation gate."""

    session: EngineSession
    resources: GameRunResources
    ports: RuntimeFeaturePorts


def validate_feature_dependencies(
    registry: SessionRegistry,
    gate: SessionOperationGate,
) -> None:
    """Reject composition that does not share lifecycle ownership boundaries."""
    if not isinstance(registry, SessionRegistry):
        raise ValueError("live feature registry is invalid")
    if not isinstance(gate, SessionOperationGate):
        raise ValueError("live feature session gate is invalid")


@asynccontextmanager
async def perception_access(
    registry: SessionRegistry,
    gate: SessionOperationGate,
    session_id: HermesSessionId,
    capability_id: str,
) -> AsyncIterator[BorrowedFeatureAccess]:
    """Hold the current owner stable while one read-only feature call completes."""
    lease = await gate.acquire(session_id)
    async with lease:
        session = registry.get(session_id)
        yield _require_access(session, capability_id, control=False)


@asynccontextmanager
async def control_access(
    registry: SessionRegistry,
    gate: SessionOperationGate,
    session_id: HermesSessionId,
    capability_id: str,
) -> AsyncIterator[BorrowedFeatureAccess]:
    """Hold the current owner stable while one input feature call completes."""
    lease = await gate.acquire(session_id)
    async with lease:
        session = registry.get(session_id)
        yield _require_access(session, capability_id, control=True)


def verified_feature_result(
    capability_id: str,
    build: Callable[[], ResultT],
) -> ResultT:
    """Turn an adapter contract violation into one stable Bridge failure."""
    try:
        return build()
    except (TypeError, ValueError) as exc:
        raise ProtocolError(
            parameters={"operation": capability_id},
            details={"reason": "result_contract_invalid"},
            cause=exc,
        ) from exc


def _require_access(
    session: EngineSession,
    capability_id: str,
    *,
    control: bool,
) -> BorrowedFeatureAccess:
    """Require exact advertised support, group readiness, and published ports."""
    snapshot = session.snapshot()
    if capability_id not in snapshot.bridge_capability_ids:
        raise CapabilityUnavailableError(
            parameters={"capability_id": capability_id},
            details={"reason": "capability_not_advertised"},
        )
    readiness = session.control_readiness if control else session.perception_readiness
    if readiness.state is not FeatureReadiness.READY:
        raise CapabilityUnavailableError(
            parameters={"capability_id": capability_id},
            details={
                "reason": "control_not_ready" if control else "perception_not_ready",
                "state": readiness.state.value,
            },
        )
    ports = session.feature_ports
    if ports is None:
        raise CapabilityUnavailableError(
            parameters={"capability_id": capability_id},
            details={"reason": "feature_ports_unavailable"},
        )
    return BorrowedFeatureAccess(
        session=session,
        resources=session.resources,
        ports=ports,
    )
