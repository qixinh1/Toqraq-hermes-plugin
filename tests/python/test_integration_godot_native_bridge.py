"""Real-process conformance for the Godot native common Bridge baseline."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path

import pytest
from scripts.verify_godot_candidate import verify_godot_candidate
from toqraq.bridge.bridge_feature_connection import BridgeRuntimeFeatureConnectionFactory
from toqraq.components.release import ComponentIdentity
from toqraq.core.bridge import (
    COMMON_BRIDGE_LIMITS,
    BridgeHandshakeExpectation,
    BridgeOwnerKey,
)
from toqraq.core.capability_ids import (
    MANDATORY_BRIDGE_CAPABILITY_IDS,
    MANDATORY_ENGINE_CAPABILITY_IDS,
)
from toqraq.core.diagnostics import DiagnosticsQuery
from toqraq.core.frame_capture import FrameCaptureQuery, FrameScaling
from toqraq.core.geometry import Size
from toqraq.core.hierarchy import HierarchyQuery
from toqraq.core.input_control import (
    GamepadInputCommand,
    KeyboardInputCommand,
    PointerInputCommand,
    SemanticInputCommand,
    TextInputCommand,
)
from toqraq.core.metrics import MetricsQuery
from toqraq.core.object_inspection import ObjectFieldGroup, ObjectReadQuery
from toqraq.core.observation import RunObjectReference
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
from toqraq.core.runtime import RuntimeEntryPointBinding, RuntimeIdentity, RuntimeRelease
from toqraq.core.runtime_features import RuntimeFeatureConnection, RuntimeFeaturePorts
from toqraq.core.simulation_control import SetPausedCommand, StepFramesCommand
from toqraq.engines.godot.identity import (
    GODOT_BRIDGE_ID,
    GODOT_BRIDGE_PROTOCOL,
    GODOT_EDITOR_ENTRY_POINT,
    GODOT_ENGINE_ID,
    GODOT_RUNTIME_DISTRIBUTION_ID,
)
from toqraq.engines.godot.launch_planner import GODOT_BRIDGE_URL_ENVIRONMENT
from toqraq.platforms.windows.child_environment import windows_managed_child_environment

pytestmark = pytest.mark.integration

_CANDIDATE_ENVIRONMENT = "TOQRAQ_GODOT_CANDIDATE_DIR"
_CANDIDATE_VALUE = os.environ.get(_CANDIDATE_ENVIRONMENT)
_CANDIDATE = Path(_CANDIDATE_VALUE) if _CANDIDATE_VALUE else None
_PROJECT_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "godot_project"
_CREDENTIAL = "c" * 64
_SESSION_ID = "native-bridge-integration"
_RUN_REVISION = 1
_TIMEOUT_SECONDS = 30.0

if _CANDIDATE is None or not _CANDIDATE.is_dir():
    pytest.skip(
        f"{_CANDIDATE_ENVIRONMENT} is not set to a generated candidate directory",
        allow_module_level=True,
    )


def _expectation(component: ComponentIdentity) -> BridgeHandshakeExpectation:
    release_id = component.package_sha256
    release = RuntimeRelease(
        identity=RuntimeIdentity(
            engine_id=GODOT_ENGINE_ID,
            version=component.version,
            build_id=component.build_id,
            distribution_id=GODOT_RUNTIME_DISTRIBUTION_ID,
            platform=component.platform,
            architecture=component.architecture,
        ),
        component_release_ids=(release_id,),
        entry_point_bindings=(
            RuntimeEntryPointBinding(
                name=GODOT_EDITOR_ENTRY_POINT,
                component_release_id=release_id,
                component_entry_point_name=GODOT_EDITOR_ENTRY_POINT,
            ),
        ),
        bridge_id=GODOT_BRIDGE_ID,
        bridge_protocol=GODOT_BRIDGE_PROTOCOL,
        capability_ids=frozenset(MANDATORY_ENGINE_CAPABILITY_IDS),
        bridge_capability_ids=frozenset(MANDATORY_BRIDGE_CAPABILITY_IDS),
    )
    return BridgeHandshakeExpectation(
        credential=_CREDENTIAL,
        owner=BridgeOwnerKey(session_id=_SESSION_ID, run_revision=_RUN_REVISION),
        release=release,
        limits=COMMON_BRIDGE_LIMITS,
    )


async def _collect_output(reader: asyncio.StreamReader, lines: list[str]) -> None:
    while data := await reader.readline():
        lines.append(data.decode("utf-8", errors="replace").rstrip())
        del lines[:-200]


async def _launch(
    connection: RuntimeFeatureConnection,
    executable: Path,
    project: Path,
    managed_root: Path,
) -> tuple[asyncio.subprocess.Process, asyncio.Task[None], list[str]]:
    environment = {
        variable.name: variable.value
        for variable in windows_managed_child_environment(managed_root).variables
    }
    environment[GODOT_BRIDGE_URL_ENVIRONMENT] = connection.endpoint.url
    process = await asyncio.create_subprocess_exec(
        str(executable),
        "--path",
        str(project),
        cwd=project,
        env=environment,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if process.stdin is None or process.stdout is None:
        raise AssertionError("Godot process pipes were not created")
    output: list[str] = []
    collector = asyncio.create_task(_collect_output(process.stdout, output))
    process.stdin.write(
        json.dumps(
            {
                "credential": _CREDENTIAL,
                "session_id": _SESSION_ID,
                "run_revision": _RUN_REVISION,
            },
            separators=(",", ":"),
        ).encode("utf-8")
    )
    await process.stdin.drain()
    process.stdin.close()
    await process.stdin.wait_closed()
    return process, collector, output


async def _wait_ready(
    connection: RuntimeFeatureConnection,
    process: asyncio.subprocess.Process,
    output: list[str],
) -> RuntimeFeaturePorts:
    ready = asyncio.create_task(connection.wait_ready())
    exited = asyncio.create_task(process.wait())
    done, _pending = await asyncio.wait(
        (ready, exited),
        timeout=_TIMEOUT_SECONDS,
        return_when=asyncio.FIRST_COMPLETED,
    )
    if ready in done:
        exited.cancel()
        await asyncio.gather(exited, return_exceptions=True)
        return ready.result()
    ready.cancel()
    await asyncio.gather(ready, return_exceptions=True)
    if exited in done:
        raise AssertionError(
            f"Godot exited before bridge readiness: {process.returncode}; {output}"
        )
    exited.cancel()
    await asyncio.gather(exited, return_exceptions=True)
    raise AssertionError(f"Godot bridge did not become ready: {output}")


async def _stop_process(
    process: asyncio.subprocess.Process,
    collector: asyncio.Task[None],
) -> None:
    if process.returncode is None:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except TimeoutError:
            process.kill()
            await process.wait()
    await collector


async def _property_integer(
    features: RuntimeFeaturePorts,
    reference: RunObjectReference,
    name: str,
) -> int:
    snapshot = await features.objects.read(
        ObjectReadQuery(
            references=(reference,),
            fields=(ObjectFieldGroup.PROPERTIES,),
            revision=None,
            per_value_max_bytes=1024,
            total_value_max_bytes=16_384,
        )
    )
    properties = snapshot.objects[0].properties
    assert properties is not None
    values = {item.name: item.value.value for item in properties.items}
    value = values[name]
    assert isinstance(value, int) and not isinstance(value, bool)
    return value


async def _exercise(features: RuntimeFeaturePorts) -> None:
    hierarchy = await features.hierarchy.read(
        HierarchyQuery(
            root=None,
            depth=4,
            name_contains=None,
            native_types=(),
            revision=None,
            cursor=None,
            limit=64,
        )
    )
    main = next(entry for entry in hierarchy.entries if entry.display_name == "Main")
    text_input = next(entry for entry in hierarchy.entries if entry.display_name == "TextInput")
    assert main.native_type == "Node2D"

    assert await _property_integer(features, main.reference, "semantic_input_count") == 0

    diagnostics = await features.diagnostics.read(
        DiagnosticsQuery(
            source_ids=(),
            severities=(),
            revision=None,
            cursor=None,
            limit=32,
        )
    )
    assert any(record.code == "toqraq.bridge.ready" for record in diagnostics.records)
    assert any("Toqraq fixture ready" in record.summary for record in diagnostics.records)

    metrics = await features.metrics.read(
        MetricsQuery(
            groups=("toqraq.performance",),
            names=(),
            revision=None,
            limit=8,
        )
    )
    assert {sample.name for sample in metrics.samples} >= {"toqraq.performance.fps"}

    paused = await features.simulation.set_paused(SetPausedCommand(paused=True))
    assert paused.paused
    stepped = await features.simulation.step(StepFramesCommand(frame_count=2))
    assert stepped.frame_count == 2 and stepped.paused
    resumed = await features.simulation.set_paused(SetPausedCommand(paused=False))
    assert not resumed.paused

    acknowledgement = await features.input.semantic(
        SemanticInputCommand(
            events=(SemanticInputEvent(action="toqraq_test", pressed=True, strength=1.0),),
        )
    )
    assert acknowledgement.accepted_event_count == 1
    assert await _property_integer(features, main.reference, "semantic_input_count") == 1

    keyboard_before = await _property_integer(features, main.reference, "keyboard_input_count")
    keyboard = await features.input.keyboard(
        KeyboardInputCommand(
            events=(
                KeyboardInputEvent(
                    physical_code="KeyA",
                    logical_key="a",
                    location=KeyboardLocation.STANDARD,
                    modifiers=(),
                    pressed=True,
                    repeated=False,
                ),
            )
        )
    )
    assert keyboard.accepted_event_count == 1
    assert (
        await _property_integer(features, main.reference, "keyboard_input_count") > keyboard_before
    )

    pointer_before = await _property_integer(features, main.reference, "pointer_input_count")
    pointer = await features.input.pointer(
        PointerInputCommand(
            pointer_id=0,
            pointer_kind=PointerKind.MOUSE,
            coordinate_space=PointerCoordinateSpace.VIEWPORT_NORMALIZED,
            events=(PointerMoveEvent(x=0.5, y=0.5, delta_x=0.0, delta_y=0.0),),
        )
    )
    assert pointer.accepted_event_count == 1
    assert await _property_integer(features, main.reference, "pointer_input_count") > pointer_before

    text = await features.input.text(TextInputCommand(text="Hermes"))
    assert text.accepted_event_count == 1
    text_snapshot = await features.objects.read(
        ObjectReadQuery(
            references=(text_input.reference,),
            fields=(ObjectFieldGroup.PROPERTIES,),
            revision=None,
            per_value_max_bytes=1024,
            total_value_max_bytes=16_384,
        )
    )
    text_properties = text_snapshot.objects[0].properties
    assert text_properties is not None
    text_values = {item.name: item.value.value for item in text_properties.items}
    assert text_values["text"] == "Hermes"

    gamepad_before = await _property_integer(features, main.reference, "gamepad_input_count")
    gamepad = await features.input.gamepad(
        GamepadInputCommand(
            device_slot=0,
            events=(GamepadAxisEvent(axis=GamepadAxis.LEFT_X, value=0.5),),
        )
    )
    assert gamepad.accepted_event_count == 1
    assert await _property_integer(features, main.reference, "gamepad_input_count") > gamepad_before

    frame = await features.frame.capture(
        FrameCaptureQuery(
            maximum_size=Size(width=480, height=270),
            scaling=FrameScaling.CONTAIN,
            maximum_bytes=4 * 1024 * 1024,
        )
    )
    assert frame.viewport_size == Size(width=960, height=540)
    assert frame.encoded_size == Size(width=480, height=270)
    assert frame.data.startswith(b"\x89PNG\r\n\x1a\n")
    assert frame.byte_length > 1024


def test_native_bridge_real_process_common_feature_loop(tmp_path: Path) -> None:
    extraction = tmp_path / "component"
    extraction.mkdir()
    assert _CANDIDATE is not None
    candidate = verify_godot_candidate(_CANDIDATE, extraction)
    project = shutil.copytree(_PROJECT_FIXTURE, tmp_path / "project")
    managed_root = tmp_path / "hermes-home" / "toqraq"

    async def scenario() -> None:
        connection = await BridgeRuntimeFeatureConnectionFactory().open(
            _expectation(candidate.identity)
        )
        process, collector, output = await _launch(
            connection,
            candidate.executable,
            project,
            managed_root,
        )
        try:
            features = await _wait_ready(connection, process, output)
            async with asyncio.timeout(_TIMEOUT_SECONDS):
                await _exercise(features)
            assert (managed_root / "appdata").is_dir()
        except Exception as exc:
            details = getattr(exc, "details", None)
            raise AssertionError(
                f"native bridge flow failed: {type(exc).__name__}; {details}; {output}"
            ) from exc
        finally:
            await connection.close()
            await _stop_process(process, collector)

    asyncio.run(scenario())
