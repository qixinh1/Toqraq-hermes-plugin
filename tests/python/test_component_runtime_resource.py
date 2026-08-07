"""Prepared component ownership transfer tests."""

from __future__ import annotations

import asyncio
from typing import cast

import pytest
from toqraq.components.lease import ComponentLease
from toqraq.components.mutation import ComponentMutation
from toqraq.components.runtime_resource import PreparedComponentResource
from toqraq.components.store import ComponentInstallation
from toqraq.core.resource import AsyncResource


class _Lease:
    def __init__(self) -> None:
        self.close_count = 0
        self.fail = True

    def close(self) -> None:
        self.close_count += 1
        if self.fail:
            self.fail = False
            raise OSError("deferred cleanup")


class _Mutation:
    def __init__(self, *, fail_once: bool = False) -> None:
        self.close_count = 0
        self.fail_once = fail_once

    def close(self) -> None:
        self.close_count += 1
        if self.fail_once:
            self.fail_once = False
            raise OSError("native mutation unlock failed")


def test_async_resource_observes_failure_and_retries_the_same_lease() -> None:
    lease = _Lease()
    mutation = _Mutation()
    resource = PreparedComponentResource(
        cast(ComponentLease[ComponentInstallation], lease),
        cast(ComponentMutation, mutation),
    )
    assert resource.release_mutation() is True

    assert isinstance(resource, AsyncResource)
    with pytest.raises(OSError):
        asyncio.run(resource.close())
    asyncio.run(resource.close())

    assert lease.close_count == 2
    assert mutation.close_count == 1


def test_failed_commit_release_retains_mutation_and_lease_for_ordered_retry() -> None:
    order: list[str] = []

    class Mutation(_Mutation):
        def close(self) -> None:
            order.append("mutation")
            super().close()

    class Lease(_Lease):
        fail = False

        def close(self) -> None:
            order.append("lease")
            self.close_count += 1

    mutation = Mutation(fail_once=True)
    lease = Lease()
    resource = PreparedComponentResource(
        cast(ComponentLease[ComponentInstallation], lease),
        cast(ComponentMutation, mutation),
    )

    assert resource.release_mutation() is False
    assert lease.close_count == 0

    asyncio.run(resource.close())
    asyncio.run(resource.close())

    assert order == ["mutation", "mutation", "lease", "lease"]
    assert mutation.close_count == 2
