from __future__ import annotations

import os
import stat
import urllib.error
from pathlib import Path

import pytest
from toqraq.components.download_file import open_partial
from toqraq.components.download_http import _transport_rejection
from toqraq.components.download_models import ComponentDownloadRejection


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits only")
def test_open_partial_repairs_existing_file_permissions(tmp_path: Path) -> None:
    path = tmp_path / "package.download"
    path.write_bytes(b"partial")
    path.chmod(0o666)

    descriptor = open_partial(path, 1024)
    try:
        assert stat.S_IMODE(os.fstat(descriptor).st_mode) == 0o600
    finally:
        os.close(descriptor)


@pytest.mark.parametrize(
    "error",
    [TimeoutError("direct"), urllib.error.URLError(TimeoutError("wrapped"))],
)
def test_transport_timeout_classification_includes_wrapped_errors(
    error: OSError,
) -> None:
    assert _transport_rejection(error) is ComponentDownloadRejection.TIMEOUT


def test_non_timeout_transport_error_stays_distinct() -> None:
    assert (
        _transport_rejection(urllib.error.URLError(OSError("connection")))
        is ComponentDownloadRejection.TRANSPORT_FAILED
    )
