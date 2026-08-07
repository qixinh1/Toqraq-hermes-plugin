"""Immutable catalog of explicitly registered component releases."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import islice
from types import MappingProxyType

from ..core.errors import ComponentReleaseInvalidError, ComponentReleaseNotFoundError
from .identity import component_identity_key
from .release import ComponentRelease

MAX_COMPONENT_RECORDS_PER_CATALOG = 256


class CertifiedComponentCatalog:
    """Immutable explicit release set certified by one plugin build."""

    def __init__(self, releases: Iterable[ComponentRelease]) -> None:
        """Index a bounded release set by its opaque complete-identity digest."""
        selected = tuple(islice(releases, MAX_COMPONENT_RECORDS_PER_CATALOG + 1))
        if len(selected) > MAX_COMPONENT_RECORDS_PER_CATALOG:
            raise ComponentReleaseInvalidError(details={"reason": "certified_record_set_too_large"})
        indexed: dict[str, ComponentRelease] = {}
        for release in selected:
            release_id = component_identity_key(release.identity)
            if release_id in indexed:
                raise ComponentReleaseInvalidError(
                    details={"reason": "duplicate_component_identity"}
                )
            indexed[release_id] = release
        self._releases = selected
        self._by_id: Mapping[str, ComponentRelease] = MappingProxyType(indexed)

    def list(self) -> tuple[ComponentRelease, ...]:
        """Return releases in explicit registration order."""
        return self._releases

    def release_id(self, release: ComponentRelease) -> str:
        """Return the public opaque identifier of a registered release."""
        release_id = component_identity_key(release.identity)
        if self._by_id.get(release_id) is not release:
            raise ComponentReleaseInvalidError(details={"reason": "release_not_registered"})
        return release_id

    def require(self, release_id: str) -> ComponentRelease:
        """Resolve one public identifier or raise a stable application failure."""
        try:
            return self._by_id[release_id]
        except KeyError as exc:
            raise ComponentReleaseNotFoundError(parameters={"release_id": release_id}) from exc
