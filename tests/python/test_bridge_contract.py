"""Pure common bridge handshake, JSON-RPC, and bound tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from typing import cast

import pytest
from pydantic import ValidationError
from toqraq.contracts.bridge import (
    BRIDGE_HANDSHAKE_METHOD,
    BridgeErrorResponse,
    BridgeHandshakeRequest,
    BridgeHandshakeResponse,
    bridge_error_response,
)
from toqraq.contracts.bridge_codec import decode_handshake_request
from toqraq.core.bridge import (
    MAX_BRIDGE_BINARY_TRANSFER_BYTES,
    MAX_BRIDGE_RUN_REVISION,
    MAX_BRIDGE_TEXT_MESSAGE_BYTES,
    MIN_BRIDGE_TEXT_MESSAGE_BYTES,
    BridgeHandshakeExpectation,
    BridgeHandshakeOffer,
    BridgeLimits,
    BridgeOwnerKey,
    validate_bridge_credential,
    validate_bridge_handshake,
    validate_bridge_run_revision,
    validate_bridge_session_id,
)
from toqraq.core.bridge_errors import (
    BRIDGE_WIRE_ERROR_TYPES,
    BridgeCredentialMismatchError,
    BridgeHandshakeField,
    BridgeHandshakeMismatchError,
    BridgeJsonInvalidError,
    BridgeMessageTooLargeError,
    BridgeMethodNotFoundError,
    BridgeParamsInvalidError,
    BridgeRequestInvalidError,
    BridgeWireError,
)
from toqraq.core.capability_ids import (
    MANDATORY_BRIDGE_CAPABILITY_IDS,
    MANDATORY_ENGINE_CAPABILITY_IDS,
)
from toqraq.core.errors import ErrorCategory
from toqraq.core.runtime import (
    RuntimeEntryPointBinding,
    RuntimeIdentity,
    RuntimeRelease,
)

_CREDENTIAL = "a" * 64
_SESSION_ID = "session-42"
_CAPABILITIES = MANDATORY_ENGINE_CAPABILITY_IDS | frozenset({"godot.observe.physics"})
_BRIDGE_CAPABILITIES = MANDATORY_BRIDGE_CAPABILITY_IDS | frozenset({"godot.observe.physics"})


def _identity() -> RuntimeIdentity:
    """Build one exact certified runtime identity."""
    return RuntimeIdentity(
        engine_id="godot",
        version="4.7.1",
        build_id="toqraq.1",
        distribution_id="toqraq",
        platform="windows",
        architecture="x86_64",
    )


def _release(
    *,
    capabilities: frozenset[str] = _CAPABILITIES,
    bridge_capabilities: frozenset[str] = _BRIDGE_CAPABILITIES,
) -> RuntimeRelease:
    """Build one release suitable for an authenticated listener."""
    component_id = "1" * 64
    return RuntimeRelease(
        identity=_identity(),
        component_release_ids=(component_id,),
        entry_point_bindings=(
            RuntimeEntryPointBinding(
                name="editor",
                component_release_id=component_id,
                component_entry_point_name="editor",
            ),
        ),
        bridge_id="toqraq.godot.bridge",
        bridge_protocol="1.0",
        capability_ids=capabilities,
        bridge_capability_ids=bridge_capabilities,
    )


def _host_limits() -> BridgeLimits:
    """Build the listener policy used by the fixture."""
    return BridgeLimits(
        max_text_message_bytes=MAX_BRIDGE_TEXT_MESSAGE_BYTES,
        max_binary_transfer_bytes=32 << 20,
        max_in_flight_requests=16,
    )


def _peer_limits() -> BridgeLimits:
    """Build a valid peer declaration with independently stricter fields."""
    return BridgeLimits(
        max_text_message_bytes=128 << 10,
        max_binary_transfer_bytes=MAX_BRIDGE_BINARY_TRANSFER_BYTES,
        max_in_flight_requests=8,
    )


def _expectation() -> BridgeHandshakeExpectation:
    """Build immutable launch facts owned by one listener."""
    return BridgeHandshakeExpectation(
        credential=_CREDENTIAL,
        owner=BridgeOwnerKey(session_id=_SESSION_ID, run_revision=7),
        release=_release(),
        limits=_host_limits(),
    )


def _offer() -> BridgeHandshakeOffer:
    """Build the matching peer identity."""
    return BridgeHandshakeOffer(
        credential=_CREDENTIAL,
        owner=BridgeOwnerKey(session_id=_SESSION_ID, run_revision=7),
        runtime_identity=_identity(),
        bridge_id="toqraq.godot.bridge",
        protocol="1.0",
        capability_ids=_BRIDGE_CAPABILITIES,
        limits=_peer_limits(),
    )


def _payload() -> dict[str, object]:
    """Build the complete first JSON-RPC message."""
    return {
        "jsonrpc": "2.0",
        "id": "handshake:7",
        "method": BRIDGE_HANDSHAKE_METHOD,
        "params": {
            "credential": _CREDENTIAL,
            "session_id": _SESSION_ID,
            "run_revision": 7,
            "engine_id": "godot",
            "engine_version": "4.7.1",
            "build_id": "toqraq.1",
            "distribution_id": "toqraq",
            "platform": "windows",
            "architecture": "x86_64",
            "bridge_id": "toqraq.godot.bridge",
            "protocol": "1.0",
            "capabilities": sorted(_BRIDGE_CAPABILITIES),
            "limits": {
                "max_text_message_bytes": 128 << 10,
                "max_binary_transfer_bytes": MAX_BRIDGE_BINARY_TRANSFER_BYTES,
                "max_in_flight_requests": 8,
            },
        },
    }


def test_exact_handshake_returns_only_owner_protocol_capabilities_and_effective_limits() -> None:
    accepted = validate_bridge_handshake(_offer(), _expectation())

    assert accepted.owner == BridgeOwnerKey(session_id=_SESSION_ID, run_revision=7)
    assert accepted.protocol == "1.0"
    assert accepted.capability_ids == _BRIDGE_CAPABILITIES
    assert accepted.limits == BridgeLimits(
        max_text_message_bytes=128 << 10,
        max_binary_transfer_bytes=32 << 20,
        max_in_flight_requests=8,
    )

    request = decode_handshake_request(json.dumps(_payload()))
    response = BridgeHandshakeResponse.from_core(request_id=request.id, value=accepted)
    body = response.model_dump(mode="json")
    assert body["id"] == "handshake:7"
    assert body["result"] == {
        "owner": {"session_id": _SESSION_ID, "run_revision": 7},
        "protocol": "1.0",
        "capabilities": sorted(_BRIDGE_CAPABILITIES),
        "limits": {
            "max_text_message_bytes": 128 << 10,
            "max_binary_transfer_bytes": 32 << 20,
            "max_in_flight_requests": 8,
        },
    }
    assert "credential" not in json.dumps(body)
    assert _CREDENTIAL not in repr(request)
    assert _CREDENTIAL not in repr(_offer())
    assert _CREDENTIAL not in repr(_expectation())


@pytest.mark.parametrize("field", list(BridgeHandshakeField))
def test_handshake_rejects_each_exact_mismatch_without_retaining_values(
    field: BridgeHandshakeField,
) -> None:
    offer = _mismatched_offer(field)

    with pytest.raises(BridgeHandshakeMismatchError) as raised:
        validate_bridge_handshake(offer, _expectation())

    error = raised.value
    assert error.field is field
    assert error.code == "bridge.handshake_mismatch"
    assert error.category is ErrorCategory.UNAUTHENTICATED
    assert error.rpc_code == -32001
    assert error.parameters == {"field": field.value}
    assert isinstance(error, BridgeCredentialMismatchError) is (
        field is BridgeHandshakeField.CREDENTIAL
    )
    assert _CREDENTIAL not in repr(error.parameters)
    assert "wrong-session" not in repr(error.parameters)


def _mismatched_offer(field: BridgeHandshakeField) -> BridgeHandshakeOffer:
    """Return an offer differing in only the selected exact field."""
    offer = _offer()
    if field is BridgeHandshakeField.CREDENTIAL:
        return replace(offer, credential="b" * 64)
    if field is BridgeHandshakeField.SESSION_ID:
        return replace(offer, owner=replace(offer.owner, session_id="wrong-session"))
    if field is BridgeHandshakeField.RUN_REVISION:
        return replace(offer, owner=replace(offer.owner, run_revision=8))
    identity_field = {
        BridgeHandshakeField.ENGINE_ID: ("engine_id", "other"),
        BridgeHandshakeField.ENGINE_VERSION: ("version", "4.7.2"),
        BridgeHandshakeField.BUILD_ID: ("build_id", "toqraq.2"),
        BridgeHandshakeField.DISTRIBUTION_ID: ("distribution_id", "vendor"),
        BridgeHandshakeField.PLATFORM: ("platform", "linux"),
        BridgeHandshakeField.ARCHITECTURE: ("architecture", "arm64"),
    }.get(field)
    if identity_field is not None:
        name, value = identity_field
        return replace(
            offer,
            runtime_identity=replace(offer.runtime_identity, **{name: value}),
        )
    if field is BridgeHandshakeField.BRIDGE_ID:
        return replace(offer, bridge_id="toqraq.other.bridge")
    if field is BridgeHandshakeField.PROTOCOL:
        return replace(offer, protocol="2.0")
    if field is BridgeHandshakeField.CAPABILITIES:
        return replace(offer, capability_ids=offer.capability_ids | {"godot.extra.feature"})
    raise AssertionError(f"unhandled handshake field: {field}")


def test_handshake_only_candidate_authenticates_an_exact_empty_native_set() -> None:
    release = _release(
        capabilities=frozenset({"toqraq.play.lifecycle"}),
        bridge_capabilities=frozenset(),
    )
    expectation = BridgeHandshakeExpectation(
        credential=_CREDENTIAL,
        owner=BridgeOwnerKey(session_id=_SESSION_ID, run_revision=1),
        release=release,
        limits=_host_limits(),
    )
    offer = replace(
        _offer(),
        owner=expectation.owner,
        capability_ids=frozenset(),
    )

    accepted = validate_bridge_handshake(offer, expectation)

    assert accepted.capability_ids == frozenset()


@pytest.mark.parametrize(
    "call",
    [
        lambda: validate_bridge_credential("A" * 64),
        lambda: validate_bridge_credential("a" * 63),
        lambda: validate_bridge_session_id("session\x00bad"),
        lambda: validate_bridge_session_id("\u754c" * 171),
        lambda: validate_bridge_run_revision(True),
        lambda: validate_bridge_run_revision(0),
        lambda: validate_bridge_run_revision(MAX_BRIDGE_RUN_REVISION + 1),
        lambda: BridgeLimits(
            max_text_message_bytes=MIN_BRIDGE_TEXT_MESSAGE_BYTES - 1,
            max_binary_transfer_bytes=1,
            max_in_flight_requests=1,
        ),
        lambda: BridgeLimits(
            max_text_message_bytes=MIN_BRIDGE_TEXT_MESSAGE_BYTES,
            max_binary_transfer_bytes=1,
            max_in_flight_requests=True,
        ),
        lambda: BridgeLimits(
            max_text_message_bytes=MAX_BRIDGE_TEXT_MESSAGE_BYTES + 1,
            max_binary_transfer_bytes=1,
            max_in_flight_requests=1,
        ),
    ],
)
def test_core_handshake_values_reject_noncanonical_and_out_of_range_input(
    call: Callable[[], object],
) -> None:
    with pytest.raises(ValueError):
        call()


def test_session_id_byte_bound_is_exact() -> None:
    assert validate_bridge_session_id("\u754c" * 170) == "\u754c" * 170
    assert validate_bridge_run_revision(MAX_BRIDGE_RUN_REVISION) == MAX_BRIDGE_RUN_REVISION


@pytest.mark.parametrize(
    ("message", "error_type", "code", "rpc_code"),
    [
        (
            '{"jsonrpc":"2.0","jsonrpc":"2.0","id":"x","method":"toqraq.handshake","params":{}}',
            BridgeJsonInvalidError,
            "bridge.json_invalid",
            -32700,
        ),
        ("[1]", BridgeRequestInvalidError, "bridge.request_invalid", -32600),
        (
            json.dumps({**_payload(), "id": 1}),
            BridgeRequestInvalidError,
            "bridge.request_invalid",
            -32600,
        ),
        (
            json.dumps({**_payload(), "extra": True}),
            BridgeRequestInvalidError,
            "bridge.request_invalid",
            -32600,
        ),
        (
            json.dumps({**_payload(), "method": "toqraq.other"}),
            BridgeMethodNotFoundError,
            "bridge.method_not_found",
            -32601,
        ),
    ],
)
def test_decoder_classifies_json_rpc_failures_stably(
    message: str,
    error_type: type[BridgeWireError],
    code: str,
    rpc_code: int,
) -> None:
    with pytest.raises(error_type) as raised:
        decode_handshake_request(message)
    error = raised.value
    assert error.code == code
    assert error.rpc_code == rpc_code


def test_decoder_rejects_nonfinite_numbers_lone_surrogates_and_oversized_text() -> None:
    nonfinite = _payload()
    params = dict(cast(dict[str, object], nonfinite["params"]))
    params["run_revision"] = float("nan")
    nonfinite["params"] = params
    with pytest.raises(BridgeJsonInvalidError):
        decode_handshake_request(json.dumps(nonfinite))

    overflow = json.dumps(_payload()).replace('"run_revision": 7', '"run_revision": 1e999')
    with pytest.raises(BridgeJsonInvalidError):
        decode_handshake_request(overflow)

    invalid_unicode = _payload()
    params = dict(cast(dict[str, object], invalid_unicode["params"]))
    params["session_id"] = "\ud800"
    invalid_unicode["params"] = params
    with pytest.raises(BridgeJsonInvalidError):
        decode_handshake_request(json.dumps(invalid_unicode))

    with pytest.raises(BridgeMessageTooLargeError) as raised:
        decode_handshake_request(" " * (MAX_BRIDGE_TEXT_MESSAGE_BYTES + 1))
    assert raised.value.parameters == {
        "actual_bytes": MAX_BRIDGE_TEXT_MESSAGE_BYTES + 1,
        "maximum_bytes": MAX_BRIDGE_TEXT_MESSAGE_BYTES,
    }


def test_decoder_applies_aggregate_depth_and_collection_bounds_before_dispatch() -> None:
    deep: object = True
    for _ in range(17):
        deep = [deep]
    payload = _payload()
    params = dict(cast(dict[str, object], payload["params"]))
    params["unknown"] = deep
    payload["params"] = params
    with pytest.raises(BridgeRequestInvalidError):
        decode_handshake_request(json.dumps(payload))

    params["unknown"] = list(range(257))
    with pytest.raises(BridgeRequestInvalidError):
        decode_handshake_request(json.dumps(payload))


def test_invalid_params_report_only_a_bounded_schema_location() -> None:
    secret = "do-not-echo-this-value"
    payload = _payload()
    params = dict(cast(dict[str, object], payload["params"]))
    params["capabilities"] = [secret, secret]
    payload["params"] = params

    with pytest.raises(BridgeParamsInvalidError) as raised:
        decode_handshake_request(json.dumps(payload))

    error = raised.value
    assert error.code == "bridge.params_invalid"
    assert error.details == {"location": "params.capabilities"}
    assert error.cause is None
    assert error.__cause__ is None
    assert error.__context__ is None
    response = bridge_error_response(error, request_id="handshake:7")
    serialized = response.model_dump_json()
    assert secret not in serialized
    assert response.error.code == -32602
    assert response.error.message == "Invalid params"
    assert response.error.data.trace_id == str(error.trace_id)


@pytest.mark.parametrize(
    ("message", "error_type"),
    [
        ('{"credential":"do-not-retain-this-secret"', BridgeJsonInvalidError),
        (
            json.dumps({**_payload(), "id": "do not retain this request"}),
            BridgeRequestInvalidError,
        ),
    ],
)
def test_decoder_failures_do_not_retain_raw_parser_or_validation_input(
    message: str,
    error_type: type[BridgeWireError],
) -> None:
    with pytest.raises(error_type) as raised:
        decode_handshake_request(message)

    error = raised.value
    assert error.cause is None
    assert error.__cause__ is None
    assert error.__context__ is None
    assert "do-not-retain" not in repr(error)


def test_wire_errors_have_unique_codes_numbers_and_exact_error_responses() -> None:
    assert len({error_type.code for error_type in BRIDGE_WIRE_ERROR_TYPES}) == len(
        BRIDGE_WIRE_ERROR_TYPES
    )
    assert len({error_type.rpc_code for error_type in BRIDGE_WIRE_ERROR_TYPES}) == len(
        BRIDGE_WIRE_ERROR_TYPES
    )
    for error_type in BRIDGE_WIRE_ERROR_TYPES:
        if error_type is BridgeParamsInvalidError:
            error = error_type(location="params")
        elif error_type is BridgeHandshakeMismatchError:
            error = error_type(field=BridgeHandshakeField.PROTOCOL)
        elif error_type is BridgeMessageTooLargeError:
            error = error_type(actual_bytes=2, maximum_bytes=1)
        else:
            error = error_type()
        response = bridge_error_response(error, request_id=None)
        payload = response.model_dump(mode="json")
        assert payload["jsonrpc"] == "2.0"
        assert payload["id"] is None
        assert payload["error"]["code"] == error.rpc_code
        assert payload["error"]["data"]["code"] == error.code
        assert payload["error"]["data"]["category"] == error.category.value


def test_handshake_and_response_models_forbid_alternate_envelopes() -> None:
    request = BridgeHandshakeRequest.model_validate(_payload())
    with pytest.raises(ValidationError):
        BridgeHandshakeRequest.model_validate({**_payload(), "result": {}})
    with pytest.raises(ValidationError):
        BridgeHandshakeRequest.model_validate({**_payload(), "id": "bad id"})
    normalized_identity = _payload()
    params = dict(cast(dict[str, object], normalized_identity["params"]))
    params["engine_id"] = " godot "
    normalized_identity["params"] = params
    with pytest.raises(ValidationError):
        BridgeHandshakeRequest.model_validate(normalized_identity)

    accepted = validate_bridge_handshake(request.params.to_core(), _expectation())
    response = BridgeHandshakeResponse.from_core(
        request_id=request.id,
        value=accepted,
    ).model_dump(mode="python")
    with pytest.raises(ValidationError):
        BridgeHandshakeResponse.model_validate({**response, "error": {}})
    error = bridge_error_response(BridgeJsonInvalidError(), request_id=None).model_dump(
        mode="python"
    )
    with pytest.raises(ValidationError):
        BridgeErrorResponse.model_validate({**error, "result": {}})
