"""Pure and Pydantic project-inventory contract invariants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from toqraq.api import build_router
from toqraq.contracts.project_inventory import (
    ProjectInventoryCategoryCounts,
    ProjectInventoryEntryValue,
    ProjectInventoryRequest,
    ProjectInventoryResult,
    ProjectInventoryScanResult,
    ProjectInventorySource,
)
from toqraq.core.project_inventory import (
    MAX_PROJECT_INVENTORY_PAGE_ENTRIES,
    ProjectInventoryCategory,
    ProjectInventoryEntry,
    ProjectInventorySnapshot,
    ProjectInventoryStatistics,
)
from toqraq.engines.godot.project_format import GODOT_PROJECT_FORMAT
from toqraq.services.container import build_container

_REVISION = "1" * 64
_CURSOR = "eyJvIjoxLCJxIjoiMSIsInIiOiIxIiwidiI6MX0"


def _statistics(*, complete: bool = True) -> ProjectInventoryStatistics:
    return ProjectInventoryStatistics(
        visited_entries=4,
        visited_directories=2,
        excluded_links=1,
        excluded_policy=0,
        unreadable=0,
        unclassified=1,
        complete=complete,
    )


def _counts() -> ProjectInventoryCategoryCounts:
    return ProjectInventoryCategoryCounts(
        scene=1,
        script=1,
        resource=0,
        setting=0,
        dependency=0,
        input=0,
    )


def _scan() -> ProjectInventoryScanResult:
    return ProjectInventoryScanResult(
        visited_entries=4,
        visited_directories=2,
        excluded_links=1,
        excluded_policy=0,
        unreadable=0,
        unclassified=1,
        complete=True,
    )


def _result(**changes: object) -> ProjectInventoryResult:
    values: dict[str, object] = {
        "engine": "godot",
        "source": ProjectInventorySource.WORKSPACE,
        "revision": _REVISION,
        "scope": None,
        "categories": (
            ProjectInventoryCategory.SCENE,
            ProjectInventoryCategory.SCRIPT,
        ),
        "counts": _counts(),
        "scan": _scan(),
        "total_count": 2,
        "entries": (
            ProjectInventoryEntryValue(
                path="a.tscn",
                category=ProjectInventoryCategory.SCENE,
            ),
            ProjectInventoryEntryValue(
                path="b.gd",
                category=ProjectInventoryCategory.SCRIPT,
            ),
        ),
        "truncated": False,
        "next_cursor": None,
    }
    values.update(changes)
    return ProjectInventoryResult.model_validate(values)


def test_core_paths_names_snapshots_and_statistics_are_bounded() -> None:
    path = "游" * 170
    name = "游" * 85
    entry = ProjectInventoryEntry(
        path=path,
        category=ProjectInventoryCategory.INPUT,
        name=name,
    )
    snapshot = ProjectInventorySnapshot(
        engine_id="godot",
        entries=(entry,),
        statistics=_statistics(),
    )

    assert snapshot.entries == (entry,)
    with pytest.raises(ValueError, match="path is too large"):
        ProjectInventoryEntry(
            path="游" * 171,
            category=ProjectInventoryCategory.SCENE,
        )
    with pytest.raises(ValueError, match="name is too large"):
        ProjectInventoryEntry(
            path="main.tscn",
            category=ProjectInventoryCategory.INPUT,
            name="游" * 86,
        )
    for invalid in (
        "/absolute",
        "a\\b",
        "a/../b",
        "a//b",
        "line\nbreak",
        "D:relative",
        "asset:stream",
        "trailing.",
        "trailing ",
        "CON",
        "CON .txt",
        "com1.txt",
        "LPT¹.log",
    ):
        with pytest.raises(ValueError):
            ProjectInventoryEntry(
                path=invalid,
                category=ProjectInventoryCategory.SCENE,
            )
        with pytest.raises(ValidationError):
            ProjectInventoryRequest(scope=invalid)
    with pytest.raises(ValueError, match="duplicated"):
        ProjectInventorySnapshot(
            engine_id="godot",
            entries=(entry, entry),
            statistics=_statistics(),
        )
    with pytest.raises(ValueError, match="statistic"):
        ProjectInventoryStatistics(
            visited_entries=-1,
            visited_directories=0,
            excluded_links=0,
            excluded_policy=0,
            unreadable=0,
            unclassified=0,
            complete=True,
        )


def test_request_defaults_and_boundaries_are_strict_and_immutable() -> None:
    request = ProjectInventoryRequest()

    assert request.limit == 32
    with pytest.raises(ValidationError):
        request.limit = 1
    assert ProjectInventoryRequest(limit=1).limit == 1
    assert (
        ProjectInventoryRequest(limit=MAX_PROJECT_INVENTORY_PAGE_ENTRIES).limit
        == MAX_PROJECT_INVENTORY_PAGE_ENTRIES
    )
    for invalid in (
        {"limit": 0},
        {"limit": MAX_PROJECT_INVENTORY_PAGE_ENTRIES + 1},
        {"categories": []},
        {"categories": ["scene", "scene"]},
        {"scope": "../game"},
        {"cursor": "not+base64"},
        {"extra": True},
    ):
        with pytest.raises(ValidationError):
            ProjectInventoryRequest.model_validate(invalid)


def test_result_requires_canonical_order_counts_and_cursor_truncation() -> None:
    result = _result()

    assert result.total_count == result.counts.selected_total(result.categories)
    with pytest.raises(ValidationError, match="not canonical"):
        _result(
            categories=(
                ProjectInventoryCategory.SCRIPT,
                ProjectInventoryCategory.SCENE,
            )
        )
    with pytest.raises(ValidationError, match="not sorted"):
        _result(entries=tuple(reversed(result.entries)))
    with pytest.raises(ValidationError, match="contradicts"):
        _result(total_count=3)
    with pytest.raises(ValidationError, match="truncation"):
        _result(truncated=True, next_cursor=None)
    truncated = _result(
        entries=(result.entries[0],),
        truncated=True,
        next_cursor=_CURSOR,
    )
    assert truncated.next_cursor == _CURSOR


def test_godot_format_has_matching_probe_and_inventory_identity() -> None:
    assert GODOT_PROJECT_FORMAT.engine_id == "godot"
    assert GODOT_PROJECT_FORMAT.project_probe.engine_id == "godot"
    assert GODOT_PROJECT_FORMAT.project_inventory_reader.engine_id == "godot"


def test_inventory_has_no_rest_route() -> None:
    paths = {
        route.path for route in build_router(build_container()).routes if hasattr(route, "path")
    }

    assert all("inventory" not in path for path in paths)
