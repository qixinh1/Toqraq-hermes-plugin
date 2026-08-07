"""Public JSON frame result and focused capture service tests."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import pytest
from pydantic import ValidationError
from toqraq.contracts.bridge_frame import FrameCaptureParams
from toqraq.contracts.frame_capture import FrameCaptureResult
from toqraq.core.capability_ids import OBSERVE_FRAME_CAPABILITY_ID
from toqraq.core.errors import ProtocolError
from toqraq.services.frame_capture import FrameCaptureService

from _bridge_feature_values import frame_values
from _live_feature_support import make_live_feature_fixture


def test_capture_returns_complete_canonical_json_png_without_transfer_identity(
    tmp_path: Path,
) -> None:
    async def run() -> None:
        fixture = make_live_feature_fixture(tmp_path)
        query, expected = frame_values()
        try:
            result = await FrameCaptureService(fixture.registry, fixture.gate).capture(
                "hermes-session",
                FrameCaptureParams.from_core(query),
            )
            payload = result.model_dump(mode="json")

            assert result.to_core(query=query) == expected
            assert base64.b64decode(payload["png_base64"], validate=True) == expected.data
            assert payload["mime_type"] == "image/png"
            assert payload["byte_length"] == len(expected.data)
            assert "transfer_id" not in payload
            assert fixture.frame.queries == [query]
        finally:
            await fixture.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("png_base64", "A==="),
        ("sha256", "0" * 64),
        ("byte_length", 1),
    ],
)
def test_public_frame_metadata_must_match_complete_png(field: str, value: object) -> None:
    query, frame = frame_values()
    payload = FrameCaptureResult.from_core(frame, query=query).model_dump(mode="python")
    payload[field] = value

    with pytest.raises(ValidationError):
        FrameCaptureResult.model_validate(payload)


def test_capture_rejects_a_result_above_the_original_byte_ceiling(tmp_path: Path) -> None:
    async def run() -> None:
        fixture = make_live_feature_fixture(tmp_path)
        query, _frame = frame_values()
        request = FrameCaptureParams.from_core(query).model_copy(update={"maximum_bytes": 1})
        try:
            with pytest.raises(ProtocolError) as captured:
                await FrameCaptureService(fixture.registry, fixture.gate).capture(
                    "hermes-session",
                    request,
                )
            assert captured.value.parameters == {"operation": OBSERVE_FRAME_CAPABILITY_ID}
            assert captured.value.details == {"reason": "result_contract_invalid"}
        finally:
            await fixture.close()

    asyncio.run(run())
