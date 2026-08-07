"""CAS and cross-loop safety tests for active session ownership."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from toqraq.core.errors import SessionNotFoundError, SessionStateError
from toqraq.core.session_registry import SessionRegistry

from _session_domain_support import make_session


def test_owner_revisions_are_monotonic_per_hermes_session() -> None:
    registry = SessionRegistry()

    first = registry.issue_owner("session-a")
    second = registry.issue_owner("session-a")
    other = registry.issue_owner("session-b")

    assert (first.run_revision, second.run_revision) == (1, 2)
    assert other.run_revision == 1
    assert first.session_id == second.session_id == "session-a"


def test_only_latest_issued_run_can_commit(tmp_path) -> None:
    registry = SessionRegistry()
    stale_owner = registry.issue_owner("session-a")
    current_owner = registry.issue_owner("session-a")
    stale, *_ = make_session(tmp_path, stale_owner)
    current, *_ = make_session(tmp_path, current_owner)

    assert not registry.compare_and_swap(None, stale)
    assert registry.compare_and_swap(None, current)
    assert registry.get("session-a") is current


def test_observed_owner_lookup_rejects_a_replacement_run(tmp_path) -> None:
    registry = SessionRegistry()
    stale_owner = registry.issue_owner("session-a")
    current_owner = registry.issue_owner("session-a")
    current, *_ = make_session(tmp_path, current_owner)
    assert registry.compare_and_swap(None, current)

    with pytest.raises(SessionStateError) as captured:
        registry.get_owned(stale_owner)

    assert captured.value.parameters == {"session_id": "session-a"}
    assert captured.value.details == {
        "reason": "run_replaced",
        "expected_run_revision": stale_owner.run_revision,
        "current_run_revision": current_owner.run_revision,
        "retryable": True,
    }
    assert registry.get_owned(current_owner) is current


def test_replacement_compares_exact_object_not_equal_owner_facts(tmp_path) -> None:
    registry = SessionRegistry()
    first_owner = registry.issue_owner("session-a")
    first, *_ = make_session(tmp_path, first_owner)
    equivalent_but_stale, *_ = make_session(tmp_path, first_owner)
    assert registry.compare_and_swap(None, first)
    asyncio.run(first.close())

    replacement_owner = registry.issue_owner("session-a")
    replacement, *_ = make_session(tmp_path, replacement_owner)

    assert not registry.compare_and_swap(equivalent_but_stale, replacement)
    assert registry.get("session-a") is first
    assert registry.compare_and_swap(first, replacement)
    assert registry.get("session-a") is replacement


def test_compare_and_swap_never_overwrites_an_unexpected_owner(tmp_path) -> None:
    registry = SessionRegistry()
    first_owner = registry.issue_owner("session-a")
    first, *_ = make_session(tmp_path, first_owner)
    assert registry.compare_and_swap(None, first)

    second_owner = registry.issue_owner("session-a")
    second, *_ = make_session(tmp_path, second_owner)

    assert not registry.compare_and_swap(None, second)
    assert registry.get("session-a") is first


def test_live_or_failed_cleanup_owner_cannot_be_replaced_or_discarded(tmp_path) -> None:
    registry = SessionRegistry()
    first, *_ = make_session(
        tmp_path,
        registry.issue_owner("session-a"),
        process_close_failures=1,
    )
    assert registry.compare_and_swap(None, first)
    replacement, *_ = make_session(tmp_path, registry.issue_owner("session-a"))

    assert not registry.compare_and_swap(first, replacement)
    assert not registry.discard_if(first)
    assert registry.get("session-a") is first

    async def settle_cleanup() -> None:
        with pytest.raises(ExceptionGroup):
            await first.close()
        assert not registry.compare_and_swap(first, replacement)
        assert not registry.discard_if(first)
        await first.close()

    asyncio.run(settle_cleanup())
    assert registry.compare_and_swap(first, replacement)


def test_discard_requires_exact_current_object_and_preserves_revision_history(tmp_path) -> None:
    registry = SessionRegistry()
    owner = registry.issue_owner("session-a")
    current, *_ = make_session(tmp_path, owner)
    stale, *_ = make_session(tmp_path, owner)
    assert registry.compare_and_swap(None, current)
    asyncio.run(current.close())

    assert not registry.discard_if(stale)
    assert registry.find("session-a") is current
    assert registry.discard_if(current)
    assert registry.find("session-a") is None
    assert not registry.discard_if(current)
    assert registry.issue_owner("session-a").run_revision == 2
    with pytest.raises(SessionNotFoundError):
        registry.get("session-a")


def test_finalization_releases_an_idle_identity_revision_record() -> None:
    registry = SessionRegistry()
    assert registry.issue_owner("session-a").run_revision == 1

    registry.finalize("session-a")

    assert registry.issue_owner("session-a").run_revision == 1


def test_finalization_retains_an_active_owner_for_retry(tmp_path) -> None:
    registry = SessionRegistry()
    owner = registry.issue_owner("session-a")
    session, *_ = make_session(tmp_path, owner)
    assert registry.compare_and_swap(None, session)

    with pytest.raises(SessionStateError) as captured:
        registry.finalize("session-a")

    assert captured.value.details == {
        "reason": "finalization_owner_remains",
        "retryable": True,
    }
    asyncio.run(session.close())


def test_registry_returns_an_immutable_point_in_time_tuple(tmp_path) -> None:
    registry = SessionRegistry()
    first, *_ = make_session(tmp_path, registry.issue_owner("session-a"))
    second, *_ = make_session(tmp_path, registry.issue_owner("session-b"))
    assert registry.compare_and_swap(None, first)
    assert registry.compare_and_swap(None, second)

    snapshot = registry.sessions()
    assert snapshot == (first, second)
    assert isinstance(snapshot, tuple)
    asyncio.run(first.close())
    assert registry.discard_if(first)
    assert snapshot == (first, second)
    assert registry.sessions() == (second,)


def test_revision_issuance_is_safe_across_concurrent_host_event_loops() -> None:
    registry = SessionRegistry()

    async def issue_many() -> tuple[int, ...]:
        await asyncio.sleep(0)
        return tuple(registry.issue_owner("shared-session").run_revision for _ in range(32))

    def host_loop() -> tuple[int, ...]:
        return asyncio.run(issue_many())

    with ThreadPoolExecutor(max_workers=4) as executor:
        batches = tuple(executor.map(lambda _index: host_loop(), range(4)))

    revisions = sorted(revision for batch in batches for revision in batch)
    assert revisions == list(range(1, 129))


def test_cross_loop_cas_and_finalize_cannot_both_displace_the_same_owner(tmp_path) -> None:
    registry = SessionRegistry()
    current, *_ = make_session(tmp_path, registry.issue_owner("session-a"))
    assert registry.compare_and_swap(None, current)
    replacement, *_ = make_session(tmp_path, registry.issue_owner("session-a"))
    asyncio.run(current.close())
    barrier = Barrier(2)

    async def call(operation: Callable[[], bool]) -> bool:
        barrier.wait(timeout=2)
        await asyncio.sleep(0)
        return operation()

    def host_loop(operation: Callable[[], bool]) -> bool:
        return asyncio.run(call(operation))

    operations = (
        lambda: registry.compare_and_swap(current, replacement),
        lambda: registry.discard_if(current),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(host_loop, operations))

    assert sum(outcomes) == 1
    assert registry.find("session-a") in {None, replacement}


def test_registry_rejects_a_replacement_closed_before_commit(tmp_path) -> None:
    registry = SessionRegistry()
    replacement, *_ = make_session(tmp_path, registry.issue_owner("session-a"))
    asyncio.run(replacement.close())

    assert not registry.compare_and_swap(None, replacement)
    assert registry.find("session-a") is None


def test_commit_claim_and_close_have_no_unowned_intermediate_state(tmp_path) -> None:
    registry = SessionRegistry()
    replacement, *_ = make_session(tmp_path, registry.issue_owner("session-a"))
    barrier = Barrier(2)

    def commit() -> bool:
        barrier.wait(timeout=2)
        return registry.compare_and_swap(None, replacement)

    def cleanup() -> None:
        barrier.wait(timeout=2)
        asyncio.run(replacement.close())

    with ThreadPoolExecutor(max_workers=2) as executor:
        commit_result = executor.submit(commit)
        cleanup_result = executor.submit(cleanup)
        committed = commit_result.result(timeout=3)
        cleanup_result.result(timeout=3)

    assert replacement.resources.empty
    if committed:
        assert registry.get("session-a") is replacement
        assert registry.discard_if(replacement)
    else:
        assert registry.find("session-a") is None


@pytest.mark.parametrize("session_id", ["", "bad\nidentity", "x" * 513])
def test_registry_validates_every_external_session_identity(session_id: str) -> None:
    registry = SessionRegistry()

    with pytest.raises(ValueError):
        registry.issue_owner(session_id)
    with pytest.raises(ValueError):
        registry.find(session_id)
    with pytest.raises(ValueError):
        registry.get(session_id)
