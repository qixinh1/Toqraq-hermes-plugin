"""Generated Hermes tool-schema contract tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from toqraq.contracts.bridge_diagnostics import DiagnosticsReadResult
from toqraq.contracts.bridge_hierarchy import HierarchyReadResult
from toqraq.contracts.bridge_input import InputAcknowledgementValue
from toqraq.contracts.bridge_metrics import MetricsReadResult
from toqraq.contracts.bridge_objects import ObjectReadResult
from toqraq.contracts.frame_capture import FrameCaptureResult
from toqraq.contracts.process_output import ProcessOutputResult
from toqraq.contracts.project_inventory import ProjectInventoryResult
from toqraq.contracts.sessions import SessionResult
from toqraq.contracts.setup import SetupResult
from toqraq.hermes.tools import TOOL_SPECS, build_tools
from toqraq.services.container import build_container

EXPECTED_RESULT_MODELS = (
    SetupResult,
    ProjectInventoryResult,
    SessionResult,
    SessionResult,
    SessionResult,
    SessionResult,
    SessionResult,
    HierarchyReadResult,
    ObjectReadResult,
    DiagnosticsReadResult,
    ProcessOutputResult,
    MetricsReadResult,
    FrameCaptureResult,
    InputAcknowledgementValue,
    InputAcknowledgementValue,
    InputAcknowledgementValue,
    InputAcknowledgementValue,
    InputAcknowledgementValue,
)
HOST_OWNED_FIELDS = {"hermes_session", "session", "session_id", "task_id"}
PLUGIN_MANIFEST = Path(__file__).parents[2] / "plugin.yaml"


def _tools():
    """Build registrations over one isolated service graph."""
    return build_tools(build_container())


def test_tool_names_are_unique_namespaced_and_complete() -> None:
    tools = _tools()
    names = tuple(tool.name for tool in tools)
    assert names == tuple(spec.name for spec in TOOL_SPECS)
    assert len(set(names)) == len(names)
    assert all(name.startswith("toqraq_") for name in names)


def test_every_tool_declares_its_exact_success_result_contract() -> None:
    assert tuple(tool.result_model for tool in _tools()) == EXPECTED_RESULT_MODELS


def test_manifest_declares_the_exact_generated_tool_order() -> None:
    manifest = yaml.safe_load(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
    assert tuple(manifest["provides_tools"]) == tuple(spec.name for spec in TOOL_SPECS)


def test_every_parameter_schema_is_generated_from_its_request_model() -> None:
    for tool in _tools():
        assert tool.schema == {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.request_model.model_json_schema(),
        }
        assert tool.schema["parameters"]["additionalProperties"] is False


def test_every_nested_input_event_schema_rejects_unknown_fields() -> None:
    input_tools = [tool for tool in _tools() if "_input_" in tool.name]
    assert len(input_tools) == 5
    for tool in input_tools:
        schema = tool.schema["parameters"]
        definitions: dict[str, Any] = schema.get("$defs", {})
        object_definitions = [
            definition for definition in definitions.values() if definition.get("type") == "object"
        ]
        assert all(
            definition.get("additionalProperties") is False for definition in object_definitions
        )


def test_game_owner_is_never_model_selectable() -> None:
    for tool in _tools():
        properties = set(tool.schema["parameters"].get("properties", {}))
        if tool.name.startswith("toqraq_game_"):
            assert HOST_OWNED_FIELDS.isdisjoint(properties)


def test_project_inventory_owner_and_project_are_never_model_selectable() -> None:
    inventory = next(tool for tool in _tools() if tool.name == "toqraq_project_read_inventory")
    properties = set(inventory.schema["parameters"].get("properties", {}))

    assert HOST_OWNED_FIELDS.isdisjoint(properties)
    assert {"project_dir", "engine", "version"}.isdisjoint(properties)


def test_setup_and_start_expose_only_current_selection_inputs() -> None:
    tools = {tool.name: tool for tool in _tools()}
    setup = tools["toqraq_project_setup"].schema["parameters"]["properties"]
    start = tools["toqraq_game_start"].schema["parameters"]["properties"]
    assert set(setup) == {"project_dir", "engine", "version"}
    assert set(start) == {"project_dir", "engine", "version"}
