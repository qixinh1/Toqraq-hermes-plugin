"""Minimal exact Core values shared by focused Bridge adapter tests."""

from __future__ import annotations

from toqraq.core.diagnostics import DiagnosticsPage, DiagnosticsQuery
from toqraq.core.frame_capture import FrameCaptureQuery, FrameCaptureResult, FrameScaling
from toqraq.core.geometry import Size
from toqraq.core.hierarchy import HierarchyPage, HierarchyQuery
from toqraq.core.input_control import (
    GamepadInputCommand,
    KeyboardInputCommand,
    PointerInputCommand,
    SemanticInputCommand,
    TextInputCommand,
)
from toqraq.core.metrics import MetricSample, MetricsQuery, MetricsSnapshot, MetricValueKind
from toqraq.core.object_inspection import (
    ObjectExtensionGroup,
    ObjectFieldGroup,
    ObjectReadQuery,
    ObjectSnapshot,
    RuntimeObject,
)
from toqraq.core.observation import ObservationRevision, ObservationStamp, RunObjectReference
from toqraq.core.player_input import (
    GamepadAxis,
    GamepadAxisEvent,
    KeyboardInputEvent,
    KeyboardLocation,
    PointerCoordinateSpace,
    PointerKind,
    PointerMoveEvent,
    SemanticInputEvent,
)

from _png_support import png_header


def revision(value: str) -> ObservationRevision:
    return ObservationRevision(value=value)


def stamp(value: str) -> ObservationStamp:
    return ObservationStamp(
        revision=revision(value),
        observed_at_unix_ms=1_700_000_000_000,
    )


def hierarchy_values() -> tuple[HierarchyQuery, HierarchyPage]:
    query = HierarchyQuery(
        root=None,
        depth=1,
        name_contains=None,
        native_types=(),
        revision=None,
        cursor=None,
        limit=1,
    )
    return query, HierarchyPage(
        stamp=stamp("hierarchy:1"),
        entries=(),
        truncated=False,
        next_cursor=None,
    )


def object_values() -> tuple[ObjectReadQuery, ObjectSnapshot]:
    reference = RunObjectReference(value="node:player")
    fields = (ObjectFieldGroup.EXTENSIONS,)
    query = ObjectReadQuery(
        references=(reference,),
        fields=fields,
        revision=None,
        per_value_max_bytes=64,
        total_value_max_bytes=64,
    )
    value = RuntimeObject(
        reference=reference,
        display_name="Player",
        native_type="Node",
        properties=None,
        components=None,
        resources=None,
        extensions=ObjectExtensionGroup(
            total_count=0,
            items=(),
            truncated=False,
        ),
    )
    return query, ObjectSnapshot(
        stamp=stamp("objects:1"),
        fields=fields,
        objects=(value,),
        value_bytes=0,
    )


def diagnostics_values() -> tuple[DiagnosticsQuery, DiagnosticsPage]:
    query = DiagnosticsQuery(
        source_ids=(),
        severities=(),
        revision=None,
        cursor=None,
        limit=1,
    )
    return query, DiagnosticsPage(
        stamp=stamp("diagnostics:1"),
        records=(),
        truncated=False,
        next_cursor=None,
    )


def metrics_values() -> tuple[MetricsQuery, MetricsSnapshot]:
    metric_name = "toqraq.performance.fps"
    query = MetricsQuery(
        groups=(),
        names=(metric_name,),
        revision=None,
        limit=1,
    )
    return query, MetricsSnapshot(
        stamp=stamp("metrics:1"),
        samples=(
            MetricSample(
                name=metric_name,
                kind=MetricValueKind.NUMBER,
                value=60.0,
                unit="toqraq.unit.frames_per_second",
                observed_at_unix_ms=1_700_000_000_000,
            ),
        ),
        total_count=1,
        truncated=False,
        unavailable=(),
        collection_duration_microseconds=1,
    )


def input_commands() -> tuple[
    SemanticInputCommand,
    KeyboardInputCommand,
    PointerInputCommand,
    TextInputCommand,
    GamepadInputCommand,
]:
    return (
        SemanticInputCommand(
            events=(SemanticInputEvent(action="player.jump", pressed=True, strength=1.0),),
        ),
        KeyboardInputCommand(
            events=(
                KeyboardInputEvent(
                    physical_code="KeyW",
                    logical_key="w",
                    location=KeyboardLocation.STANDARD,
                    modifiers=(),
                    pressed=True,
                    repeated=False,
                ),
            ),
        ),
        PointerInputCommand(
            pointer_id=0,
            pointer_kind=PointerKind.MOUSE,
            coordinate_space=PointerCoordinateSpace.VIEWPORT_NORMALIZED,
            events=(PointerMoveEvent(x=0.5, y=0.5, delta_x=0.0, delta_y=0.0),),
        ),
        TextInputCommand(text="hello"),
        GamepadInputCommand(
            device_slot=0,
            events=(GamepadAxisEvent(axis=GamepadAxis.LEFT_X, value=0.5),),
        ),
    )


def frame_values(*, padding_bytes: int = 0) -> tuple[FrameCaptureQuery, FrameCaptureResult]:
    size = Size(width=1, height=1)
    data = png_header(size.width, size.height, padding_bytes=padding_bytes)
    query = FrameCaptureQuery(
        maximum_size=size,
        scaling=FrameScaling.CONTAIN,
        maximum_bytes=len(data),
    )
    return query, FrameCaptureResult(
        viewport_size=size,
        captured_at_unix_ms=1_700_000_000_000,
        encoded_size=size,
        frame_revision=revision("frame:1"),
        data=data,
    )
