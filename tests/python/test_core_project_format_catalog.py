"""Read-only engine project-format catalog tests."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from toqraq.core.engine_contribution import (
    EngineProjectFormat,
    ProjectDescription,
)
from toqraq.core.errors import EngineNotFoundError
from toqraq.core.project_format_catalog import MAX_PROJECT_FORMATS, ProjectFormatCatalog

from _project_format_support import EmptyProjectInventoryReader


class _Probe:
    def __init__(self, engine_id: str) -> None:
        self._engine_id = engine_id

    @property
    def engine_id(self) -> str:
        return self._engine_id

    def probe(self, project_root: Path) -> ProjectDescription | None:
        del project_root
        return None


def _format(engine_id: str) -> EngineProjectFormat:
    return EngineProjectFormat(
        engine_id=engine_id,
        project_probe=_Probe(engine_id),
        project_inventory_reader=EmptyProjectInventoryReader(engine_id),
    )


def test_catalog_preserves_explicit_order_and_exact_instances() -> None:
    cocos = _format("cocos")
    godot = _format("godot")
    catalog = ProjectFormatCatalog((cocos, godot))

    assert catalog.list() == (cocos, godot)
    assert catalog.find("godot") is godot
    assert catalog.require("cocos") is cocos


def test_catalog_rejects_duplicate_incomplete_and_oversized_composition() -> None:
    godot = _format("godot")

    assert ProjectFormatCatalog(()).list() == ()
    with pytest.raises(ValueError):
        ProjectFormatCatalog((godot, godot))
    with pytest.raises(ValueError):
        ProjectFormatCatalog((godot, cast(EngineProjectFormat, object())))
    with pytest.raises(ValueError):
        ProjectFormatCatalog(_format(f"engine{index}") for index in range(MAX_PROJECT_FORMATS + 1))


@pytest.mark.parametrize("engine_id", ["unity", "Godot", "godot/runtime", ""])
def test_required_format_returns_typed_failure_for_unknown_or_invalid_identity(
    engine_id: str,
) -> None:
    catalog = ProjectFormatCatalog((_format("godot"),))

    with pytest.raises(EngineNotFoundError) as caught:
        catalog.require(engine_id)

    assert caught.value.parameters["engine"] == engine_id
