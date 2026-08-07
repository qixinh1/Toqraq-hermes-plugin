"""Compose the checked OpenAPI graph from public Pydantic contracts."""

from __future__ import annotations

import re
from typing import Any

from fastapi import FastAPI
from toqraq.api import build_router
from toqraq.contracts.bridge import (
    BridgeErrorResponse,
    BridgeHandshakeRequest,
    BridgeHandshakeResponse,
)
from toqraq.contracts.bridge_cancellation import RequestCancelRequest, RequestCancelResponse
from toqraq.contracts.bridge_diagnostics import (
    DiagnosticsReadRequest,
    DiagnosticsReadResponse,
)
from toqraq.contracts.bridge_frame import FrameCaptureRequest, FrameCaptureResponse
from toqraq.contracts.bridge_hierarchy import HierarchyReadRequest, HierarchyReadResponse
from toqraq.contracts.bridge_input import (
    GamepadInputRequest,
    InputAcknowledgementResponse,
    KeyboardInputRequest,
    PointerInputRequest,
    SemanticInputRequest,
    TextInputRequest,
)
from toqraq.contracts.bridge_metrics import MetricsReadRequest, MetricsReadResponse
from toqraq.contracts.bridge_objects import ObjectReadRequest, ObjectReadResponse
from toqraq.contracts.bridge_simulation import (
    SimulationSetPausedRequest,
    SimulationSetPausedResponse,
    SimulationStepRequest,
    SimulationStepResponse,
)
from toqraq.contracts.errors import ErrorEnvelope
from toqraq.contracts.events import SESSION_EVENT_ADAPTER
from toqraq.services.container import build_container
from toqraq.version import PLUGIN_VERSION

SCHEMA_REFERENCE = re.compile(r"^#/components/schemas/([^/]+)$")
SCHEMA_METADATA = frozenset(
    {
        "title",
        "description",
        "default",
        "examples",
        "deprecated",
        "readOnly",
        "writeOnly",
    }
)
NON_HTTP_CONTRACT_MODELS = (
    ErrorEnvelope,
    BridgeHandshakeRequest,
    BridgeHandshakeResponse,
    BridgeErrorResponse,
    HierarchyReadRequest,
    HierarchyReadResponse,
    ObjectReadRequest,
    ObjectReadResponse,
    DiagnosticsReadRequest,
    DiagnosticsReadResponse,
    MetricsReadRequest,
    MetricsReadResponse,
    FrameCaptureRequest,
    FrameCaptureResponse,
    SimulationSetPausedRequest,
    SimulationSetPausedResponse,
    SimulationStepRequest,
    SimulationStepResponse,
    SemanticInputRequest,
    KeyboardInputRequest,
    PointerInputRequest,
    TextInputRequest,
    GamepadInputRequest,
    InputAcknowledgementResponse,
    RequestCancelRequest,
    RequestCancelResponse,
)
NON_HTTP_SCHEMA_ROOTS = {
    "SessionEvent",
    *(model.__name__ for model in NON_HTTP_CONTRACT_MODELS),
}


def build_openapi() -> dict[str, Any]:
    """Compose real routes and merge checked non-HTTP boundary contracts."""
    application = FastAPI(title="Toqraq Plugin API", version=PLUGIN_VERSION)
    application.include_router(build_router(build_container()))
    document = application.openapi()
    remove_unreachable_framework_errors(document)
    add_event_contract(document)
    add_non_http_contracts(document)
    retain_referenced_schemas(document, roots=NON_HTTP_SCHEMA_ROOTS)
    return document


def remove_unreachable_framework_errors(document: dict[str, Any]) -> None:
    """Remove generated 422 responses that the shared route boundary replaces."""
    for path_item in document.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if isinstance(operation, dict):
                responses = operation.get("responses")
                if isinstance(responses, dict):
                    responses.pop("422", None)


def add_event_contract(document: dict[str, Any]) -> None:
    """Merge Pydantic's WebSocket event schema into OpenAPI components."""
    event_schema = SESSION_EVENT_ADAPTER.json_schema(
        mode="serialization",
        ref_template="#/components/schemas/{model}",
    )
    merge_contract_schema(document, name="SessionEvent", schema=event_schema)


def add_non_http_contracts(document: dict[str, Any]) -> None:
    """Merge exact tool/error and engine-process schemas into the artifact."""
    for model in NON_HTTP_CONTRACT_MODELS:
        schema = model.model_json_schema(
            mode="serialization",
            ref_template="#/components/schemas/{model}",
        )
        merge_contract_schema(document, name=model.__name__, schema=schema)


def merge_contract_schema(
    document: dict[str, Any],
    *,
    name: str,
    schema: dict[str, Any],
) -> None:
    """Merge one non-HTTP root and reject conflicting shared definitions."""
    definitions = schema.pop("$defs", {})
    components = document.setdefault("components", {}).setdefault("schemas", {})
    for definition_name, definition_schema in definitions.items():
        existing = components.get(definition_name)
        if existing is not None and not schemas_equivalent(existing, definition_schema):
            raise ValueError(f"conflicting public schema: {definition_name}")
        components[definition_name] = definition_schema
    existing = components.get(name)
    if existing is not None and not schemas_equivalent(existing, schema):
        raise ValueError(f"conflicting public schema: {name}")
    components[name] = schema


def schemas_equivalent(left: object, right: object) -> bool:
    """Compare public JSON shape while ignoring annotation-only metadata."""
    return schema_contract_shape(left) == schema_contract_shape(right)


def schema_contract_shape(value: object) -> object:
    """Recursively remove JSON Schema annotations that cannot alter a value."""
    if isinstance(value, list):
        return [schema_contract_shape(item) for item in value]
    if isinstance(value, dict):
        return {
            key: schema_contract_shape(item)
            for key, item in value.items()
            if key not in SCHEMA_METADATA
        }
    return value


def retain_referenced_schemas(document: dict[str, Any], *, roots: set[str]) -> None:
    """Drop definitions left only by FastAPI's displaced validation response."""
    schemas = document.get("components", {}).get("schemas", {})
    reachable = set(roots)
    pending = list(references(document.get("paths", {}))) + list(roots)
    while pending:
        name = pending.pop()
        if name not in reachable:
            reachable.add(name)
        schema = schemas.get(name)
        if schema is not None:
            pending.extend(references(schema) - reachable)
    document["components"]["schemas"] = {
        name: schema for name, schema in schemas.items() if name in reachable
    }


def references(value: object) -> set[str]:
    """Collect local component references from JSON Schema data."""
    if isinstance(value, list):
        result: set[str] = set()
        for item in value:
            result.update(references(item))
        return result
    if not isinstance(value, dict):
        return set()
    result = set()
    reference = value.get("$ref")
    if isinstance(reference, str) and (match := SCHEMA_REFERENCE.fullmatch(reference)):
        result.add(match.group(1))
    for item in value.values():
        result.update(references(item))
    return result
