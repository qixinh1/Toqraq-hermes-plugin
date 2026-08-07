"""Pure mapping from registered Godot components to exact runtime releases."""

from __future__ import annotations

from ...components.catalog import (
    MAX_COMPONENT_RECORDS_PER_CATALOG,
    CertifiedComponentCatalog,
)
from ...components.release import ComponentRelease
from ...core.capability_ids import (
    MANDATORY_BRIDGE_CAPABILITY_IDS,
    MANDATORY_ENGINE_CAPABILITY_IDS,
)
from ...core.component import ComponentKind
from ...core.engine_contribution import ProjectDescription
from ...core.errors import (
    ComponentReleaseInvalidError,
    ComponentReleaseNotFoundError,
    RuntimeReleaseNotFoundError,
)
from ...core.runtime import (
    RuntimeEntryPointBinding,
    RuntimeIdentity,
    RuntimeRelease,
)
from .identity import (
    GODOT_EDITOR_ENTRY_POINT,
    GODOT_ENGINE_ID,
    GODOT_RUNTIME_COMPONENT_ID,
    GODOT_RUNTIME_DISTRIBUTION_ID,
)

_SelectableKey = tuple[str, str, str, str]


class GodotRuntimeCatalog:
    """Immutable exact Godot releases backed by explicit component IDs."""

    def __init__(
        self,
        components: CertifiedComponentCatalog,
        runtime_component_release_ids: tuple[str, ...],
    ) -> None:
        """Validate and map only the component releases registered by Godot."""
        if not isinstance(components, CertifiedComponentCatalog):
            raise ComponentReleaseInvalidError(details={"reason": "component_catalog_invalid"})
        if (
            not isinstance(runtime_component_release_ids, tuple)
            or len(runtime_component_release_ids) > MAX_COMPONENT_RECORDS_PER_CATALOG
            or any(not isinstance(release_id, str) for release_id in runtime_component_release_ids)
        ):
            raise ComponentReleaseInvalidError(
                details={"reason": "runtime_component_registration_invalid"}
            )
        if len(set(runtime_component_release_ids)) != len(runtime_component_release_ids):
            raise ComponentReleaseInvalidError(
                details={"reason": "duplicate_runtime_component_registration"}
            )

        releases: list[RuntimeRelease] = []
        selectable_keys: set[_SelectableKey] = set()
        for release_id in runtime_component_release_ids:
            component = _registered_component(components, release_id)
            runtime = _map_runtime_release(release_id, component)
            selectable_key = _selectable_key(runtime.identity)
            if selectable_key in selectable_keys:
                raise ComponentReleaseInvalidError(details={"reason": "ambiguous_runtime_version"})
            releases.append(runtime)
            selectable_keys.add(selectable_key)

        self._releases = tuple(releases)

    @property
    def engine_id(self) -> str:
        """Return the stable Godot contribution identifier."""
        return GODOT_ENGINE_ID

    def releases(self, project: ProjectDescription) -> tuple[RuntimeRelease, ...]:
        """Return registered releases in explicit deterministic order."""
        if not isinstance(project, ProjectDescription) or project.engine_id != GODOT_ENGINE_ID:
            raise RuntimeReleaseNotFoundError(details={"reason": "engine_mismatch"})
        return self._releases


def _registered_component(
    catalog: CertifiedComponentCatalog,
    release_id: str,
) -> ComponentRelease:
    """Resolve one explicit registration as an internal catalog invariant."""
    try:
        return catalog.require(release_id)
    except ComponentReleaseNotFoundError as exc:
        raise ComponentReleaseInvalidError(
            details={"reason": "runtime_component_not_registered"},
            cause=exc,
        ) from exc


def _map_runtime_release(release_id: str, component: ComponentRelease) -> RuntimeRelease:
    """Map one complete instrumented Godot component without inferred facts."""
    if (
        component.kind is not ComponentKind.ENGINE
        or component.identity.component_id != GODOT_RUNTIME_COMPONENT_ID
    ):
        raise ComponentReleaseInvalidError(details={"reason": "runtime_component_mismatch"})
    if component.dependencies:
        raise ComponentReleaseInvalidError(
            details={"reason": "runtime_component_dependencies_not_registered"}
        )
    bridge = component.bridge
    if bridge is None:
        raise ComponentReleaseInvalidError(details={"reason": "runtime_bridge_missing"})
    entry_names = frozenset(entry.name for entry in component.entry_points)
    if GODOT_EDITOR_ENTRY_POINT not in entry_names:
        raise ComponentReleaseInvalidError(details={"reason": "runtime_entry_point_missing"})
    capabilities = frozenset(component.capabilities)
    if not MANDATORY_ENGINE_CAPABILITY_IDS.issubset(capabilities):
        raise ComponentReleaseInvalidError(
            details={"reason": "runtime_baseline_capabilities_missing"}
        )
    bridge_capabilities = frozenset(bridge.capabilities)
    if not MANDATORY_BRIDGE_CAPABILITY_IDS.issubset(bridge_capabilities):
        raise ComponentReleaseInvalidError(
            details={"reason": "runtime_bridge_capabilities_missing"}
        )
    try:
        identity = RuntimeIdentity(
            engine_id=GODOT_ENGINE_ID,
            version=component.identity.version,
            build_id=component.identity.build_id,
            distribution_id=GODOT_RUNTIME_DISTRIBUTION_ID,
            platform=component.identity.platform,
            architecture=component.identity.architecture,
        )
        return RuntimeRelease(
            identity=identity,
            component_release_ids=(release_id,),
            entry_point_bindings=(
                RuntimeEntryPointBinding(
                    name=GODOT_EDITOR_ENTRY_POINT,
                    component_release_id=release_id,
                    component_entry_point_name=GODOT_EDITOR_ENTRY_POINT,
                ),
            ),
            bridge_id=bridge.bridge_id,
            bridge_protocol=bridge.protocol,
            capability_ids=capabilities,
            bridge_capability_ids=bridge_capabilities,
        )
    except ValueError as exc:
        raise ComponentReleaseInvalidError(
            details={"reason": "runtime_identity_invalid"},
            cause=exc,
        ) from exc


def _selectable_key(identity: RuntimeIdentity) -> _SelectableKey:
    """Return the complete user-visible runtime choice identity."""
    return (
        identity.engine_id,
        identity.version,
        identity.platform,
        identity.architecture,
    )
