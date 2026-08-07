"""Host window resolution from renderer-reported screen points."""

from __future__ import annotations

from ...core.errors import HostWindowNotFoundError, PlatformOperationError
from . import native

_NONINTERACTIVE = native.WS_EX_NOACTIVATE | native.WS_EX_TRANSPARENT


def locate_host_window(point: tuple[int, int], excluded_process_id: int) -> int:
    """Resolve the top-level window containing a screen point.

    Top-level windows are enumerated in Z-order; the first visible window
    whose rect contains the point wins. Windows owned by ``excluded_process_id``
    are skipped so a freshly started game covering the pane cannot shadow
    the real host.

    Args:
        point: Absolute screen coordinates in physical pixels.
        excluded_process_id: Process id whose windows are ignored.

    Returns:
        The top-level native window handle.

    Raises:
        HostWindowNotFoundError: If no usable window contains the point.
    """
    if (
        isinstance(excluded_process_id, bool)
        or not isinstance(excluded_process_id, int)
        or excluded_process_id < 1
    ):
        raise ValueError("excluded process ID is invalid")
    hit: int | None = None

    def visit(handle: int) -> bool:
        nonlocal hit
        if not native.is_window_visible(handle):
            return True
        try:
            if native.get_window_long(handle, native.GWL_EXSTYLE) & _NONINTERACTIVE:
                return True
            left, top, right, bottom = native.get_window_rect(handle)
            owner_pid = native.get_window_process_id(handle)
        except PlatformOperationError:
            # Windows can disappear between enumeration and inspection.
            return True
        if not (left <= point[0] < right and top <= point[1] < bottom):
            return True
        if owner_pid == excluded_process_id:
            return True
        hit = handle
        return False

    native.enumerate_windows(visit)
    if hit is None:
        raise HostWindowNotFoundError(
            parameters={"x": point[0], "y": point[1]},
            details={"reason": "no_interactive_window_at_point"},
        )
    return hit
