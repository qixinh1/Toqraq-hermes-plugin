from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from toqraq.components.space import (
    ComponentSpacePhase,
    ComponentSpacePolicy,
    ComponentSpaceRejectedError,
    ComponentSpaceRejection,
    require_component_space,
)


class _Probe:
    def __init__(self, value: object) -> None:
        self.value = value
        self.paths: list[Path] = []

    def available_bytes(self, path: Path) -> int:
        self.paths.append(path)
        if isinstance(self.value, OSError):
            raise self.value
        return cast(int, self.value)


def test_capacity_accepts_exact_payload_plus_reserve(tmp_path: Path) -> None:
    probe = _Probe(110)

    require_component_space(
        probe,
        ComponentSpacePolicy(reserve_bytes=10),
        tmp_path,
        100,
        ComponentSpacePhase.DOWNLOAD,
    )

    assert probe.paths == [tmp_path]


def test_capacity_failure_carries_only_safe_numeric_facts(tmp_path: Path) -> None:
    with pytest.raises(ComponentSpaceRejectedError) as captured:
        require_component_space(
            _Probe(109),
            ComponentSpacePolicy(reserve_bytes=10),
            tmp_path,
            100,
            ComponentSpacePhase.INSTALL,
        )

    error = captured.value
    assert error.reason is ComponentSpaceRejection.INSUFFICIENT
    assert error.phase is ComponentSpacePhase.INSTALL
    assert error.required_bytes == 110
    assert error.available_bytes == 109
    assert str(tmp_path) not in str(error)


@pytest.mark.parametrize("value", [OSError("private"), -1, True, "100"])
def test_capacity_rejects_failed_or_invalid_probe_values(
    tmp_path: Path,
    value: object,
) -> None:
    with pytest.raises(ComponentSpaceRejectedError) as captured:
        require_component_space(
            _Probe(value),
            ComponentSpacePolicy(reserve_bytes=0),
            tmp_path,
            1,
            ComponentSpacePhase.DOWNLOAD,
        )

    assert captured.value.reason is ComponentSpaceRejection.PROBE_FAILED


@pytest.mark.parametrize("value", [-1, True, 1.5])
def test_capacity_policy_rejects_invalid_reserve(value: object) -> None:
    with pytest.raises(ValueError):
        ComponentSpacePolicy(reserve_bytes=cast(int, value))


@pytest.mark.parametrize("value", [-1, True, 1.5])
def test_capacity_rejects_invalid_payload_size(tmp_path: Path, value: object) -> None:
    with pytest.raises(ValueError):
        require_component_space(
            _Probe(100),
            ComponentSpacePolicy(reserve_bytes=0),
            tmp_path,
            cast(int, value),
            ComponentSpacePhase.DOWNLOAD,
        )
