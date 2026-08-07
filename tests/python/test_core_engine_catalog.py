"""Immutable engine contribution catalog tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import cast

import pytest
from toqraq.core.bridge import BridgeListenerEndpoint
from toqraq.core.engine_catalog import MAX_ENGINE_CONTRIBUTIONS, EngineCatalog
from toqraq.core.engine_contribution import (
    EngineContribution,
    EngineProjectFormat,
    ProjectDescription,
)
from toqraq.core.preview import PreviewSurface
from toqraq.core.process_tree import (
    ProcessBootstrap,
    ProcessEnvironment,
    ProcessLaunch,
    ProcessTree,
)
from toqraq.core.runtime import PreparedRuntime, RuntimeRelease

from _project_format_support import EmptyProjectInventoryReader


class _Probe:
    def __init__(self, engine_id: str) -> None:
        self._engine_id = engine_id

    @property
    def engine_id(self) -> str:
        return self._engine_id

    def probe(self, project_root: Path) -> ProjectDescription | None:
        return None


class _RuntimeCatalog:
    def __init__(self, engine_id: str) -> None:
        self._engine_id = engine_id

    @property
    def engine_id(self) -> str:
        return self._engine_id

    def releases(self, project: ProjectDescription) -> tuple[RuntimeRelease, ...]:
        return ()


class _Provisioner:
    def __init__(self, engine_id: str) -> None:
        self._engine_id = engine_id

    @property
    def engine_id(self) -> str:
        return self._engine_id

    def prepare(self, release: RuntimeRelease, cancellation: Event) -> PreparedRuntime:
        raise AssertionError("catalog lookup must not prepare a runtime")


class _LaunchPlanner:
    def __init__(self, engine_id: str) -> None:
        self._engine_id = engine_id

    @property
    def engine_id(self) -> str:
        return self._engine_id

    def plan(
        self,
        project: ProjectDescription,
        runtime: PreparedRuntime,
        endpoint: BridgeListenerEndpoint,
        environment: ProcessEnvironment,
        bootstrap: ProcessBootstrap,
    ) -> ProcessLaunch:
        raise AssertionError("catalog lookup must not plan a launch")


class _PreviewLocator:
    def __init__(self, engine_id: str) -> None:
        self._engine_id = engine_id

    @property
    def engine_id(self) -> str:
        return self._engine_id

    async def locate(
        self,
        project: ProjectDescription,
        runtime: PreparedRuntime,
        process_tree: ProcessTree,
        cancellation: Event,
    ) -> PreviewSurface:
        raise AssertionError("catalog lookup must not locate a preview")


def _contribution(engine_id: str) -> EngineContribution:
    project_format = EngineProjectFormat(
        engine_id=engine_id,
        project_probe=_Probe(engine_id),
        project_inventory_reader=EmptyProjectInventoryReader(engine_id),
    )
    return EngineContribution(
        project_format=project_format,
        runtime_catalog=_RuntimeCatalog(engine_id),
        runtime_provisioner=_Provisioner(engine_id),
        game_launch_planner=_LaunchPlanner(engine_id),
        preview_locator=_PreviewLocator(engine_id),
    )


def test_catalog_preserves_explicit_order_and_exact_instances() -> None:
    cocos = _contribution("cocos")
    godot = _contribution("godot")
    catalog = EngineCatalog((cocos, godot))

    assert catalog.list() == (cocos, godot)
    assert catalog.find("godot") is godot
    assert catalog.find("cocos") is cocos


def test_catalog_accepts_empty_and_rejects_duplicate_incomplete_or_oversized_composition() -> None:
    godot = _contribution("godot")

    assert EngineCatalog(()).list() == ()
    with pytest.raises(ValueError):
        EngineCatalog((godot, godot))
    with pytest.raises(ValueError):
        EngineCatalog((godot, cast(EngineContribution, object())))
    with pytest.raises(ValueError):
        EngineCatalog(
            _contribution(f"engine{index}") for index in range(MAX_ENGINE_CONTRIBUTIONS + 1)
        )


def test_catalog_returns_none_for_a_valid_unadmitted_engine() -> None:
    catalog = EngineCatalog((_contribution("godot"),))

    assert catalog.find("unity") is None


def test_catalog_does_not_accept_a_mutated_cross_engine_contribution() -> None:
    godot = _contribution("godot")

    with pytest.raises(ValueError):
        replace(
            godot,
            project_format=EngineProjectFormat(
                engine_id="unity",
                project_probe=_Probe("unity"),
                project_inventory_reader=EmptyProjectInventoryReader("unity"),
            ),
        )
