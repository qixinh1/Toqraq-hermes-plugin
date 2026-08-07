"""DPI awareness setup for the embedding process.

Physical-pixel fidelity is required for geometry synchronization: the
renderer reports coordinates derived from ``devicePixelRatio``-scaled CSS
pixels, and Win32 positioning APIs must interpret them identically.
"""

from __future__ import annotations

from . import native

_attempted = False


def ensure_dpi_awareness() -> None:
    """Apply the per-monitor V2 DPI policy once for this process."""
    global _attempted
    if _attempted:
        return
    native.enable_dpi_awareness()
    _attempted = True
