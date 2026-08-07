"""Pure diagnostic, metric, and frame-capture read-port invariants."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest
from toqraq.core.diagnostics import (
    DiagnosticLocation,
    DiagnosticRecord,
    DiagnosticSeverity,
    DiagnosticsPage,
    DiagnosticsQuery,
    DiagnosticsReader,
    validate_diagnostics_page,
)
from toqraq.core.frame_capture import (
    MAX_FRAME_CAPTURE_PIXELS,
    FrameCapture,
    FrameCaptureQuery,
    FrameCaptureResult,
    FrameScaling,
    expected_frame_capture_size,
    validate_frame_capture_result,
)
from toqraq.core.geometry import Size
from toqraq.core.metrics import (
    MetricPayload,
    MetricSample,
    MetricsQuery,
    MetricsReader,
    MetricsSnapshot,
    MetricUnavailableReason,
    MetricValueKind,
    UnavailableMetric,
    validate_metrics_snapshot,
)
from toqraq.core.observation import (
    ObservationCursor,
    ObservationRevision,
    ObservationStamp,
)

from _png_support import png_header


def _revision(value: str) -> ObservationRevision:
    return ObservationRevision(value=value)


def _stamp(value: str) -> ObservationStamp:
    return ObservationStamp(revision=_revision(value), observed_at_unix_ms=1_700_000_000_000)


def _diagnostic(sequence: int = 4) -> DiagnosticRecord:
    return DiagnosticRecord(
        sequence=sequence,
        occurred_at_unix_ms=1_700_000_000_000,
        source_id="godot.runtime",
        severity=DiagnosticSeverity.ERROR,
        code="SCRIPT_ERROR",
        summary="Invalid call in player state",
        details=("Method target no longer exists",),
        location=DiagnosticLocation(resource="res://player.gd", line=42, column=7),
    )


def _metric(
    name: str = "toqraq.performance.fps",
    kind: MetricValueKind = MetricValueKind.NUMBER,
    value: MetricPayload = 60.0,
) -> MetricSample:
    return MetricSample(
        name=name,
        kind=kind,
        value=value,
        unit="toqraq.unit.frames_per_second",
        observed_at_unix_ms=1_700_000_000_000,
    )


def _png_header(size: Size) -> bytes:
    return png_header(size.width, size.height)


_DEFAULT_FRAME_SIZE = Size(width=960, height=540)


def _frame_result(size: Size = _DEFAULT_FRAME_SIZE) -> FrameCaptureResult:
    return FrameCaptureResult(
        viewport_size=size,
        captured_at_unix_ms=1_700_000_000_000,
        encoded_size=size,
        frame_revision=_revision("frame:9"),
        data=_png_header(size),
    )


def test_diagnostic_query_pairs_cursor_with_revision_and_bounds_filters() -> None:
    query = DiagnosticsQuery(
        source_ids=("godot.runtime",),
        severities=(DiagnosticSeverity.WARNING, DiagnosticSeverity.ERROR),
        revision=_revision("diagnostics:2"),
        cursor=ObservationCursor(value="diagnostics:cursor:4"),
        limit=50,
    )
    assert query.limit == 50

    with pytest.raises(ValueError, match="requires its revision"):
        replace(query, revision=None)
    with pytest.raises(ValueError, match="source selection"):
        replace(query, source_ids=("godot.runtime", "godot.runtime"))
    with pytest.raises(ValueError, match="severity selection"):
        replace(query, severities=(DiagnosticSeverity.ERROR, DiagnosticSeverity.ERROR))


def test_diagnostic_page_has_exact_order_cursor_and_query_correlation() -> None:
    page = DiagnosticsPage(
        stamp=_stamp("diagnostics:2"),
        records=(_diagnostic(4), _diagnostic(7)),
        truncated=True,
        next_cursor=ObservationCursor(value="diagnostics:cursor:7"),
    )
    assert page.records[-1].sequence == 7

    with pytest.raises(ValueError, match="strictly sequenced"):
        replace(page, records=(_diagnostic(7), _diagnostic(4)))
    with pytest.raises(ValueError, match="truncation"):
        replace(page, next_cursor=None)
    with pytest.raises(ValueError, match="diagnostic sequence"):
        replace(_diagnostic(), sequence=0)

    query = DiagnosticsQuery(
        source_ids=("godot.runtime",),
        severities=(DiagnosticSeverity.ERROR,),
        revision=_revision("diagnostics:2"),
        cursor=None,
        limit=2,
    )
    validate_diagnostics_page(page, query)
    with pytest.raises(ValueError, match="requested limit"):
        validate_diagnostics_page(page, replace(query, limit=1))
    with pytest.raises(ValueError, match="source does not match"):
        validate_diagnostics_page(page, replace(query, source_ids=("godot.editor",)))
    with pytest.raises(ValueError, match="severity does not match"):
        validate_diagnostics_page(page, replace(query, severities=(DiagnosticSeverity.WARNING,)))


def test_metrics_query_requires_explicit_unique_namespaced_selection() -> None:
    query = MetricsQuery(
        groups=("toqraq.performance",),
        names=("godot.rendering.draw_calls",),
        revision=_revision("metrics:4"),
        limit=32,
    )
    assert query.groups == ("toqraq.performance",)

    with pytest.raises(ValueError, match="requires a group or name"):
        replace(query, groups=(), names=())
    with pytest.raises(ValueError, match="groups"):
        replace(query, groups=("toqraq.performance", "toqraq.performance"))
    with pytest.raises(ValueError, match="namespaced"):
        replace(query, names=("fps",))


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        (MetricValueKind.BOOLEAN, True),
        (MetricValueKind.INTEGER, 144),
        (MetricValueKind.NUMBER, 16.67),
    ],
)
def test_metric_samples_are_closed_typed_scalars(
    kind: MetricValueKind,
    value: MetricPayload,
) -> None:
    assert _metric(kind=kind, value=value).kind is kind


def test_metric_samples_and_snapshot_reject_ambiguous_or_hidden_data() -> None:
    with pytest.raises(ValueError, match="integer metric"):
        _metric(kind=MetricValueKind.INTEGER, value=True)
    with pytest.raises(ValueError, match="number metric"):
        _metric(kind=MetricValueKind.NUMBER, value=float("nan"))
    with pytest.raises(ValueError, match="boolean metric"):
        _metric(kind=MetricValueKind.BOOLEAN, value=cast(MetricPayload, "yes"))

    snapshot = MetricsSnapshot(
        stamp=_stamp("metrics:4"),
        samples=(_metric(),),
        total_count=2,
        truncated=True,
        unavailable=(
            UnavailableMetric(
                selection_id="godot.physics.active_bodies",
                reason=MetricUnavailableReason.NOT_READY,
            ),
        ),
        collection_duration_microseconds=240,
    )
    assert snapshot.total_count == 2

    with pytest.raises(ValueError, match="truncation"):
        replace(snapshot, truncated=False)
    with pytest.raises(ValueError, match="sample names"):
        replace(snapshot, samples=(_metric(), _metric()), total_count=2, truncated=False)
    with pytest.raises(ValueError, match="selections must be unique"):
        replace(snapshot, unavailable=(snapshot.unavailable[0], snapshot.unavailable[0]))

    query = MetricsQuery(
        groups=("toqraq.performance",),
        names=("godot.physics.active_bodies",),
        revision=_revision("metrics:4"),
        limit=1,
    )
    validate_metrics_snapshot(snapshot, query)
    with pytest.raises(ValueError, match="requested limit"):
        validate_metrics_snapshot(
            replace(
                snapshot,
                samples=(
                    snapshot.samples[0],
                    _metric(name="toqraq.performance.frame_time"),
                ),
                total_count=2,
                truncated=False,
            ),
            query,
        )
    with pytest.raises(ValueError, match="sample does not match"):
        validate_metrics_snapshot(snapshot, replace(query, groups=("godot.rendering",)))


def test_frame_query_bounds_area_scaling_format_and_bytes_before_capture() -> None:
    query = FrameCaptureQuery(
        maximum_size=Size(width=1_920, height=1_080),
        scaling=FrameScaling.CONTAIN,
        maximum_bytes=8 << 20,
    )
    assert query.maximum_size.width * query.maximum_size.height < MAX_FRAME_CAPTURE_PIXELS

    with pytest.raises(ValueError, match="capture policy"):
        replace(query, maximum_size=Size(width=16_384, height=16_384))
    with pytest.raises(ValueError, match="byte ceiling"):
        replace(query, maximum_bytes=0)


def test_frame_result_contains_only_complete_immutable_png_bytes() -> None:
    result = _frame_result()

    assert result.byte_length == len(result.data)
    assert "data=" not in repr(result)

    with pytest.raises(ValueError, match="immutable bytes"):
        replace(result, data=cast(bytes, bytearray(result.data)))
    with pytest.raises(ValueError, match="not a PNG"):
        replace(result, data=b"not-png")
    with pytest.raises(ValueError, match="IHDR"):
        replace(result, data=result.data[:8] + (12).to_bytes(4, "big") + result.data[12:])
    with pytest.raises(ValueError, match="dimensions"):
        replace(result, encoded_size=Size(width=959, height=540))


def test_frame_scaling_is_exact_integer_contain_without_upscaling() -> None:
    contain = FrameCaptureQuery(
        maximum_size=Size(width=500, height=500),
        scaling=FrameScaling.CONTAIN,
        maximum_bytes=1_024,
    )
    assert expected_frame_capture_size(Size(width=1001, height=500), contain) == Size(
        width=500,
        height=249,
    )
    assert expected_frame_capture_size(Size(width=500, height=1001), contain) == Size(
        width=249,
        height=500,
    )
    assert expected_frame_capture_size(Size(width=320, height=200), contain) == Size(
        width=320,
        height=200,
    )

    native = replace(contain, scaling=FrameScaling.NATIVE)
    with pytest.raises(ValueError, match="does not fit"):
        expected_frame_capture_size(Size(width=501, height=500), native)


def test_frame_result_is_correlated_with_scaling_and_request_bytes() -> None:
    query = FrameCaptureQuery(
        maximum_size=Size(width=500, height=500),
        scaling=FrameScaling.CONTAIN,
        maximum_bytes=1_024,
    )
    encoded = Size(width=500, height=249)
    result = FrameCaptureResult(
        viewport_size=Size(width=1001, height=500),
        captured_at_unix_ms=1_700_000_000_000,
        encoded_size=encoded,
        frame_revision=_revision("frame:9"),
        data=_png_header(encoded),
    )
    validate_frame_capture_result(result, query)

    with pytest.raises(ValueError, match="encoded size"):
        validate_frame_capture_result(replace(result, viewport_size=Size(1000, 500)), query)
    with pytest.raises(ValueError, match="byte ceiling"):
        validate_frame_capture_result(result, replace(query, maximum_bytes=1))


class _DiagnosticsReader:
    async def read(self, query: DiagnosticsQuery) -> DiagnosticsPage:
        return DiagnosticsPage(
            stamp=_stamp("diagnostics:1"),
            records=(),
            truncated=False,
            next_cursor=None,
        )


class _MetricsReader:
    async def read(self, query: MetricsQuery) -> MetricsSnapshot:
        return MetricsSnapshot(
            stamp=_stamp("metrics:1"),
            samples=(),
            total_count=0,
            truncated=False,
            unavailable=(),
            collection_duration_microseconds=0,
        )


class _FrameCapture:
    async def capture(self, query: FrameCaptureQuery) -> FrameCaptureResult:
        return _frame_result()


def test_diagnostics_metrics_and_frame_ports_are_independently_structural() -> None:
    assert isinstance(_DiagnosticsReader(), DiagnosticsReader)
    assert isinstance(_MetricsReader(), MetricsReader)
    assert isinstance(_FrameCapture(), FrameCapture)
