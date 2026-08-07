from __future__ import annotations

import multiprocessing
import os
from pathlib import Path
from typing import Any, cast

import pytest
from toqraq.components.layout import ComponentStoreLayout
from toqraq.components.lease import ComponentLease
from toqraq.components.lock import ComponentFileLock
from toqraq.components.mutation import ComponentMutationOwner
from toqraq.components.release import ComponentRelease
from toqraq.components.store import (
    ComponentInstallation,
    ComponentStore,
    ComponentStoreRejectedError,
    ComponentStoreRejection,
)

from test_component_store import (
    _LOCK_POLICY,
    _POLICY,
    _prepare,
    _publish,
    _remove,
    _store,
)


def _lease(
    layout: ComponentStoreLayout,
    store: ComponentStore,
    release: ComponentRelease,
) -> ComponentLease[ComponentInstallation]:
    with ComponentMutationOwner(layout, _LOCK_POLICY).acquire(release.identity) as mutation:
        installation = store.require(release, _POLICY)
        return store.acquire_lease(installation, mutation)


def _lease_process(
    root: str,
    release_json: str,
    ready: Any,
    release_signal: Any,
    crash: bool,
) -> None:
    layout = ComponentStoreLayout(Path(root))
    store = ComponentStore(layout, _LOCK_POLICY)
    store.initialize()
    release = ComponentRelease.model_validate_json(release_json)
    lease = _lease(layout, store, release)
    ready.put("leased")
    ready.close()
    ready.join_thread()
    if crash:
        os._exit(0)
    release_signal.wait(10)
    lease.close()


def test_live_lease_blocks_removal_until_idempotent_release(tmp_path: Path) -> None:
    layout, store = _store(tmp_path / "toqraq")
    staging, release = _prepare(layout)
    _publish(layout, store, staging, release)

    assert store.is_leased(release) is False
    lease = _lease(layout, store, release)
    assert store.is_leased(release) is True
    with pytest.raises(ComponentStoreRejectedError) as captured:
        _remove(layout, store, release.identity)
    assert captured.value.reason is ComponentStoreRejection.COMPONENT_IN_USE

    lease.close()
    lease.close()
    assert store.is_leased(release) is False
    assert _remove(layout, store, release.identity) is True
    assert _remove(layout, store, release.identity) is False
    assert store.find(release, _POLICY) is None


def test_lease_context_owns_the_exact_verified_installation(tmp_path: Path) -> None:
    layout, store = _store(tmp_path / "toqraq")
    staging, release = _prepare(layout)
    installed = _publish(layout, store, staging, release)

    with _lease(layout, store, release) as lease:
        assert lease.installation == installed
        assert any(".lease." in path.name for path in layout.locks.iterdir())

    assert not any(".lease." in path.name for path in layout.locks.iterdir())


def test_lease_cleanup_failure_is_observed_and_receipt_cleanup_can_retry() -> None:
    class Lock:
        release_count = 0

        def release(self) -> None:
            self.release_count += 1

    class Receipt:
        unlink_count = 0

        def unlink(self, *, missing_ok: bool) -> None:
            assert missing_ok is True
            self.unlink_count += 1
            if self.unlink_count == 1:
                raise OSError("receipt busy")

    lock = Lock()
    receipt = Receipt()
    lease = ComponentLease(
        "installation",
        cast(ComponentFileLock, lock),
        cast(Path, receipt),
    )

    with pytest.raises(OSError):
        lease.close()
    lease.close()
    lease.close()

    assert lock.release_count == 1
    assert receipt.unlink_count == 2


def test_lease_retains_lock_and_receipt_until_native_release_can_retry() -> None:
    class Lock:
        release_count = 0

        def release(self) -> None:
            self.release_count += 1
            if self.release_count == 1:
                raise OSError("native unlock failed")

    class Receipt:
        unlink_count = 0

        def unlink(self, *, missing_ok: bool) -> None:
            assert missing_ok is True
            self.unlink_count += 1

    lock = Lock()
    receipt = Receipt()
    lease = ComponentLease(
        "installation",
        cast(ComponentFileLock, lock),
        cast(Path, receipt),
    )

    with pytest.raises(OSError):
        lease.close()
    assert lock.release_count == 1
    assert receipt.unlink_count == 0

    lease.close()
    lease.close()
    assert lock.release_count == 2
    assert receipt.unlink_count == 1


def test_lease_in_another_process_blocks_removal(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    layout, store = _store(tmp_path / "toqraq")
    staging, release = _prepare(layout)
    _publish(layout, store, staging, release)
    ready = context.Queue()
    release_signal = context.Event()
    process = context.Process(
        target=_lease_process,
        args=(
            str(layout.root),
            release.model_dump_json(),
            ready,
            release_signal,
            False,
        ),
    )
    process.start()
    assert ready.get(timeout=10) == "leased"

    with pytest.raises(ComponentStoreRejectedError) as captured:
        _remove(layout, store, release.identity)
    assert captured.value.reason is ComponentStoreRejection.COMPONENT_IN_USE

    release_signal.set()
    process.join(timeout=10)
    assert process.exitcode == 0
    assert _remove(layout, store, release.identity) is True


def test_crashed_process_lease_is_reclaimed_before_removal(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    layout, store = _store(tmp_path / "toqraq")
    staging, release = _prepare(layout)
    _publish(layout, store, staging, release)
    ready = context.Queue()
    unused_signal = context.Event()
    process = context.Process(
        target=_lease_process,
        args=(
            str(layout.root),
            release.model_dump_json(),
            ready,
            unused_signal,
            True,
        ),
    )
    process.start()
    assert ready.get(timeout=10) == "leased"
    process.join(timeout=10)
    assert process.exitcode == 0
    assert any(".lease." in path.name for path in layout.locks.iterdir())

    assert _remove(layout, store, release.identity) is True

    assert not any(".lease." in path.name for path in layout.locks.iterdir())
