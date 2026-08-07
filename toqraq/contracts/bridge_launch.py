"""Exact secret-safe process bootstrap contract for one bridge launch."""

from __future__ import annotations

import json

from pydantic import Field

from ..core.bridge import MAX_BRIDGE_RUN_REVISION
from ..core.bridge_launch import BridgeLaunchBootstrap
from ..core.process_tree import ProcessBootstrap
from .base import ContractModel
from .bridge import BridgeCredential, BridgeSessionId

_CANONICAL_JSON_SEPARATORS = (",", ":")


class BridgeLaunchBootstrapValue(ContractModel):
    """Exact JSON object transferred through the one-shot bootstrap pipe."""

    credential: BridgeCredential = Field(repr=False)
    session_id: BridgeSessionId
    run_revision: int = Field(gt=0, le=MAX_BRIDGE_RUN_REVISION)

    @classmethod
    def from_core(cls, value: BridgeLaunchBootstrap) -> BridgeLaunchBootstrapValue:
        """Create one boundary value from a validated pure launch identity."""
        if not isinstance(value, BridgeLaunchBootstrap):
            raise ValueError("bridge launch bootstrap is invalid")
        return cls(
            credential=value.credential,
            session_id=value.session_id,
            run_revision=value.run_revision,
        )


def encode_bridge_launch_bootstrap(value: BridgeLaunchBootstrap) -> ProcessBootstrap:
    """Encode one deterministic UTF-8 object owned by a process launch."""
    contract = BridgeLaunchBootstrapValue.from_core(value)
    payload = json.dumps(
        contract.model_dump(mode="json"),
        allow_nan=False,
        ensure_ascii=False,
        separators=_CANONICAL_JSON_SEPARATORS,
        sort_keys=True,
    ).encode("utf-8")
    return ProcessBootstrap(payload=payload)
