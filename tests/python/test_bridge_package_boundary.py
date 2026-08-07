"""Bridge package import-boundary regression tests."""

from __future__ import annotations

import subprocess
import sys


def test_bridge_adapter_import_is_independent_of_the_composition_root() -> None:
    source = "\n".join(
        (
            "import sys",
            "import toqraq.bridge.bridge_feature_connection",
            "assert 'toqraq.services.container' not in sys.modules",
        )
    )
    completed = subprocess.run(
        [sys.executable, "-c", source],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
