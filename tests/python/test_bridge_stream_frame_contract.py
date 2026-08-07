"""Strict bridge diagnostic and metric DTO contract tests."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError
from toqraq.contracts.bridge_diagnostics import (
    DIAGNOSTICS_READ_METHOD,
    DiagnosticsReadRequest,
    DiagnosticsReadResponse,
)
from toqraq.contracts.bridge_metrics import (
    METRICS_READ_METHOD,
    MetricsReadRequest,
    MetricsReadResponse,
)
from toqraq.core.diagnostics import (
    DiagnosticLocation,
    DiagnosticRecord,
    DiagnosticSeverity,
    DiagnosticsPage,
    DiagnosticsQuery,
)
from toqraq.core.metrics import (
    MetricSample,
    MetricsQuery,
    MetricsSnapshot,
    MetricUnavailableReason,
    MetricValueKind,
    UnavailableMetric,
)
from toqraq.core.observation import (
    ObservationCursor,
    ObservationRevision,
    ObservationStamp,
)


def _revision(value: str) -> ObservationRevision:
    return ObservationRevision(value=value)


def _stamp(value: str) -> ObservationStamp:
    return ObservationStamp(
        revision=_revision(value),
        observed_at_unix_ms=1_700_000_000_000,
    )


def _diagnostics_query() -> DiagnosticsQuery:
    return DiagnosticsQuery(
        source_ids=("godot.runtime",),
        severities=(DiagnosticSeverity.WARNING, DiagnosticSeverity.ERROR),
        revision=_revision("diagnostics:7"),
        cursor=ObservationCursor(value="diagnostics:cursor:4"),
        limit=100,
    )


def _diagnostics_page() -> DiagnosticsPage:
    return DiagnosticsPage(
        stamp=_stamp("diagnostics:7"),
        records=(
            DiagnosticRecord(
                sequence=5,
                occurred_at_unix_ms=1_699_999_999_000,
                source_id="godot.runtime",
                severity=DiagnosticSeverity.ERROR,
                code="SCRIPT_ERROR",
                summary="Invalid call in player state",
                details=("Method target no longer exists",),
                location=DiagnosticLocation(
                    resource="res://player.gd",
                    line=42,
                    column=7,
                ),
            ),
        ),
        truncated=False,
        next_cursor=None,
    )


def _metrics_query() -> MetricsQuery:
    return MetricsQuery(
        groups=("toqraq.performance",),
        names=("godot.rendering.draw_calls", "godot.physics.active_bodies"),
        revision=_revision("metrics:6"),
        limit=64,
    )


def _metrics_snapshot() -> MetricsSnapshot:
    return MetricsSnapshot(
        stamp=_stamp("metrics:6"),
        samples=(
            MetricSample(
                name="toqraq.performance.fps",
                kind=MetricValueKind.NUMBER,
                value=59.94,
                unit="toqraq.unit.frames_per_second",
                observed_at_unix_ms=1_700_000_000_000,
            ),
            MetricSample(
                name="godot.rendering.draw_calls",
                kind=MetricValueKind.INTEGER,
                value=128,
                unit="toqraq.unit.count",
                observed_at_unix_ms=1_700_000_000_001,
            ),
        ),
        total_count=3,
        truncated=True,
        unavailable=(
            UnavailableMetric(
                selection_id="godot.physics.active_bodies",
                reason=MetricUnavailableReason.NOT_READY,
            ),
        ),
        collection_duration_microseconds=275,
    )


def test_diagnostics_request_and_response_round_trip_exact_runtime_stream_facts() -> None:
    request = DiagnosticsReadRequest.from_core(
        request_id="host-1",
        query=_diagnostics_query(),
    )
    response = DiagnosticsReadResponse.from_core(
        request_id=request.id,
        value=_diagnostics_page(),
        query=_diagnostics_query(),
    )

    assert request.method == DIAGNOSTICS_READ_METHOD
    assert request.params.to_core() == _diagnostics_query()
    assert (
        DiagnosticsReadRequest.model_validate(request.model_dump(mode="json")).params.to_core()
        == _diagnostics_query()
    )
    assert response.result.to_core(query=_diagnostics_query()) == _diagnostics_page()
    payload = response.model_dump(mode="json")
    assert "kind" not in payload["result"]
    assert "runtime" not in payload["result"]
    assert "returned_count" not in payload["result"]
    assert (
        DiagnosticsReadResponse.model_validate(payload).result.to_core(query=_diagnostics_query())
        == _diagnostics_page()
    )


def test_diagnostics_contract_rejects_stale_cursor_shape_order_and_hidden_fields() -> None:
    request = DiagnosticsReadRequest.from_core(
        request_id="host-1",
        query=_diagnostics_query(),
    ).model_dump(mode="json")
    invalid = deepcopy(request)
    invalid["params"]["revision"] = None
    with pytest.raises(ValidationError, match="requires its revision"):
        DiagnosticsReadRequest.model_validate(invalid)

    invalid = deepcopy(request)
    invalid["params"]["source_ids"] = ["godot.runtime", "godot.runtime"]
    with pytest.raises(ValidationError, match="must be unique"):
        DiagnosticsReadRequest.model_validate(invalid)

    response = DiagnosticsReadResponse.from_core(
        request_id="host-1",
        value=_diagnostics_page(),
        query=_diagnostics_query(),
    ).model_dump(mode="json")
    second = deepcopy(response["result"]["records"][0])
    second["sequence"] = 4
    invalid = deepcopy(response)
    invalid["result"]["records"].append(second)
    with pytest.raises(ValidationError, match="strictly sequenced"):
        DiagnosticsReadResponse.model_validate(invalid)

    invalid = deepcopy(response)
    invalid["result"]["records"][0]["stacktrace"] = "native secret"
    with pytest.raises(ValidationError, match="Extra inputs"):
        DiagnosticsReadResponse.model_validate(invalid)


def test_metrics_request_and_response_round_trip_namespaced_typed_samples() -> None:
    request = MetricsReadRequest.from_core(request_id="host-2", query=_metrics_query())
    response = MetricsReadResponse.from_core(
        request_id=request.id,
        value=_metrics_snapshot(),
        query=_metrics_query(),
    )

    assert request.method == METRICS_READ_METHOD
    assert request.params.to_core() == _metrics_query()
    assert (
        MetricsReadRequest.model_validate(request.model_dump(mode="json")).params.to_core()
        == _metrics_query()
    )
    assert response.result.to_core(query=_metrics_query()) == _metrics_snapshot()
    payload = response.model_dump(mode="json")
    assert "kind" not in payload["result"]
    assert [sample["kind"] for sample in payload["result"]["samples"]] == [
        "number",
        "integer",
    ]
    assert (
        MetricsReadResponse.model_validate(payload).result.to_core(query=_metrics_query())
        == _metrics_snapshot()
    )


def test_metrics_contract_rejects_implicit_selection_bad_types_and_hidden_truncation() -> None:
    request = MetricsReadRequest.from_core(
        request_id="host-2",
        query=_metrics_query(),
    ).model_dump(mode="json")
    invalid = deepcopy(request)
    invalid["params"]["groups"] = []
    invalid["params"]["names"] = []
    with pytest.raises(ValidationError, match="requires a group or name"):
        MetricsReadRequest.model_validate(invalid)

    response = MetricsReadResponse.from_core(
        request_id="host-2",
        value=_metrics_snapshot(),
        query=_metrics_query(),
    ).model_dump(mode="json")
    invalid = deepcopy(response)
    invalid["result"]["samples"][1]["value"] = True
    with pytest.raises(ValidationError):
        MetricsReadResponse.model_validate(invalid)

    invalid = deepcopy(response)
    invalid["result"]["samples"][0]["value"] = float("nan")
    with pytest.raises(ValidationError):
        MetricsReadResponse.model_validate(invalid)

    invalid = deepcopy(response)
    invalid["result"]["truncated"] = False
    with pytest.raises(ValidationError, match="truncation"):
        MetricsReadResponse.model_validate(invalid)
