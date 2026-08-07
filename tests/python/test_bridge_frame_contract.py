"""Strict frame announcement and completed-binary bridge contract tests."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import cast

import pytest
from pydantic import ValidationError
from toqraq.contracts.bridge_frame import (
    FRAME_CAPTURE_METHOD,
    FrameCaptureRequest,
    FrameCaptureResponse,
)
from toqraq.core.frame_capture import (
    FrameCaptureQuery,
    FrameCaptureResult,
    FrameScaling,
)
from toqraq.core.geometry import Size
from toqraq.core.observation import ObservationRevision

from _png_support import png_header


def _frame_query() -> FrameCaptureQuery:
    return FrameCaptureQuery(
        maximum_size=Size(width=1_920, height=1_080),
        scaling=FrameScaling.CONTAIN,
        maximum_bytes=8 << 20,
    )


def _png_header(size: Size) -> bytes:
    return png_header(size.width, size.height)


def _frame_result() -> FrameCaptureResult:
    encoded_size = Size(width=1_920, height=1_080)
    return FrameCaptureResult(
        viewport_size=Size(width=2_560, height=1_440),
        captured_at_unix_ms=1_700_000_000_000,
        encoded_size=encoded_size,
        frame_revision=ObservationRevision(value="frame:42"),
        data=_png_header(encoded_size),
    )


def _response() -> FrameCaptureResponse:
    return FrameCaptureResponse.from_core(
        request_id="host-3",
        value=_frame_result(),
        query=_frame_query(),
        transfer_id="a" * 32,
    )


def test_frame_announcement_round_trips_without_json_media_bytes() -> None:
    request = FrameCaptureRequest.from_core(request_id="host-3", query=_frame_query())
    frame = _frame_result()
    response = _response()

    assert request.method == FRAME_CAPTURE_METHOD
    assert request.params.to_core() == _frame_query()
    assert (
        FrameCaptureRequest.model_validate(request.model_dump(mode="json")).params.to_core()
        == _frame_query()
    )
    assert response.result.to_core(query=_frame_query(), png_bytes=frame.data) == frame
    payload = response.model_dump(mode="json")
    assert "kind" not in payload["result"]
    assert payload["result"]["viewport_size"] == {"width": 2_560, "height": 1_440}
    assert payload["result"]["transfer"] == {
        "transfer_id": "a" * 32,
        "mime_type": "image/png",
        "size": {"width": 1_920, "height": 1_080},
        "byte_length": len(frame.data),
        "sha256": hashlib.sha256(frame.data).hexdigest(),
        "frame_revision": "frame:42",
    }
    serialized = response.model_dump_json()
    assert "base64" not in serialized
    assert '"data"' not in serialized
    assert (
        FrameCaptureResponse.model_validate(payload).result.to_core(
            query=_frame_query(),
            png_bytes=frame.data,
        )
        == frame
    )


def test_frame_contract_rejects_excess_work_and_hidden_payload() -> None:
    request = FrameCaptureRequest.from_core(
        request_id="host-3",
        query=_frame_query(),
    ).model_dump(mode="json")
    invalid = deepcopy(request)
    invalid["params"]["maximum_size"] = {"width": 16_384, "height": 16_384}
    with pytest.raises(ValidationError, match="pixel budget"):
        FrameCaptureRequest.model_validate(invalid)

    response = _response().model_dump(mode="json")
    invalid = deepcopy(response)
    invalid["result"]["transfer"]["transfer_id"] = "A" * 32
    with pytest.raises(ValidationError):
        FrameCaptureResponse.model_validate(invalid)

    invalid = deepcopy(response)
    invalid["result"]["transfer"]["sha256"] = "b" * 63
    with pytest.raises(ValidationError):
        FrameCaptureResponse.model_validate(invalid)

    invalid = deepcopy(response)
    invalid["result"]["transfer"]["data"] = "base64-is-forbidden"
    with pytest.raises(ValidationError, match="Extra inputs"):
        FrameCaptureResponse.model_validate(invalid)

    invalid = deepcopy(response)
    invalid["result"]["kind"] = "capture"
    with pytest.raises(ValidationError, match="Extra inputs"):
        FrameCaptureResponse.model_validate(invalid)


def test_frame_binary_must_match_announcement_png_and_request() -> None:
    query = _frame_query()
    frame = _frame_result()
    response = _response()

    with pytest.raises(ValueError, match="immutable bytes"):
        response.result.to_core(
            query=query,
            png_bytes=cast(bytes, bytearray(frame.data)),
        )
    with pytest.raises(ValueError, match="length"):
        response.result.to_core(query=query, png_bytes=frame.data + b"x")

    payload = response.model_dump(mode="json")
    bad_hash = deepcopy(payload)
    bad_hash["result"]["transfer"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        FrameCaptureResponse.model_validate(bad_hash).result.to_core(
            query=query,
            png_bytes=frame.data,
        )

    bad_signature = b"not-png!" + frame.data[8:]
    bad_signature_payload = deepcopy(payload)
    bad_signature_payload["result"]["transfer"]["sha256"] = hashlib.sha256(
        bad_signature
    ).hexdigest()
    with pytest.raises(ValueError, match="not a PNG"):
        FrameCaptureResponse.model_validate(bad_signature_payload).result.to_core(
            query=query,
            png_bytes=bad_signature,
        )

    with pytest.raises(ValueError, match="byte ceiling"):
        response.result.to_core(
            query=FrameCaptureQuery(
                maximum_size=query.maximum_size,
                scaling=query.scaling,
                maximum_bytes=len(frame.data) - 1,
            ),
            png_bytes=frame.data,
        )


def test_frame_response_must_match_exact_native_or_contain_size() -> None:
    query = _frame_query()
    frame = _frame_result()
    response = _response().model_dump(mode="json")

    wrong_size = Size(width=1_919, height=1_080)
    wrong_png = _png_header(wrong_size)
    response["result"]["transfer"]["size"] = {
        "width": wrong_size.width,
        "height": wrong_size.height,
    }
    response["result"]["transfer"]["byte_length"] = len(wrong_png)
    response["result"]["transfer"]["sha256"] = hashlib.sha256(wrong_png).hexdigest()
    with pytest.raises(ValueError, match="encoded size"):
        FrameCaptureResponse.model_validate(response).result.to_core(
            query=query,
            png_bytes=wrong_png,
        )

    native = FrameCaptureQuery(
        maximum_size=Size(width=1_920, height=1_080),
        scaling=FrameScaling.NATIVE,
        maximum_bytes=8 << 20,
    )
    with pytest.raises(ValueError, match="does not fit"):
        FrameCaptureResponse.from_core(
            request_id="host-3",
            value=frame,
            query=native,
            transfer_id="a" * 32,
        )
