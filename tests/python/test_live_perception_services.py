"""Focused hierarchy, object, diagnostic, and metric service tests."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest
from toqraq.contracts.bridge_diagnostics import DiagnosticsReadParams, DiagnosticsReadResult
from toqraq.contracts.bridge_frame import FrameCaptureParams
from toqraq.contracts.bridge_hierarchy import HierarchyReadParams, HierarchyReadResult
from toqraq.contracts.bridge_input import SemanticInputParams
from toqraq.contracts.bridge_metrics import MetricsReadParams, MetricsReadResult
from toqraq.contracts.bridge_objects import ObjectReadParams, ObjectReadResult
from toqraq.core.capability_ids import (
    CONTROL_INPUT_CAPABILITY_ID,
    MANDATORY_BRIDGE_CAPABILITY_IDS,
    OBSERVE_DIAGNOSTICS_CAPABILITY_ID,
    OBSERVE_FRAME_CAPABILITY_ID,
    OBSERVE_HIERARCHY_CAPABILITY_ID,
    OBSERVE_PERFORMANCE_CAPABILITY_ID,
    OBSERVE_PROPERTIES_CAPABILITY_ID,
)
from toqraq.core.errors import (
    CapabilityUnavailableError,
    ProtocolError,
    SessionNotFoundError,
)
from toqraq.core.observation import ObservationRevision
from toqraq.core.session_registry import SessionRegistry
from toqraq.services.diagnostics import DiagnosticsService
from toqraq.services.frame_capture import FrameCaptureService
from toqraq.services.hierarchy import HierarchyService
from toqraq.services.input import InputService
from toqraq.services.metrics import MetricsService
from toqraq.services.object_inspection import ObjectInspectionService
from toqraq.services.session_gate import SessionOperationGate

from _bridge_feature_values import (
    diagnostics_values,
    frame_values,
    hierarchy_values,
    input_commands,
    metrics_values,
    object_values,
)
from _live_feature_support import LiveFeatureFixture, make_live_feature_fixture


async def _invoke_feature(kind: str, fixture: LiveFeatureFixture) -> object:
    """Invoke one focused service with its canonical valid request."""
    if kind == "hierarchy":
        query, _result = hierarchy_values()
        return await HierarchyService(fixture.registry, fixture.gate).read(
            "hermes-session",
            HierarchyReadParams.from_core(query),
        )
    if kind == "objects":
        query, _result = object_values()
        return await ObjectInspectionService(fixture.registry, fixture.gate).read(
            "hermes-session",
            ObjectReadParams.from_core(query),
        )
    if kind == "diagnostics":
        query, _result = diagnostics_values()
        return await DiagnosticsService(fixture.registry, fixture.gate).read(
            "hermes-session",
            DiagnosticsReadParams.from_core(query),
        )
    if kind == "metrics":
        query, _result = metrics_values()
        return await MetricsService(fixture.registry, fixture.gate).read(
            "hermes-session",
            MetricsReadParams.from_core(query),
        )
    if kind == "frame":
        query, _result = frame_values()
        return await FrameCaptureService(fixture.registry, fixture.gate).capture(
            "hermes-session",
            FrameCaptureParams.from_core(query),
        )
    command, *_other_commands = input_commands()
    return await InputService(fixture.registry, fixture.gate).semantic(
        "hermes-session",
        SemanticInputParams.from_core(command),
    )


def test_each_perception_service_reuses_and_correlates_bridge_values(tmp_path: Path) -> None:
    async def run() -> None:
        fixture = make_live_feature_fixture(tmp_path)
        hierarchy_query, hierarchy_page = hierarchy_values()
        object_query, object_snapshot = object_values()
        diagnostics_query, diagnostics_page = diagnostics_values()
        metrics_query, metrics_snapshot = metrics_values()
        try:
            hierarchy = await HierarchyService(fixture.registry, fixture.gate).read(
                "hermes-session",
                HierarchyReadParams.from_core(hierarchy_query),
            )
            objects = await ObjectInspectionService(fixture.registry, fixture.gate).read(
                "hermes-session",
                ObjectReadParams.from_core(object_query),
            )
            diagnostics = await DiagnosticsService(fixture.registry, fixture.gate).read(
                "hermes-session",
                DiagnosticsReadParams.from_core(diagnostics_query),
            )
            metrics = await MetricsService(fixture.registry, fixture.gate).read(
                "hermes-session",
                MetricsReadParams.from_core(metrics_query),
            )

            assert hierarchy == HierarchyReadResult.from_core(
                hierarchy_page,
                query=hierarchy_query,
            )
            assert objects == ObjectReadResult.from_core(object_snapshot, query=object_query)
            assert diagnostics == DiagnosticsReadResult.from_core(
                diagnostics_page,
                query=diagnostics_query,
            )
            assert metrics == MetricsReadResult.from_core(metrics_snapshot, query=metrics_query)
            assert fixture.hierarchy.queries == [hierarchy_query]
            assert fixture.objects.queries == [object_query]
            assert fixture.diagnostics.queries == [diagnostics_query]
            assert fixture.metrics.queries == [metrics_query]
        finally:
            await fixture.close()

    asyncio.run(run())


def test_perception_requires_ready_ports_and_an_existing_session(tmp_path: Path) -> None:
    async def run() -> None:
        fixture = make_live_feature_fixture(tmp_path, publish_features=False)
        query, _page = hierarchy_values()
        request = HierarchyReadParams.from_core(query)
        try:
            with pytest.raises(CapabilityUnavailableError) as captured:
                await HierarchyService(fixture.registry, fixture.gate).read(
                    "hermes-session",
                    request,
                )
            assert captured.value.parameters == {"capability_id": OBSERVE_HIERARCHY_CAPABILITY_ID}
            assert captured.value.details == {
                "reason": "perception_not_ready",
                "state": "connecting",
            }
        finally:
            await fixture.close()

        empty_service = HierarchyService(SessionRegistry(), SessionOperationGate())
        with pytest.raises(SessionNotFoundError):
            await empty_service.read("missing-session", request)

    asyncio.run(run())


@pytest.mark.parametrize(
    ("kind", "capability_id"),
    [
        ("hierarchy", OBSERVE_HIERARCHY_CAPABILITY_ID),
        ("objects", OBSERVE_PROPERTIES_CAPABILITY_ID),
        ("diagnostics", OBSERVE_DIAGNOSTICS_CAPABILITY_ID),
        ("metrics", OBSERVE_PERFORMANCE_CAPABILITY_ID),
        ("frame", OBSERVE_FRAME_CAPABILITY_ID),
        ("input", CONTROL_INPUT_CAPABILITY_ID),
    ],
)
def test_each_service_requires_its_exact_bridge_capability(
    tmp_path: Path,
    kind: str,
    capability_id: str,
) -> None:
    async def run() -> None:
        fixture = make_live_feature_fixture(
            tmp_path,
            bridge_capability_ids=MANDATORY_BRIDGE_CAPABILITY_IDS - {capability_id},
        )
        try:
            with pytest.raises(CapabilityUnavailableError) as captured:
                await _invoke_feature(kind, fixture)
            assert captured.value.parameters == {"capability_id": capability_id}
            assert captured.value.details == {"reason": "capability_not_advertised"}
        finally:
            await fixture.close()

    asyncio.run(run())


def test_result_correlation_failure_becomes_a_stable_protocol_error(tmp_path: Path) -> None:
    async def run() -> None:
        fixture = make_live_feature_fixture(tmp_path)
        query, _page = hierarchy_values()
        stale_query = replace(
            query,
            revision=ObservationRevision(value="hierarchy:other"),
        )
        try:
            with pytest.raises(ProtocolError) as captured:
                await HierarchyService(fixture.registry, fixture.gate).read(
                    "hermes-session",
                    HierarchyReadParams.from_core(stale_query),
                )
            assert captured.value.parameters == {"operation": OBSERVE_HIERARCHY_CAPABILITY_ID}
            assert captured.value.details == {"reason": "result_contract_invalid"}
            assert isinstance(captured.value.cause, ValueError)
        finally:
            await fixture.close()

    asyncio.run(run())


def test_session_gate_stays_held_until_result_correlation_finishes(tmp_path: Path) -> None:
    async def run() -> None:
        fixture = make_live_feature_fixture(tmp_path)
        query, _page = hierarchy_values()
        lease = await fixture.gate.acquire("hermes-session")
        try:
            pending = asyncio.create_task(
                HierarchyService(fixture.registry, fixture.gate).read(
                    "hermes-session",
                    HierarchyReadParams.from_core(query),
                )
            )
            await asyncio.sleep(0)
            assert fixture.hierarchy.queries == []
            lease.close()
            await pending
            assert fixture.hierarchy.queries == [query]
        finally:
            lease.close()
            await fixture.close()

    asyncio.run(run())
