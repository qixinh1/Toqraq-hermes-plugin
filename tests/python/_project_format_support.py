"""Shared empty project-inventory port for non-inventory contract tests."""

from __future__ import annotations

from pathlib import Path
from threading import Event

from toqraq.core.project_inventory import (
    ProjectInventorySnapshot,
    ProjectInventoryStatistics,
)


class EmptyProjectInventoryReader:
    """Return one complete empty shape for a declared test engine."""

    def __init__(self, engine_id: str) -> None:
        self._engine_id = engine_id

    @property
    def engine_id(self) -> str:
        return self._engine_id

    def scan(
        self,
        project_root: Path,
        scope: str | None,
        cancellation: Event,
    ) -> ProjectInventorySnapshot:
        del project_root, scope, cancellation
        return ProjectInventorySnapshot(
            engine_id=self.engine_id,
            entries=(),
            statistics=ProjectInventoryStatistics(
                visited_entries=0,
                visited_directories=0,
                excluded_links=0,
                excluded_policy=0,
                unreadable=0,
                unclassified=0,
                complete=True,
            ),
        )
