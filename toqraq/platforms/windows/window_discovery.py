"""Bounded Win32 implementation of native preview-window discovery."""

from __future__ import annotations

from ...core.errors import PlatformOperationError
from ...core.geometry import Size
from ...core.native_preview import (
    MAX_NATIVE_PREVIEW_CANDIDATES,
    NativeWindowCandidate,
)
from ...core.preview import NativeWindowReference
from . import native


class WindowsNativeWindowDiscovery:
    """Enumerate only visible non-empty windows owned by one exact PID."""

    def for_process(self, process_id: int) -> tuple[NativeWindowCandidate, ...]:
        """Return the largest bounded candidates in deterministic order."""
        if isinstance(process_id, bool) or not isinstance(process_id, int) or process_id < 1:
            raise ValueError("native preview process ID is invalid")
        candidates: list[NativeWindowCandidate] = []

        def visit(handle: int) -> bool:
            if not native.is_window_visible(handle):
                return True
            try:
                if native.get_window_process_id(handle) != process_id:
                    return True
                left, top, right, bottom = native.get_client_rect(handle)
                width = right - left
                height = bottom - top
                if width < 1 or height < 1:
                    return True
                candidates.append(
                    NativeWindowCandidate(
                        window=NativeWindowReference(value=handle),
                        process_id=process_id,
                        client_size=Size(width=width, height=height),
                    )
                )
                candidates.sort(key=_candidate_order, reverse=True)
                del candidates[MAX_NATIVE_PREVIEW_CANDIDATES:]
            except PlatformOperationError:
                # A foreign process may destroy its window during enumeration.
                pass
            return True

        native.enumerate_windows(visit)
        return tuple(candidates)


def _candidate_order(candidate: NativeWindowCandidate) -> tuple[int, int]:
    """Prefer the largest client and then one deterministic native reference."""
    return candidate.area, -candidate.window.value
