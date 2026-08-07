from __future__ import annotations

import threading
from pathlib import Path
from typing import cast

import pytest
from toqraq.components.identity import component_identity_key
from toqraq.components.layout import ComponentStoreLayout
from toqraq.components.lock import (
    ComponentFileLock,
    ComponentLockCancelledError,
    ComponentLockPolicy,
    ComponentLockTimeoutError,
)
from toqraq.components.mutation import (
    ComponentMutation,
    ComponentMutationOwner,
    ComponentMutationRejectedError,
    ComponentMutationRejection,
)
from toqraq.components.release import ComponentIdentity

_LOCK_POLICY = ComponentLockPolicy(timeout_seconds=0.1, poll_seconds=0.01)


def _identity(digest: str = "1" * 64) -> ComponentIdentity:
    return ComponentIdentity.model_validate(
        {
            "component_id": "engine.godot",
            "version": "4.7.1-stable",
            "build_id": "toqraq.windows.x86_64.release",
            "platform": "windows",
            "architecture": "x86_64",
            "package_sha256": digest,
        }
    )


def _owner(tmp_path: Path) -> ComponentMutationOwner:
    layout = ComponentStoreLayout(tmp_path / "toqraq")
    layout.initialize()
    return ComponentMutationOwner(layout, _LOCK_POLICY)


def test_mutation_authorizes_only_its_exact_identity_while_live(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    mutation = owner.acquire(_identity())

    mutation.require(_identity())
    with pytest.raises(ComponentMutationRejectedError) as mismatch:
        mutation.require(_identity("2" * 64))
    assert mismatch.value.reason is ComponentMutationRejection.IDENTITY_MISMATCH

    mutation.close()
    mutation.close()
    with pytest.raises(ComponentMutationRejectedError) as closed:
        mutation.require(_identity())
    assert closed.value.reason is ComponentMutationRejection.CLOSED


def test_mutation_serializes_the_complete_identity_transaction(tmp_path: Path) -> None:
    owner = _owner(tmp_path)

    with owner.acquire(_identity()), pytest.raises(ComponentLockTimeoutError):
        owner.acquire(_identity())

    with owner.acquire(_identity()) as next_owner:
        next_owner.require(_identity())


def test_mutation_wait_observes_owner_cancellation(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    cancellation = threading.Event()
    cancellation.set()

    with pytest.raises(ComponentLockCancelledError):
        owner.acquire(_identity(), cancellation=cancellation)


def test_context_releases_mutation_after_an_operation_failure(tmp_path: Path) -> None:
    owner = _owner(tmp_path)

    with pytest.raises(RuntimeError, match="operation failed"), owner.acquire(_identity()):
        raise RuntimeError("operation failed")

    with owner.acquire(_identity()) as next_owner:
        next_owner.require(_identity())


def test_mutation_retains_failed_lock_release_for_idempotent_retry() -> None:
    class Lock:
        release_count = 0

        def release(self) -> None:
            self.release_count += 1
            if self.release_count == 1:
                raise OSError("native unlock failed")

    identity = _identity()
    lock = Lock()
    mutation = ComponentMutation(
        component_identity_key(identity),
        cast(ComponentFileLock, lock),
    )

    with pytest.raises(OSError):
        mutation.close()
    mutation.require(identity)

    mutation.close()
    mutation.close()
    assert lock.release_count == 2
    with pytest.raises(ComponentMutationRejectedError) as closed:
        mutation.require(identity)
    assert closed.value.reason is ComponentMutationRejection.CLOSED
