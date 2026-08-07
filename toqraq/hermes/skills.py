"""Register Toqraq's focused, explicitly loaded Hermes skills."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from .context import HermesPluginContext

BUNDLED_SKILLS: Final[tuple[tuple[str, str], ...]] = (
    (
        "game-development",
        "Use for game changes that need live engine verification.",
    ),
    (
        "asset-workflow",
        "Use for sourcing and importing traceable game media.",
    ),
    (
        "balance",
        "Use for modeling and tuning connected game values.",
    ),
    (
        "playtest-debug",
        "Use for bounded playtesting and running-game diagnosis.",
    ),
)

_SKILLS_ROOT = Path(__file__).resolve().parents[2] / "skills"


def register_skills(ctx: HermesPluginContext) -> None:
    """Register every bundled skill through Hermes's namespace owner."""
    for name, description in BUNDLED_SKILLS:
        ctx.register_skill(name, _SKILLS_ROOT / name / "SKILL.md", description)
