"""Application-port adapters over certified component infrastructure."""

from __future__ import annotations

from collections.abc import Callable
from threading import Event
from types import MappingProxyType

from ..core.component import (
    ComponentLicense,
    ComponentReadiness,
    ComponentSource,
    ComponentWorkCancelledError,
    ComponentWorkPhase,
    ComponentWorkProgress,
    ManagedComponent,
)
from ..core.errors import (
    ComponentDownloadError,
    ComponentInstallError,
    ComponentInUseError,
    ComponentOperationError,
    ComponentOperationTimeoutError,
    ComponentPublicationError,
    ComponentReleaseInvalidError,
    ComponentStorageError,
    ToqraqError,
)
from .catalog import CertifiedComponentCatalog
from .layout import ComponentStoreLayoutError
from .lock import (
    ComponentLockCancelledError,
    ComponentLockFileError,
    ComponentLockTimeoutError,
)
from .mutation import ComponentMutationOwner
from .provision_models import (
    ComponentProvisionCancelledError,
    ComponentProvisionPhase,
    ComponentProvisionProgress,
    ComponentProvisionRejectedError,
    ComponentProvisionRejection,
)
from .provisioner import ComponentProvisioner
from .release import ComponentRelease
from .store import (
    ComponentStore,
    ComponentStoreCancelledError,
    ComponentStoreRejectedError,
    ComponentStoreRejection,
)
from .strategy import ComponentStrategyCatalog, ComponentStrategyRejectedError

_PREPARE_PHASES = MappingProxyType(
    {
        ComponentProvisionPhase.CHECKING: ComponentWorkPhase.CHECKING,
        ComponentProvisionPhase.DOWNLOADING: ComponentWorkPhase.DOWNLOADING,
        ComponentProvisionPhase.INSTALLING: ComponentWorkPhase.INSTALLING,
        ComponentProvisionPhase.VERIFYING: ComponentWorkPhase.VERIFYING,
        ComponentProvisionPhase.READY: ComponentWorkPhase.READY,
    }
)
_PROVISION_ERRORS: MappingProxyType[ComponentProvisionRejection, type[ToqraqError]] = (
    MappingProxyType(
        {
            ComponentProvisionRejection.STRATEGY_UNAVAILABLE: ComponentReleaseInvalidError,
            ComponentProvisionRejection.STORAGE_UNAVAILABLE: ComponentStorageError,
            ComponentProvisionRejection.DOWNLOAD_FAILED: ComponentDownloadError,
            ComponentProvisionRejection.INSTALL_FAILED: ComponentInstallError,
            ComponentProvisionRejection.PUBLICATION_FAILED: ComponentPublicationError,
            ComponentProvisionRejection.OWNERSHIP_TIMEOUT: ComponentOperationTimeoutError,
            ComponentProvisionRejection.OWNERSHIP_FAILED: ComponentOperationError,
        }
    )
)


class CertifiedComponentInventory:
    """Read certified component metadata and authoritative managed readiness."""

    def __init__(
        self,
        catalog: CertifiedComponentCatalog,
        store: ComponentStore,
        strategies: ComponentStrategyCatalog,
    ) -> None:
        """Bind explicit release, storage, and verification policy owners."""
        self._catalog = catalog
        self._store = store
        self._strategies = strategies

    def list_components(self) -> tuple[ManagedComponent, ...]:
        """Return every registered release in deterministic catalog order."""
        self._initialize_store()
        return tuple(self._managed(release) for release in self._catalog.list())

    def require_component(self, release_id: str) -> ManagedComponent:
        """Return one registered release with its current readiness."""
        self._initialize_store()
        return self._managed(self._catalog.require(release_id))

    def _managed(self, release: ComponentRelease) -> ManagedComponent:
        """Translate a certified record without exposing infrastructure values."""
        try:
            strategy = self._strategies.resolve(release.install_strategy)
        except ComponentStrategyRejectedError as exc:
            raise ComponentReleaseInvalidError(
                parameters={"component_id": release.identity.component_id},
                details={"reason": "install_strategy_unavailable"},
                cause=exc,
            ) from exc
        try:
            readiness = self._store.readiness(release, strategy.content_policy)
            in_use = self._store.is_leased(release)
        except (ComponentStoreRejectedError, OSError) as exc:
            raise ComponentStorageError(
                parameters={"component_id": release.identity.component_id},
                details={"reason": "readiness_failed"},
                cause=exc,
            ) from exc
        return _managed_component(
            self._catalog.release_id(release),
            release,
            readiness,
            in_use,
        )

    def _initialize_store(self) -> None:
        """Translate private layout failures at the application boundary."""
        try:
            self._store.initialize()
        except (ComponentStoreLayoutError, OSError) as exc:
            raise ComponentStorageError(
                details={"reason": "store_unavailable"},
                cause=exc,
            ) from exc


class CertifiedComponentPreparation:
    """Prepare one registered release and translate infrastructure failures."""

    def __init__(
        self,
        catalog: CertifiedComponentCatalog,
        provisioner: ComponentProvisioner,
    ) -> None:
        """Bind exact release selection to the complete provision transaction."""
        self._catalog = catalog
        self._provisioner = provisioner

    def prepare_component(
        self,
        release_id: str,
        cancellation: Event,
        progress: Callable[[ComponentWorkProgress], None],
    ) -> None:
        """Prepare or repair one release, preserving cancellation semantics."""
        release = self._catalog.require(release_id)
        phase = ComponentProvisionPhase.CHECKING

        def observe(value: ComponentProvisionProgress) -> None:
            nonlocal phase
            phase = value.phase
            progress(
                ComponentWorkProgress(
                    _PREPARE_PHASES[value.phase],
                    value.completed_bytes,
                    value.total_bytes,
                )
            )

        try:
            self._provisioner.prepare(
                release,
                cancellation=cancellation,
                progress=observe,
            )
        except ComponentProvisionCancelledError as exc:
            raise ComponentWorkCancelledError from exc
        except ComponentProvisionRejectedError as exc:
            error_type = _PROVISION_ERRORS[exc.reason]
            raise error_type(
                parameters={"release_id": release_id},
                details={"reason": exc.reason.value, "phase": phase.value},
                cause=exc,
            ) from exc


class CertifiedComponentRemoval:
    """Remove one registered unleased component under exact mutation ownership."""

    def __init__(
        self,
        catalog: CertifiedComponentCatalog,
        store: ComponentStore,
        mutations: ComponentMutationOwner,
    ) -> None:
        """Bind release lookup, store mutation, and cross-process ownership."""
        self._catalog = catalog
        self._store = store
        self._mutations = mutations

    def remove_component(
        self,
        release_id: str,
        cancellation: Event,
        progress: Callable[[ComponentWorkProgress], None],
    ) -> None:
        """Remove an exact component or complete idempotently when absent."""
        release = self._catalog.require(release_id)
        progress(ComponentWorkProgress(ComponentWorkPhase.CHECKING, 0, 0))
        try:
            self._store.initialize()
            mutation = self._mutations.acquire(
                release.identity,
                cancellation=cancellation,
            )
            with mutation:
                if cancellation.is_set():
                    raise ComponentStoreCancelledError
                progress(ComponentWorkProgress(ComponentWorkPhase.REMOVING, 0, 0))
                self._store.remove(
                    release.identity,
                    mutation,
                    cancellation=cancellation,
                )
        except (ComponentLockCancelledError, ComponentStoreCancelledError) as exc:
            raise ComponentWorkCancelledError from exc
        except ComponentLockTimeoutError as exc:
            raise ComponentOperationTimeoutError(
                parameters={"release_id": release_id},
                details={"reason": "ownership_timeout"},
                cause=exc,
            ) from exc
        except ComponentStoreRejectedError as exc:
            raise _removal_error(release_id, exc) from exc
        except (ComponentStoreLayoutError, ComponentLockFileError, OSError) as exc:
            raise ComponentOperationError(
                parameters={"release_id": release_id},
                details={"reason": "removal_failed"},
                cause=exc,
            ) from exc


def _removal_error(
    release_id: str,
    failure: ComponentStoreRejectedError,
) -> ToqraqError:
    """Map every stable store rejection to one application failure family."""
    parameters = {"release_id": release_id}
    details = {"reason": failure.reason.value}
    if failure.reason is ComponentStoreRejection.COMPONENT_IN_USE:
        return ComponentInUseError(parameters=parameters, details=details, cause=failure)
    if failure.reason is ComponentStoreRejection.PUBLICATION_FAILED:
        return ComponentPublicationError(parameters=parameters, details=details, cause=failure)
    return ComponentOperationError(parameters=parameters, details=details, cause=failure)


def _managed_component(
    release_id: str,
    release: ComponentRelease,
    readiness: ComponentReadiness,
    in_use: bool,
) -> ManagedComponent:
    """Convert one strict infrastructure record to its pure application value."""
    return ManagedComponent(
        release_id=release_id,
        component_id=release.identity.component_id,
        kind=release.kind,
        label=release.label,
        version=release.identity.version,
        build_id=release.identity.build_id,
        platform=release.identity.platform,
        architecture=release.identity.architecture,
        package_bytes=release.package_bytes,
        installed_bytes=release.installed_bytes,
        package_sha256=release.identity.package_sha256,
        source=ComponentSource(
            publisher=release.source.publisher,
            package_url=release.source.package_url,
            provenance_url=release.source.provenance_url,
        ),
        license=ComponentLicense(
            identifier=release.license.identifier,
            name=release.license.name,
            url=release.license.url,
            acceptance_required=release.license.acceptance_required,
        ),
        authentication_required=release.authentication_required,
        capabilities=release.capabilities,
        readiness=readiness,
        in_use=in_use,
    )
