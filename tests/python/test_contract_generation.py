"""Generated public-contract ownership and drift gates."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from scripts import contract_openapi, contract_typescript, generate_contracts


def test_committed_contract_artifacts_match_real_route_composition() -> None:
    artifacts = generate_contracts.render_artifacts()

    assert artifacts == {path: path.read_bytes() for path in artifacts}
    document = json.loads(artifacts[generate_contracts.OPENAPI_PATH])
    assert "/sessions" in document["paths"]
    assert "/preview/native/attach" in document["paths"]
    assert "/components" in document["paths"]
    assert "/component-jobs" in document["paths"]
    assert "/component-jobs/active" in document["paths"]
    assert "SessionEvent" in document["components"]["schemas"]
    assert "BridgeHandshakeRequest" in document["components"]["schemas"]
    assert "BridgeHandshakeResponse" in document["components"]["schemas"]
    assert "BridgeErrorResponse" in document["components"]["schemas"]
    for name in (
        "HierarchyReadRequest",
        "HierarchyReadResponse",
        "ObjectReadRequest",
        "ObjectReadResponse",
        "DiagnosticsReadRequest",
        "DiagnosticsReadResponse",
        "MetricsReadRequest",
        "MetricsReadResponse",
        "FrameCaptureRequest",
        "FrameCaptureResponse",
        "SimulationSetPausedRequest",
        "SimulationSetPausedResponse",
        "SimulationStepRequest",
        "SimulationStepResponse",
        "SemanticInputRequest",
        "KeyboardInputRequest",
        "PointerInputRequest",
        "TextInputRequest",
        "GamepadInputRequest",
        "InputAcknowledgementResponse",
        "RequestCancelRequest",
        "RequestCancelResponse",
    ):
        assert name in document["components"]["schemas"]
    assert set(document["components"]["schemas"]["FrameTransferValue"]["properties"]) == {
        "transfer_id",
        "mime_type",
        "size",
        "byte_length",
        "sha256",
        "frame_revision",
    }
    assert "ComponentJobResult" in document["components"]["schemas"]
    assert "ComponentActiveJobsResult" in document["components"]["schemas"]
    assert all(
        "422" not in operation.get("responses", {})
        for path_item in document["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict)
    )


def test_generated_desktop_types_are_deep_readonly_and_never_escape_typing() -> None:
    source = generate_contracts.TYPES_PATH.read_text(encoding="utf-8")

    assert "ReadonlyArray<" in source
    assert 'readonly "payload"' in source
    assert 'readonly "run_revision": number' in source
    assert 'readonly "runtime": RuntimeIdentityResult' in source
    assert 'readonly "process_state": SessionProcessState' in source
    assert 'readonly "preview": PreviewReadinessResult' in source
    assert 'readonly "perception": FeatureReadinessResult' in source
    assert 'readonly "control": FeatureReadinessResult' in source
    assert 'readonly "exit_code":' in source
    assert 'readonly "exit_code"?:' not in source
    assert "export type BridgeHandshakeRequest" in source
    assert "export type BridgeHandshakeResponse" in source
    assert "export type BridgeErrorResponse" in source
    assert "export type HierarchyReadRequest" in source
    assert "export type ObjectReadResponse" in source
    assert "export type DiagnosticsReadResponse" in source
    assert "export type MetricsReadResponse" in source
    assert "export type FrameCaptureResponse" in source
    assert "export type SimulationSetPausedRequest" in source
    assert "export type SimulationStepResponse" in source
    assert "export type SemanticInputRequest" in source
    assert "export type PointerInputRequest" in source
    assert "export type GamepadInputRequest" in source
    assert "export type InputAcknowledgementResponse" in source
    assert "export type RequestCancelResponse" in source
    assert 'readonly "transfer_id": string' in source
    assert '"session.started"' in source
    assert '"session.readiness"' in source
    assert '"session.process_state"' in source
    assert '"session.stopped"' in source
    assert '"session.failed"' in source
    assert " any" not in source
    assert " unknown" not in source


def test_generated_runtime_rules_are_focused_exact_schema_facts() -> None:
    source = generate_contracts.RUNTIME_RULES_PATH.read_text(encoding="utf-8")
    exports = set(re.findall(r"^export const (\w+)Rules =", source, flags=re.MULTILINE))

    assert exports == contract_typescript.DESKTOP_RUNTIME_RULE_SCHEMAS
    assert len(source.splitlines()) <= 500
    assert "SetupResultRules" in source
    assert '"action": Object.freeze({ values:' in source
    assert "\"engine_choices\": Object.freeze({ kind: 'array', maximumItems: 16" in source
    assert "PublicErrorRules" in source
    assert "\"trace_id\": Object.freeze({ kind: 'string', minimumLength: 36" in source
    assert 'errorJson: Object.freeze({"maximumDepth": 4' in source
    assert "new RegExp" in source
    assert "from " not in source

    document = json.loads(generate_contracts.OPENAPI_PATH.read_bytes())
    public_error = document["components"]["schemas"]["PublicError"]
    assert public_error["properties"]["trace_id"] == {
        "maxLength": 36,
        "minLength": 36,
        "pattern": ("^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"),
        "title": "Trace Id",
        "type": "string",
    }
    assert public_error["x-toqraq-error-json"]["maximumNodes"] == 128


def test_atomic_writer_replaces_complete_content(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "contract.json"
    target.parent.mkdir()
    target.write_bytes(b"old")

    generate_contracts.write_atomic(target, b"new contract\n")

    assert target.read_bytes() == b"new contract\n"
    assert list(target.parent.iterdir()) == [target]


def test_generator_rejects_schema_semantics_it_cannot_preserve() -> None:
    with pytest.raises(ValueError, match="unsupported string schema keywords: not"):
        contract_typescript.schema_type(
            {"type": "string", "not": {"const": "unsafe"}},
            0,
        )


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "array", "items": {"type": "boolean"}},
        {"type": "string", "maxLength": 10, "format": "uuid"},
        {"type": "integer", "minimum": 0},
        {"type": "number", "minimum": 0, "maximum": 1, "multipleOf": 0.1},
    ],
)
def test_runtime_rule_generation_rejects_unbounded_or_uninterpreted_facts(
    schema: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        contract_typescript.runtime_rule(schema, {})


def test_event_schema_merge_rejects_a_conflicting_route_definition() -> None:
    document = {"components": {"schemas": {"SessionResult": {"type": "string"}}}}

    with pytest.raises(ValueError, match="conflicting public schema: SessionResult"):
        contract_openapi.add_event_contract(document)


def test_schema_merge_accepts_only_annotation_metadata_differences() -> None:
    left = {
        "type": "object",
        "properties": {
            "error": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
            }
        },
    }
    right = {
        "title": "Annotated",
        "type": "object",
        "properties": {
            "error": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "default": None,
                "description": "Annotation-only difference.",
            }
        },
    }

    assert contract_openapi.schemas_equivalent(left, right)
    right["properties"]["error"]["anyOf"] = [{"type": "integer"}, {"type": "null"}]
    assert not contract_openapi.schemas_equivalent(left, right)
