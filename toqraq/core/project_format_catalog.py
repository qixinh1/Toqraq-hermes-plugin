"""Immutable catalog of side-effect-free engine project formats."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import islice
from types import MappingProxyType

from .engine_contribution import EngineProjectFormat
from .errors import EngineNotFoundError
from .runtime import validate_engine_id

MAX_PROJECT_FORMATS = 16


class ProjectFormatCatalog:
    """Bounded explicit lookup of project formats independent of runtime admission."""

    def __init__(self, formats: Iterable[EngineProjectFormat]) -> None:
        """Retain composition order and reject incomplete or duplicate entries."""
        selected = tuple(islice(formats, MAX_PROJECT_FORMATS + 1))
        if len(selected) > MAX_PROJECT_FORMATS:
            raise ValueError("project format catalog size is invalid")
        indexed: dict[str, EngineProjectFormat] = {}
        for project_format in selected:
            if not isinstance(project_format, EngineProjectFormat):
                raise ValueError("project format catalog entry is invalid")
            if project_format.engine_id in indexed:
                raise ValueError("project format identifier is duplicated")
            indexed[project_format.engine_id] = project_format
        self._formats = selected
        self._by_id: Mapping[str, EngineProjectFormat] = MappingProxyType(indexed)

    def list(self) -> tuple[EngineProjectFormat, ...]:
        """Return formats in explicit composition order."""
        return self._formats

    def find(self, engine_id: str) -> EngineProjectFormat | None:
        """Return a registered valid engine format or None."""
        return self._by_id.get(validate_engine_id(engine_id))

    def require(self, engine_id: str) -> EngineProjectFormat:
        """Return one explicitly selected format or raise a typed lookup failure."""
        try:
            canonical = validate_engine_id(engine_id)
        except (TypeError, ValueError) as exc:
            raise EngineNotFoundError(
                parameters={"engine": engine_id if isinstance(engine_id, str) else "invalid"},
                details={"reason": "invalid_identifier"},
                cause=exc,
            ) from exc
        try:
            return self._by_id[canonical]
        except KeyError as exc:
            raise EngineNotFoundError(
                parameters={"engine": canonical},
                details={"reason": "format_not_registered"},
            ) from exc
