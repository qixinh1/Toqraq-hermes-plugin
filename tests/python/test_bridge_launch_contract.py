"""Contract tests for the one-shot bridge launch bootstrap."""

from __future__ import annotations

from dataclasses import fields

import pytest
from pydantic import ValidationError
from toqraq.contracts.bridge_launch import (
    BridgeLaunchBootstrapValue,
    encode_bridge_launch_bootstrap,
)
from toqraq.core.bridge import MAX_BRIDGE_RUN_REVISION, MAX_BRIDGE_SESSION_ID_BYTES
from toqraq.core.bridge_launch import BridgeLaunchBootstrap
from toqraq.core.process_tree import MAX_PROCESS_BOOTSTRAP_BYTES, ProcessBootstrap

_CREDENTIAL = "0123456789abcdef" * 4
_SESSION_ID = "Hermes-会话"


def _value(
    *,
    credential: str = _CREDENTIAL,
    session_id: str = _SESSION_ID,
    run_revision: int = 7,
) -> BridgeLaunchBootstrap:
    return BridgeLaunchBootstrap(
        credential=credential,
        session_id=session_id,
        run_revision=run_revision,
    )


def test_core_value_reuses_exact_bridge_validation_and_redacts_credential() -> None:
    value = _value(run_revision=MAX_BRIDGE_RUN_REVISION)

    assert tuple(field.name for field in fields(value)) == (
        "credential",
        "session_id",
        "run_revision",
    )
    assert value.session_id == _SESSION_ID
    assert _CREDENTIAL not in repr(value)
    assert _CREDENTIAL not in str(value)

    with pytest.raises(ValueError, match="credential"):
        _value(credential="A" * 64)
    with pytest.raises(ValueError, match="session ID"):
        _value(session_id="bad\x00session")
    with pytest.raises(ValueError, match="revision"):
        _value(run_revision=0)


def test_contract_value_is_exact_immutable_and_secret_redacted() -> None:
    value = BridgeLaunchBootstrapValue(
        credential=_CREDENTIAL,
        session_id=_SESSION_ID,
        run_revision=7,
    )

    assert value.session_id == _SESSION_ID
    assert value.run_revision == 7
    assert _CREDENTIAL not in repr(value)
    with pytest.raises(ValidationError):
        BridgeLaunchBootstrapValue.model_validate(
            {
                "credential": _CREDENTIAL,
                "session_id": _SESSION_ID,
                "run_revision": 7,
                "endpoint": "ws://127.0.0.1:1/toqraq/bridge",
            }
        )
    with pytest.raises(ValidationError):
        value.run_revision = 8  # type: ignore[misc]


def test_encoding_is_canonical_utf8_and_owned_by_process_bootstrap() -> None:
    encoded = encode_bridge_launch_bootstrap(_value())
    expected = (
        '{"credential":"0123456789abcdef0123456789abcdef0123456789abcdef'
        '0123456789abcdef","run_revision":7,"session_id":"Hermes-会话"}'
    ).encode()

    assert isinstance(encoded, ProcessBootstrap)
    assert encoded.payload == expected
    assert len(encoded.payload) <= MAX_PROCESS_BOOTSTRAP_BYTES
    assert not encoded.payload.startswith(b"\xef\xbb\xbf")
    assert b"\n" not in encoded.payload
    assert b"\r" not in encoded.payload
    assert _CREDENTIAL not in repr(encoded)


def test_maximum_session_id_stays_inside_process_bootstrap_bound() -> None:
    value = _value(session_id="s" * MAX_BRIDGE_SESSION_ID_BYTES)
    encoded = encode_bridge_launch_bootstrap(value)

    assert 0 < len(encoded.payload) <= MAX_PROCESS_BOOTSTRAP_BYTES
