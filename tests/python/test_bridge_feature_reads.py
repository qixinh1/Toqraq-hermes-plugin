"""Real-socket conformance for the four focused common Bridge read ports."""

from __future__ import annotations

import asyncio

from toqraq.bridge.bridge_features.aggregate import create_bridge_feature_ports
from toqraq.contracts.bridge_diagnostics import DiagnosticsReadRequest, DiagnosticsReadResponse
from toqraq.contracts.bridge_hierarchy import HierarchyReadRequest, HierarchyReadResponse
from toqraq.contracts.bridge_metrics import MetricsReadRequest, MetricsReadResponse
from toqraq.contracts.bridge_objects import ObjectReadRequest, ObjectReadResponse
from toqraq.core.diagnostics import DiagnosticsReader
from toqraq.core.frame_capture import FrameCapture
from toqraq.core.hierarchy import HierarchyReader
from toqraq.core.input_control import InputController
from toqraq.core.metrics import MetricsReader
from toqraq.core.object_inspection import ObjectReader
from toqraq.core.runtime_features import RuntimeFeaturePorts
from toqraq.core.simulation_control import SimulationController

from _bridge_feature_values import (
    diagnostics_values,
    hierarchy_values,
    metrics_values,
    object_values,
)
from _bridge_rpc_support import open_rpc_harness, receive_json


def test_feature_aggregate_exposes_only_the_seven_focused_core_ports() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness()
        features = create_bridge_feature_ports(harness.authenticated)

        assert isinstance(features, RuntimeFeaturePorts)
        assert isinstance(features.hierarchy, HierarchyReader)
        assert isinstance(features.objects, ObjectReader)
        assert isinstance(features.diagnostics, DiagnosticsReader)
        assert isinstance(features.metrics, MetricsReader)
        assert isinstance(features.frame, FrameCapture)
        assert isinstance(features.simulation, SimulationController)
        assert isinstance(features.input, InputController)
        assert not hasattr(features, "connection")
        assert not hasattr(features, "call")
        assert not hasattr(features, "close")

        await harness.close()

    asyncio.run(scenario())


def test_read_adapters_construct_and_correlate_each_exact_method() -> None:
    async def scenario() -> None:
        harness = await open_rpc_harness()
        features = create_bridge_feature_ports(harness.authenticated)

        hierarchy_query, hierarchy_page = hierarchy_values()
        hierarchy_call = asyncio.create_task(features.hierarchy.read(hierarchy_query))
        wire = await receive_json(harness.peer)
        request = HierarchyReadRequest.model_validate(wire)
        assert request.params.to_core() == hierarchy_query
        await harness.peer.send(
            HierarchyReadResponse.from_core(
                request_id=request.id,
                value=hierarchy_page,
                query=hierarchy_query,
            ).model_dump_json()
        )
        assert await hierarchy_call == hierarchy_page

        object_query, object_snapshot = object_values()
        object_call = asyncio.create_task(features.objects.read(object_query))
        wire = await receive_json(harness.peer)
        request_object = ObjectReadRequest.model_validate(wire)
        assert request_object.params.to_core() == object_query
        await harness.peer.send(
            ObjectReadResponse.from_core(
                request_id=request_object.id,
                value=object_snapshot,
                query=object_query,
            ).model_dump_json()
        )
        assert await object_call == object_snapshot

        diagnostics_query, diagnostics_page = diagnostics_values()
        diagnostics_call = asyncio.create_task(features.diagnostics.read(diagnostics_query))
        wire = await receive_json(harness.peer)
        request_diagnostics = DiagnosticsReadRequest.model_validate(wire)
        assert request_diagnostics.params.to_core() == diagnostics_query
        await harness.peer.send(
            DiagnosticsReadResponse.from_core(
                request_id=request_diagnostics.id,
                value=diagnostics_page,
                query=diagnostics_query,
            ).model_dump_json()
        )
        assert await diagnostics_call == diagnostics_page

        metrics_query, metrics_snapshot = metrics_values()
        metrics_call = asyncio.create_task(features.metrics.read(metrics_query))
        wire = await receive_json(harness.peer)
        request_metrics = MetricsReadRequest.model_validate(wire)
        assert request_metrics.params.to_core() == metrics_query
        await harness.peer.send(
            MetricsReadResponse.from_core(
                request_id=request_metrics.id,
                value=metrics_snapshot,
                query=metrics_query,
            ).model_dump_json()
        )
        assert await metrics_call == metrics_snapshot

        await harness.close()

    asyncio.run(scenario())
