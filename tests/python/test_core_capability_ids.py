from __future__ import annotations

from toqraq.core.capability_ids import (
    HOST_ONLY_ENGINE_CAPABILITY_IDS,
    MANDATORY_BRIDGE_CAPABILITY_IDS,
    MANDATORY_ENGINE_CAPABILITY_IDS,
)
from toqraq.core.runtime import validate_namespaced_id


def test_mandatory_engine_capabilities_are_exact_namespaced_ids() -> None:
    assert (
        frozenset(
            {
                "toqraq.control.input",
                "toqraq.observe.diagnostics",
                "toqraq.observe.frame",
                "toqraq.observe.hierarchy",
                "toqraq.observe.performance",
                "toqraq.observe.properties",
                "toqraq.play.lifecycle",
                "toqraq.play.pause",
                "toqraq.play.restart",
                "toqraq.play.step",
                "toqraq.preview.display",
                "toqraq.project.inspect",
                "toqraq.runtime.prepare",
            }
        )
        == MANDATORY_ENGINE_CAPABILITY_IDS
    )
    assert all(
        validate_namespaced_id(capability_id) == capability_id
        for capability_id in MANDATORY_ENGINE_CAPABILITY_IDS
    )
    assert (
        frozenset(
            {
                "toqraq.control.input",
                "toqraq.observe.diagnostics",
                "toqraq.observe.frame",
                "toqraq.observe.hierarchy",
                "toqraq.observe.performance",
                "toqraq.observe.properties",
                "toqraq.play.pause",
                "toqraq.play.step",
            }
        )
        == MANDATORY_BRIDGE_CAPABILITY_IDS
    )
    assert MANDATORY_BRIDGE_CAPABILITY_IDS < MANDATORY_ENGINE_CAPABILITY_IDS
    assert (
        frozenset(
            {
                "toqraq.play.lifecycle",
                "toqraq.play.restart",
                "toqraq.preview.display",
                "toqraq.project.inspect",
                "toqraq.runtime.prepare",
            }
        )
        == HOST_ONLY_ENGINE_CAPABILITY_IDS
    )
    assert not MANDATORY_BRIDGE_CAPABILITY_IDS & HOST_ONLY_ENGINE_CAPABILITY_IDS
