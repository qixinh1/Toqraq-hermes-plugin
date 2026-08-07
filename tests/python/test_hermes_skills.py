"""Bundled Hermes skill registration and package-content contracts."""

from __future__ import annotations

import re
from pathlib import Path

from toqraq.hermes.skills import BUNDLED_SKILLS, register_skills

REPO_ROOT = Path(__file__).parents[2]
SKILLS_ROOT = REPO_ROOT / "skills"
EXPECTED_NAMES = (
    "game-development",
    "asset-workflow",
    "balance",
    "playtest-debug",
)
DELEGATION_BOUNDARY = (
    "Every `delegate_task` child has an independent `task_id`.",
    "`toqraq_game_*` call from that child targets the child's task",
    "not the parent's\ngame",
    "The parent gathers and passes bounded evidence",
    "retains every live-game\noperation",
    "verifies the returned summary",
    "Delegate only an independent\nanalysis or review leaf",
    "never ask a child to control or verify the parent game",
)


def _frontmatter(source: str) -> tuple[dict[str, str], str]:
    """Return scalar top-level frontmatter and the remaining body."""
    assert source.startswith("---\n")
    _, frontmatter, body = source.split("---", maxsplit=2)
    values = dict(
        re.findall(
            r"^([a-z][a-z-]*): (.+)$",
            frontmatter,
            flags=re.MULTILINE,
        )
    )
    return values, body


def test_skill_catalog_registers_exact_files_in_stable_order() -> None:
    calls: list[tuple[str, Path, str]] = []

    class Context:
        def register_skill(self, name: str, path: Path, description: str = "") -> None:
            calls.append((name, path, description))

    register_skills(Context())

    assert tuple(name for name, _description in BUNDLED_SKILLS) == EXPECTED_NAMES
    assert calls == [
        (name, (SKILLS_ROOT / name / "SKILL.md").resolve(), description)
        for name, description in BUNDLED_SKILLS
    ]
    assert all(description for _name, _path, description in calls)


def test_bundled_skills_are_self_contained_and_actionable() -> None:
    assert {
        path.relative_to(SKILLS_ROOT).as_posix()
        for path in SKILLS_ROOT.rglob("*")
        if path.is_file()
    } == {f"{name}/SKILL.md" for name in EXPECTED_NAMES}

    for name in EXPECTED_NAMES:
        source = (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")
        frontmatter, body = _frontmatter(source)
        assert set(frontmatter) == {"name", "description"}
        assert frontmatter["name"] == name
        description = frontmatter["description"]
        assert len(description) <= 60
        assert description.startswith("Use for ")
        assert description.endswith(".")
        assert description.count(".") == 1
        assert "TODO" not in source
        for heading in (
            "# ",
            "## When to Use",
            "## Prerequisites",
            "## How to Run",
            "## Quick Reference",
            "## Delegation Boundary",
            "## Procedure",
            "## Pitfalls",
            "## Verification",
        ):
            assert heading in body
        assert "`delegate_task`" in body
        assert any(tool in body for tool in ("`patch`", "`write_file`"))
        assert "`search_files`" in body
        assert "elapsed sleep" in body
        assert "Hermes file tools" not in body
        assert "ctx.dispatch_tool" not in body
        assert len(source.splitlines()) <= 500


def test_skills_keep_live_game_ownership_with_the_parent_task() -> None:
    for name in EXPECTED_NAMES:
        body = (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")
        for statement in DELEGATION_BOUNDARY:
            assert statement in body
        assert "poll" in body


def test_asset_skill_names_only_verified_conditional_media_tools() -> None:
    body = (SKILLS_ROOT / "asset-workflow" / "SKILL.md").read_text(encoding="utf-8")

    assert "`image_generate` and `vision_analyze`" in body
    assert "`video_generate`" in body
    assert "enabled `video_gen` toolset" in body
    assert "active backend" in body
    assert "`video_analyze`" in body
    assert "enabled `video` toolset" in body
    assert "suitable model" in body
    assert "`text_to_speech`" in body
    assert "enabled `tts` toolset" in body
    assert "configured provider" in body
    assert "not music or\n  sound effects" in body
    for unsupported_claim in (
        "`audio_generate`",
        "`transcribe`",
        "Hermes artifact record",
        "Hermes artifact store",
    ):
        assert unsupported_claim not in body


def test_asset_skill_uses_a_visible_binary_placement_operation() -> None:
    body = (SKILLS_ROOT / "asset-workflow" / "SKILL.md").read_text(encoding="utf-8")

    assert "place text with `patch` or `write_file`" in body
    assert "one explicit `terminal` operation for binary files" in body
