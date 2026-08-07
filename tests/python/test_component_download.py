from __future__ import annotations

import os
import stat
import threading
import urllib.error
import urllib.request
from itertools import pairwise
from pathlib import Path

import pytest
from toqraq.components.download_http import _AllowedRedirectHandler
from toqraq.components.download_models import (
    ComponentDownloadCancelledError,
    ComponentDownloadProgress,
    ComponentDownloadRejectedError,
    ComponentDownloadRejection,
)

from _component_download_support import (
    POLICY as _POLICY,
)
from _component_download_support import (
    URL as _URL,
)
from _component_download_support import (
    OpenSequence as _OpenSequence,
)
from _component_download_support import (
    Response as _Response,
)
from _component_download_support import (
    download as _download,
)
from _component_download_support import (
    downloader_fixture as _downloader,
)
from _component_download_support import (
    full_response as _full_response,
)
from _component_download_support import (
    install_opener as _install_opener,
)
from _component_download_support import (
    range_response as _range_response,
)
from _component_download_support import (
    release as _release,
)


def test_downloads_exact_package_with_bounded_progress_and_headers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = b"complete-package"
    release = _release(package)
    response = _full_response(package)
    sequence = _OpenSequence(response)
    _install_opener(monkeypatch, sequence)
    layout, downloader, owner = _downloader(tmp_path)
    progress: list[ComponentDownloadProgress] = []

    downloaded = _download(downloader, owner, release, progress=progress.append)

    assert downloaded.path == layout.download_path(release.identity)
    assert downloaded.path.read_bytes() == package
    assert downloaded.size == len(package)
    assert downloaded.sha256 == release.identity.package_sha256
    assert progress[0] == ComponentDownloadProgress(0, len(package))
    assert progress[-1] == ComponentDownloadProgress(len(package), len(package))
    assert all(one.completed_bytes <= two.completed_bytes for one, two in pairwise(progress))
    assert sequence.requests[0].get_header("Accept-encoding") == "identity"
    assert sequence.requests[0].get_header("User-agent") == _POLICY.user_agent
    assert sequence.requests[0].get_header("Range") is None
    assert 0 < sequence.timeouts[0] <= _POLICY.io_timeout_seconds
    assert response.closed
    if os.name != "nt":
        assert stat.S_IMODE(downloaded.path.stat().st_mode) == 0o600


def test_verified_cached_package_avoids_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = b"cached-package"
    release = _release(package)
    layout, downloader, owner = _downloader(tmp_path)
    layout.download_path(release.identity).write_bytes(package)
    monkeypatch.setattr(
        "toqraq.components.download_http.urllib.request.build_opener",
        lambda *_args: pytest.fail("network must not open"),
    )

    capacity: list[int] = []
    downloaded = _download(
        downloader,
        owner,
        release,
        require_capacity=capacity.append,
    )

    assert downloaded.path.read_bytes() == package
    assert capacity == []


def test_resumes_a_hashed_partial_with_exact_range(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = b"resume-this-package"
    offset = 7
    release = _release(package)
    layout, downloader, owner = _downloader(tmp_path)
    layout.download_path(release.identity).write_bytes(package[:offset])
    response = _range_response(package, offset)
    sequence = _OpenSequence(response)
    _install_opener(monkeypatch, sequence)
    progress: list[ComponentDownloadProgress] = []
    capacity: list[int] = []

    _download(
        downloader,
        owner,
        release,
        progress=progress.append,
        require_capacity=capacity.append,
    )

    assert layout.download_path(release.identity).read_bytes() == package
    assert sequence.requests[0].get_header("Range") == f"bytes={offset}-"
    assert progress[0].completed_bytes == offset
    assert capacity == [len(package) - offset]


def test_server_can_ignore_range_only_by_returning_a_complete_full_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = b"full-restart"
    release = _release(package)
    layout, downloader, owner = _downloader(tmp_path)
    layout.download_path(release.identity).write_bytes(package[:4])
    sequence = _OpenSequence(_full_response(package))
    _install_opener(monkeypatch, sequence)

    _download(downloader, owner, release)

    assert layout.download_path(release.identity).read_bytes() == package
    assert sequence.requests[0].get_header("Range") == "bytes=4-"


def test_stale_range_416_retries_once_as_a_full_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = b"range-restart"
    release = _release(package)
    layout, downloader, owner = _downloader(tmp_path)
    layout.download_path(release.identity).write_bytes(package[:3])
    error = urllib.error.HTTPError(_URL, 416, "range", {}, None)
    sequence = _OpenSequence(error, _full_response(package))
    _install_opener(monkeypatch, sequence)

    _download(downloader, owner, release)

    assert layout.download_path(release.identity).read_bytes() == package
    assert sequence.requests[0].get_header("Range") == "bytes=3-"
    assert sequence.requests[1].get_header("Range") is None


def test_cancellation_retains_prefix_and_next_call_resumes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = b"cancel-and-resume"
    release = _release(package)
    layout, downloader, owner = _downloader(tmp_path)
    cancellation = threading.Event()
    first_response = _full_response(package)
    first_sequence = _OpenSequence(first_response)
    _install_opener(monkeypatch, first_sequence)

    def cancel_after_first_chunk(value: ComponentDownloadProgress) -> None:
        if value.completed_bytes >= _POLICY.chunk_bytes:
            cancellation.set()

    with pytest.raises(ComponentDownloadCancelledError):
        _download(
            downloader,
            owner,
            release,
            cancellation=cancellation,
            progress=cancel_after_first_chunk,
        )
    retained = layout.download_path(release.identity).read_bytes()
    assert retained == package[: _POLICY.chunk_bytes]
    assert first_response.closed

    cancellation.clear()
    second_sequence = _OpenSequence(_range_response(package, len(retained)))
    _install_opener(monkeypatch, second_sequence)
    _download(downloader, owner, release, cancellation=cancellation)
    assert layout.download_path(release.identity).read_bytes() == package


def test_transport_failure_retains_only_observed_bytes_for_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = b"transport-resume"
    release = _release(package)
    layout, downloader, owner = _downloader(tmp_path)
    response = _Response(
        package,
        headers={"Content-Length": [str(len(package))]},
        failure_after=_POLICY.chunk_bytes,
    )
    _install_opener(monkeypatch, _OpenSequence(response))

    with pytest.raises(ComponentDownloadRejectedError) as captured:
        _download(downloader, owner, release)

    assert captured.value.reason is ComponentDownloadRejection.TRANSPORT_FAILED
    retained = layout.download_path(release.identity).read_bytes()
    assert retained == package[: _POLICY.chunk_bytes]


def test_digest_mismatch_discards_unresumable_complete_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = b"expected-content"
    release = _release(package)
    layout, downloader, owner = _downloader(tmp_path)
    wrong = b"unexpected-data!"
    assert len(wrong) == len(package)
    _install_opener(monkeypatch, _OpenSequence(_full_response(wrong)))

    with pytest.raises(ComponentDownloadRejectedError) as captured:
        _download(downloader, owner, release)

    assert captured.value.reason is ComponentDownloadRejection.DIGEST_MISMATCH
    assert layout.download_path(release.identity).read_bytes() == b""


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (_Response(b"body", status=201), ComponentDownloadRejection.RESPONSE_INVALID),
        (
            _Response(b"body", headers={"Content-Encoding": ["gzip"]}),
            ComponentDownloadRejection.RESPONSE_INVALID,
        ),
        (
            _Response(b"body", headers={"Content-Length": ["4", "4"]}),
            ComponentDownloadRejection.RESPONSE_INVALID,
        ),
        (
            _Response(b"body", headers={"Content-Length": ["3"]}),
            ComponentDownloadRejection.SIZE_MISMATCH,
        ),
        (
            _Response(b"body", headers={"Content-Range": ["bytes 0-3/4"]}),
            ComponentDownloadRejection.RESPONSE_INVALID,
        ),
        (
            _Response(b"body", url="https://other.example.test/body"),
            ComponentDownloadRejection.ORIGIN_REJECTED,
        ),
        (
            _Response(b"body", non_bytes=True),
            ComponentDownloadRejection.RESPONSE_INVALID,
        ),
    ],
)
def test_rejects_malformed_or_unauthorized_responses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    response: _Response,
    reason: ComponentDownloadRejection,
) -> None:
    release = _release(b"body")
    _, downloader, owner = _downloader(tmp_path)
    _install_opener(monkeypatch, _OpenSequence(response))

    with pytest.raises(ComponentDownloadRejectedError) as captured:
        _download(downloader, owner, release)

    assert captured.value.reason is reason
    assert response.closed


def test_chunked_response_cannot_hide_bytes_after_exact_package_length(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = _release(b"body")
    layout, downloader, owner = _downloader(tmp_path)
    response = _Response(b"body-extra", headers={})
    _install_opener(monkeypatch, _OpenSequence(response))

    with pytest.raises(ComponentDownloadRejectedError) as captured:
        _download(downloader, owner, release)

    assert captured.value.reason is ComponentDownloadRejection.SIZE_MISMATCH
    assert layout.download_path(release.identity).read_bytes() == b""


def test_redirect_handler_checks_every_target_and_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = urllib.request.Request(_URL)
    monkeypatch.setattr(
        urllib.request.HTTPRedirectHandler,
        "redirect_request",
        lambda _self, *_args: request,
    )
    handler = _AllowedRedirectHandler(frozenset({"https://downloads.example.test"}), 1)

    assert handler.redirect_request(request, None, 302, "", {}, _URL) is request
    with pytest.raises(ComponentDownloadRejectedError) as limited:
        handler.redirect_request(request, None, 302, "", {}, _URL)
    assert limited.value.reason is ComponentDownloadRejection.REDIRECT_LIMIT

    other = _AllowedRedirectHandler(frozenset({"https://downloads.example.test"}), 2)
    with pytest.raises(ComponentDownloadRejectedError) as rejected:
        other.redirect_request(
            request,
            None,
            302,
            "",
            {},
            "https://other.example.test/package",
        )
    assert rejected.value.reason is ComponentDownloadRejection.ORIGIN_REJECTED


def test_unsafe_existing_partial_is_never_followed_or_modified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = b"safe-package"
    release = _release(package)
    layout, downloader, owner = _downloader(tmp_path)
    outside = tmp_path / "outside"
    outside.write_bytes(b"keep")
    partial = layout.download_path(release.identity)
    try:
        partial.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symbolic links unavailable: {type(exc).__name__}")
    monkeypatch.setattr(
        "toqraq.components.download_http.urllib.request.build_opener",
        lambda *_args: pytest.fail("network must not open"),
    )

    with pytest.raises(ComponentDownloadRejectedError) as captured:
        _download(downloader, owner, release)

    assert captured.value.reason is ComponentDownloadRejection.FILE_INVALID
    assert outside.read_bytes() == b"keep"
