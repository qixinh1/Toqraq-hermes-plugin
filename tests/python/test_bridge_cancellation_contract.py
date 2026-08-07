"""Strict same-connection bridge cancellation contract tests."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError
from toqraq.contracts.bridge_cancellation import (
    REQUEST_CANCEL_METHOD,
    RequestCancelRequest,
    RequestCancelResponse,
)
from toqraq.core.bridge import BridgeRequestReference
from toqraq.core.request_cancellation import (
    CancellationAcknowledgement,
    CancellationDisposition,
    CancelRequestCommand,
)


@pytest.mark.parametrize("disposition", tuple(CancellationDisposition))
def test_cancellation_round_trips_distinct_owner_and_disposition(
    disposition: CancellationDisposition,
) -> None:
    target = BridgeRequestReference(value="host-8")
    command = CancelRequestCommand(target=target)
    value = CancellationAcknowledgement(disposition=disposition)
    request = RequestCancelRequest.from_core(request_id="host-9", command=command)
    response = RequestCancelResponse.from_core(
        request_id=request.id,
        value=value,
    )

    assert request.method == REQUEST_CANCEL_METHOD
    assert request.params.to_core() == command
    assert response.result.to_core() == value
    assert response.model_dump(mode="json")["result"] == {"disposition": disposition.value}


def test_cancellation_rejects_self_target_bad_id_and_untyped_outcome() -> None:
    target = BridgeRequestReference(value="host-8")
    command = CancelRequestCommand(target=target)
    request = RequestCancelRequest.from_core(
        request_id="host-9",
        command=command,
    ).model_dump(mode="json")
    invalid = deepcopy(request)
    invalid["id"] = invalid["params"]["target_request_id"]
    with pytest.raises(ValidationError, match="must differ"):
        RequestCancelRequest.model_validate(invalid)

    invalid = deepcopy(request)
    invalid["params"]["target_request_id"] = "bad request"
    with pytest.raises(ValidationError):
        RequestCancelRequest.model_validate(invalid)

    response = RequestCancelResponse.from_core(
        request_id="host-9",
        value=CancellationAcknowledgement(
            disposition=CancellationDisposition.REQUESTED,
        ),
    ).model_dump(mode="json")
    invalid = deepcopy(response)
    invalid["result"]["disposition"] = {"recursive": True}
    with pytest.raises(ValidationError):
        RequestCancelResponse.model_validate(invalid)
    invalid = deepcopy(response)
    invalid["result"]["kind"] = "cancellation"
    with pytest.raises(ValidationError, match="Extra inputs"):
        RequestCancelResponse.model_validate(invalid)
