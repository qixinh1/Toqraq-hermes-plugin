"""Complete exact component preparation under one mutation owner."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import Event

from .content import ComponentTreeProgress
from .download import ComponentDownloader
from .download_models import (
    ComponentDownloadCancelledError,
    ComponentDownloadProgress,
    ComponentDownloadRejectedError,
)
from .identity import component_identity_key
from .layout import ComponentStoreLayout, ComponentStoreLayoutError
from .lock import (
    ComponentLockCancelledError,
    ComponentLockFileError,
    ComponentLockTimeoutError,
)
from .mutation import ComponentMutation, ComponentMutationOwner
from .provision_models import (
    ComponentProvisionCancelledError,
    ComponentProvisionPhase,
    ComponentProvisionProgress,
    ComponentProvisionRejectedError,
    ComponentProvisionRejection,
)
from .release import ComponentRelease
from .space import (
    ComponentSpacePhase,
    ComponentSpacePolicy,
    ComponentSpaceProbe,
    ComponentSpaceRejectedError,
    require_component_space,
)
from .staging import discard_component_staging
from .store import (
    ComponentInstallation,
    ComponentStore,
    ComponentStoreCancelledError,
    ComponentStoreRejectedError,
)
from .strategy import (
    ComponentInstallCancelledError,
    ComponentInstallProgress,
    ComponentInstallRejectedError,
    ComponentStrategyCatalog,
    ComponentStrategyRejectedError,
)


class ComponentProvisioner:
    """Prepare a certified component without exposing a partial installation."""

    def __init__(
        self,
        layout: ComponentStoreLayout,
        mutations: ComponentMutationOwner,
        downloader: ComponentDownloader,
        store: ComponentStore,
        strategies: ComponentStrategyCatalog,
        space_probe: ComponentSpaceProbe,
        space_policy: ComponentSpacePolicy,
    ) -> None:
        """Bind every concrete owner used by the preparation transaction."""
        self._layout = layout
        self._mutations = mutations
        self._downloader = downloader
        self._store = store
        self._strategies = strategies
        self._space_probe = space_probe
        self._space_policy = space_policy

    def prepare(
        self,
        release: ComponentRelease,
        *,
        cancellation: Event | None = None,
        progress: Callable[[ComponentProvisionProgress], None] | None = None,
    ) -> ComponentInstallation:
        """Prepare or repair one exact release with a single atomic commit point."""
        try:
            strategy = self._strategies.resolve(release.install_strategy)
        except ComponentStrategyRejectedError as exc:
            raise ComponentProvisionRejectedError(
                ComponentProvisionRejection.STRATEGY_UNAVAILABLE,
                cause=exc,
            ) from exc
        try:
            self._store.initialize()
            _notify(progress, ComponentProvisionPhase.CHECKING, 0, 0)
            mutation = self._mutations.acquire(
                release.identity,
                cancellation=cancellation,
            )
        except ComponentLockCancelledError as exc:
            raise ComponentProvisionCancelledError from exc
        except ComponentLockTimeoutError as exc:
            raise ComponentProvisionRejectedError(
                ComponentProvisionRejection.OWNERSHIP_TIMEOUT,
                cause=exc,
            ) from exc
        except (ComponentLockFileError, ComponentStoreLayoutError, OSError) as exc:
            raise ComponentProvisionRejectedError(
                ComponentProvisionRejection.OWNERSHIP_FAILED,
                cause=exc,
            ) from exc

        staging: Path | None = None
        committed = False
        identity_key = component_identity_key(release.identity)
        try:
            with mutation:
                ready = self._store.find(release, strategy.content_policy)
                if ready is not None:
                    _notify(
                        progress,
                        ComponentProvisionPhase.READY,
                        release.installed_bytes,
                        release.installed_bytes,
                    )
                    return ready
                _require_not_cancelled(cancellation)
                self._download(
                    release,
                    mutation,
                    cancellation,
                    progress,
                )
                _require_not_cancelled(cancellation)
                require_component_space(
                    self._space_probe,
                    self._space_policy,
                    self._layout.staging,
                    release.installed_bytes,
                    ComponentSpacePhase.INSTALL,
                )
                staging = self._layout.create_staging(release.identity)
                strategy.install(
                    self._layout.download_path(release.identity),
                    staging,
                    release,
                    cancellation=cancellation,
                    progress=_install_observer(progress, release.installed_bytes),
                )
                _require_not_cancelled(cancellation)
                _notify(
                    progress,
                    ComponentProvisionPhase.VERIFYING,
                    0,
                    release.installed_bytes,
                )
                installation = self._store.publish_staging(
                    staging,
                    release,
                    strategy.content_policy,
                    mutation,
                    cancellation=cancellation,
                    progress=_verification_observer(progress, release.installed_bytes),
                )
                committed = True
                _notify(
                    progress,
                    ComponentProvisionPhase.READY,
                    release.installed_bytes,
                    release.installed_bytes,
                )
                return installation
        except (
            ComponentDownloadCancelledError,
            ComponentInstallCancelledError,
            ComponentStoreCancelledError,
        ) as exc:
            raise ComponentProvisionCancelledError from exc
        except ComponentSpaceRejectedError as exc:
            raise ComponentProvisionRejectedError(
                ComponentProvisionRejection.STORAGE_UNAVAILABLE,
                cause=exc,
            ) from exc
        except ComponentDownloadRejectedError as exc:
            raise ComponentProvisionRejectedError(
                ComponentProvisionRejection.DOWNLOAD_FAILED,
                cause=exc,
            ) from exc
        except ComponentInstallRejectedError as exc:
            raise ComponentProvisionRejectedError(
                ComponentProvisionRejection.INSTALL_FAILED,
                cause=exc,
            ) from exc
        except ComponentStoreRejectedError as exc:
            raise ComponentProvisionRejectedError(
                ComponentProvisionRejection.PUBLICATION_FAILED,
                cause=exc,
            ) from exc
        except OSError as exc:
            raise ComponentProvisionRejectedError(
                (
                    ComponentProvisionRejection.OWNERSHIP_FAILED
                    if committed
                    else ComponentProvisionRejection.INSTALL_FAILED
                ),
                cause=exc,
            ) from exc
        finally:
            if staging is not None:
                discard_component_staging(staging, self._layout.staging, identity_key)

    def _download(
        self,
        release: ComponentRelease,
        mutation: ComponentMutation,
        cancellation: Event | None,
        progress: Callable[[ComponentProvisionProgress], None] | None,
    ) -> None:
        """Acquire exact package bytes and preflight only the missing allocation."""
        self._downloader.download(
            release,
            mutation,
            cancellation=cancellation,
            progress=_download_observer(progress),
            require_capacity=lambda missing: require_component_space(
                self._space_probe,
                self._space_policy,
                self._layout.downloads,
                missing,
                ComponentSpacePhase.DOWNLOAD,
            ),
        )


def _require_not_cancelled(cancellation: Event | None) -> None:
    """Reject cancellation at an orchestration boundary before publication."""
    if cancellation is not None and cancellation.is_set():
        raise ComponentProvisionCancelledError


def _notify(
    observer: Callable[[ComponentProvisionProgress], None] | None,
    phase: ComponentProvisionPhase,
    completed: int,
    total: int,
) -> None:
    """Publish one immutable provision snapshot when observed."""
    if observer is not None:
        observer(ComponentProvisionProgress(phase, completed, total))


def _download_observer(
    observer: Callable[[ComponentProvisionProgress], None] | None,
) -> Callable[[ComponentDownloadProgress], None] | None:
    """Adapt exact package progress into the common provision phase."""
    if observer is None:
        return None

    def notify(value: ComponentDownloadProgress) -> None:
        _notify(
            observer,
            ComponentProvisionPhase.DOWNLOADING,
            value.completed_bytes,
            value.total_bytes,
        )

    return notify


def _install_observer(
    observer: Callable[[ComponentProvisionProgress], None] | None,
    certified_total: int,
) -> Callable[[ComponentInstallProgress], None] | None:
    """Bound package-declared extraction progress to the certified total."""
    if observer is None:
        return None

    def notify(value: ComponentInstallProgress) -> None:
        _notify(
            observer,
            ComponentProvisionPhase.INSTALLING,
            min(value.completed_bytes, certified_total),
            certified_total,
        )

    return notify


def _verification_observer(
    observer: Callable[[ComponentProvisionProgress], None] | None,
    certified_total: int,
) -> Callable[[ComponentTreeProgress], None] | None:
    """Adapt exact tree hashing progress into the certified verification total."""
    if observer is None:
        return None

    def notify(value: ComponentTreeProgress) -> None:
        _notify(
            observer,
            ComponentProvisionPhase.VERIFYING,
            min(value.completed_bytes, certified_total),
            certified_total,
        )

    return notify
