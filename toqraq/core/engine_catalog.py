"""Immutable process-local catalog of complete engine contributions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import islice
from types import MappingProxyType

from .engine_contribution import EngineContribution
from .project_format_catalog import MAX_PROJECT_FORMATS

MAX_ENGINE_CONTRIBUTIONS = MAX_PROJECT_FORMATS


class EngineCatalog:
    """Explicit bounded lookup of fully composed engine contributions."""

    def __init__(self, contributions: Iterable[EngineContribution]) -> None:
        """Retain composition order and reject incomplete or duplicate entries."""
        selected = tuple(islice(contributions, MAX_ENGINE_CONTRIBUTIONS + 1))
        if len(selected) > MAX_ENGINE_CONTRIBUTIONS:
            raise ValueError("engine contribution catalog size is invalid")
        indexed: dict[str, EngineContribution] = {}
        for contribution in selected:
            if not isinstance(contribution, EngineContribution):
                raise ValueError("engine catalog entry is not a complete contribution")
            engine_id = contribution.engine_id
            if engine_id in indexed:
                raise ValueError("engine contribution identifier is duplicated")
            indexed[engine_id] = contribution
        self._contributions = selected
        self._by_id: Mapping[str, EngineContribution] = MappingProxyType(indexed)

    def list(self) -> tuple[EngineContribution, ...]:
        """Return complete contributions in explicit composition order."""
        return self._contributions

    def find(self, engine_id: str) -> EngineContribution | None:
        """Return the admitted contribution for one valid engine identity."""
        return self._by_id.get(engine_id)
