"""Local verification and lease transfer for one certified Godot runtime."""

from __future__ import annotations

import logging
from threading import Event

from ...components.catalog import CertifiedComponentCatalog
from ...components.content import ComponentTreeCancelledError
from ...components.layout import ComponentStoreLayoutError
from ...components.lease import ComponentLease
from ...components.lock import (
    ComponentLockCancelledError,
    ComponentLockFileError,
    ComponentLockTimeoutError,
)
from ...components.mutation import (
    ComponentMutation,
    ComponentMutationOwner,
    ComponentMutationRejectedError,
)
from ...components.runtime_resource import PreparedComponentResource
from ...components.store import (
    ComponentInstallation,
    ComponentStore,
    ComponentStoreCancelledError,
    ComponentStoreRejectedError,
    ComponentStoreRejection,
)
from ...components.strategy import (
    ComponentStrategyCatalog,
    ComponentStrategyRejectedError,
)
from ...core.errors import (
    ComponentOperationError,
    ComponentOperationTimeoutError,
    ComponentReleaseInvalidError,
    ComponentReleaseNotFoundError,
    ComponentStorageError,
    RuntimeNotInstalledError,
    ToqraqError,
)
from ...core.runtime import (
    PreparedRuntime,
    RuntimeEntryPoint,
    RuntimeEntryPointBinding,
    RuntimePreparationCancelledError,
    RuntimeRelease,
)
from .identity import GODOT_EDITOR_ENTRY_POINT, GODOT_ENGINE_ID

logger = logging.getLogger(__name__)


class GodotRuntimeProvisioner:
    """Open the exact already-installed Godot component for one session."""

    def __init__(
        self,
        components: CertifiedComponentCatalog,
        store: ComponentStore,
        strategies: ComponentStrategyCatalog,
        mutations: ComponentMutationOwner,
    ) -> None:
        """Bind component storage, verification, and lease owners."""
        self._components = components
        self._store = store
        self._strategies = strategies
        self._mutations = mutations

    @property
    def engine_id(self) -> str:
        """Return the stable Godot contribution identifier."""
        return GODOT_ENGINE_ID

    def prepare(self, release: RuntimeRelease, cancellation: Event) -> PreparedRuntime:
        """Verify and lease this release without acquisition or reselection."""
        lease: ComponentLease[ComponentInstallation] | None = None
        resource: PreparedComponentResource | None = None
        mutation: ComponentMutation | None = None
        try:
            _require_not_cancelled(cancellation)
            component_release_id, binding = _godot_binding(release)
            component = self._components.require(component_release_id)
            strategy = self._strategies.resolve(component.install_strategy)
            self._store.initialize()
            mutation = self._mutations.acquire(
                component.identity,
                cancellation=cancellation,
            )
            installation = self._store.require(
                component,
                strategy.content_policy,
                cancellation=cancellation,
            )
            entry_point = RuntimeEntryPoint(
                name=binding.name,
                path=installation.entry_point(binding.component_entry_point_name),
            )
            _require_not_cancelled(cancellation)
            lease = self._store.acquire_lease(
                installation,
                mutation,
                cancellation=cancellation,
            )
            resource = PreparedComponentResource(lease, mutation)
            lease = None
            mutation = None
            if not resource.release_mutation():
                logger.warning(
                    "component mutation release deferred engine=%s version=%s",
                    GODOT_ENGINE_ID,
                    release.identity.version,
                )
            prepared = PreparedRuntime(
                release=release,
                entry_points=(entry_point,),
                owned_resources=(resource,),
            )
        except Exception as exc:
            cleanup = resource
            if cleanup is not None:
                try:
                    cleanup.close_blocking()
                except OSError as cleanup_error:
                    raise ComponentOperationError(
                        parameters={"engine": GODOT_ENGINE_ID},
                        details={"reason": "runtime_ownership_cleanup_failed"},
                        cause=cleanup_error,
                    ) from exc
            elif lease is not None:
                try:
                    lease.close()
                except OSError as cleanup_error:
                    raise ComponentOperationError(
                        parameters={"engine": GODOT_ENGINE_ID},
                        details={"reason": "runtime_lease_cleanup_failed"},
                        cause=cleanup_error,
                    ) from exc
            if mutation is not None:
                try:
                    mutation.close()
                except OSError as cleanup_error:
                    raise ComponentOperationError(
                        parameters={"engine": GODOT_ENGINE_ID},
                        details={"reason": "runtime_mutation_cleanup_failed"},
                        cause=cleanup_error,
                    ) from exc
            translated = _translate_prepare_failure(exc, release)
            if translated is exc:
                raise
            raise translated from exc
        return prepared


def _godot_binding(
    release: RuntimeRelease,
) -> tuple[str, RuntimeEntryPointBinding]:
    """Return the one exact component and editor binding certified for Godot."""
    if (
        release.identity.engine_id != GODOT_ENGINE_ID
        or len(release.component_release_ids) != 1
        or len(release.entry_point_bindings) != 1
    ):
        raise ComponentReleaseInvalidError(details={"reason": "runtime_release_shape_invalid"})
    binding = release.entry_point_bindings[0]
    component_release_id = release.component_release_ids[0]
    if (
        binding.name != GODOT_EDITOR_ENTRY_POINT
        or binding.component_release_id != component_release_id
    ):
        raise ComponentReleaseInvalidError(details={"reason": "runtime_entry_binding_invalid"})
    return component_release_id, binding


def _require_not_cancelled(cancellation: Event) -> None:
    """Stop before lease transfer when the owning start operation cancelled."""
    if cancellation.is_set():
        raise RuntimePreparationCancelledError


def _translate_prepare_failure(
    failure: BaseException,
    release: RuntimeRelease,
) -> BaseException:
    """Translate infrastructure failures once at the engine adapter boundary."""
    parameters = {
        "engine": GODOT_ENGINE_ID,
        "version": release.identity.version,
    }
    if isinstance(
        failure,
        (
            RuntimePreparationCancelledError,
            ComponentTreeCancelledError,
            ComponentStoreCancelledError,
        ),
    ):
        if isinstance(failure, RuntimePreparationCancelledError):
            return failure
        return RuntimePreparationCancelledError()
    if isinstance(failure, ComponentLockCancelledError):
        return RuntimePreparationCancelledError()
    if isinstance(failure, ComponentLockTimeoutError):
        return ComponentOperationTimeoutError(
            parameters=parameters,
            details={"reason": "runtime_lease_timeout"},
            cause=failure,
        )
    if isinstance(failure, ComponentReleaseNotFoundError):
        return ComponentReleaseInvalidError(
            parameters=parameters,
            details={"reason": "runtime_component_not_registered"},
            cause=failure,
        )
    if isinstance(failure, ComponentStrategyRejectedError):
        return ComponentReleaseInvalidError(
            parameters=parameters,
            details={"reason": "runtime_component_strategy_invalid"},
            cause=failure,
        )
    if isinstance(failure, (ComponentStoreLayoutError, ComponentLockFileError, OSError)):
        return ComponentStorageError(
            parameters=parameters,
            details={"reason": "runtime_store_unavailable"},
            cause=failure,
        )
    if isinstance(failure, ComponentStoreRejectedError):
        if failure.reason in {
            ComponentStoreRejection.INSTALLATION_INVALID,
            ComponentStoreRejection.ENTRY_POINT_MISSING,
        }:
            return RuntimeNotInstalledError(
                parameters=parameters,
                details={"reason": failure.reason.value},
                cause=failure,
            )
        return ComponentOperationError(
            parameters=parameters,
            details={"reason": failure.reason.value},
            cause=failure,
        )
    if isinstance(failure, ComponentMutationRejectedError):
        return ComponentReleaseInvalidError(
            parameters=parameters,
            details={"reason": "runtime_release_inconsistent"},
            cause=failure,
        )
    if isinstance(failure, ToqraqError):
        return failure
    if isinstance(failure, (ValueError, TypeError)):
        return ComponentReleaseInvalidError(
            parameters=parameters,
            details={"reason": "runtime_release_inconsistent"},
            cause=failure,
        )
    return failure
