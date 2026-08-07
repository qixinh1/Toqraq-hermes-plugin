"""Session ownership for one prepared component installation."""

from __future__ import annotations

import asyncio
import threading

from .lease import ComponentLease
from .mutation import ComponentMutation
from .store import ComponentInstallation


class PreparedComponentResource:
    """Own a committed lease and any mutation release still pending."""

    def __init__(
        self,
        lease: ComponentLease[ComponentInstallation],
        mutation: ComponentMutation,
    ) -> None:
        """Take both owners before attempting the post-commit transfer."""
        self._lease = lease
        self._mutation: ComponentMutation | None = mutation
        self._close_lock = threading.Lock()

    def release_mutation(self) -> bool:
        """Release the preparation token or retain it for session cleanup."""
        with self._close_lock:
            mutation = self._mutation
            if mutation is None:
                return True
            try:
                mutation.close()
            except OSError:
                return False
            self._mutation = None
            return True

    async def close(self) -> None:
        """Release idempotently without blocking the event-loop thread."""
        await asyncio.to_thread(self.close_blocking)

    def close_blocking(self) -> None:
        """Retry deferred mutation cleanup, then release the exact lease."""
        with self._close_lock:
            mutation = self._mutation
            if mutation is not None:
                mutation.close()
                self._mutation = None
            self._lease.close()
