"""Fail-closed process adapter for a host without a platform contribution."""

from __future__ import annotations

from ..core.errors import UnsupportedPlatformError
from ..core.process_tree import ProcessLaunch, ProcessTree


class UnavailableProcessTreeLauncher:
    """Keep the standard plugin loadable while rejecting unsupported launches."""

    def launch(self, command: ProcessLaunch) -> ProcessTree:
        """Reject execution because no platform launcher owns this host."""
        if not isinstance(command, ProcessLaunch):
            raise ValueError("process launch command is invalid")
        raise UnsupportedPlatformError(details={"reason": "process_launcher_unavailable"})

    def close(self) -> None:
        """Release no resources; this adapter never acquires any."""
