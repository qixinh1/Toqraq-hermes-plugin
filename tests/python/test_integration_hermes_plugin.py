"""Clean-profile verification through the public Hermes plugin lifecycle."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from toqraq.hermes.tools import TOOL_SPECS

REPO_ROOT = Path(__file__).parents[2]
HERMES_SOURCE_ENV = "TOQRAQ_HERMES_SOURCE"
_COMMAND_TIMEOUT_SECONDS = 120
_DIAGNOSTIC_CHARACTER_LIMIT = 4_000
_PACKAGE_ENTRIES = (
    ".gitattributes",
    ".gitignore",
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "__init__.py",
    "dashboard",
    "desktop",
    "docs",
    "plugin.yaml",
    "skills",
    "toqraq",
)

pytestmark = [pytest.mark.integration, pytest.mark.hermes_integration]


def _require_hermes_source() -> Path:
    """Return the Hermes source tree required by this external suite."""
    value = os.environ.get(HERMES_SOURCE_ENV)
    if not value:
        pytest.skip(
            f"set {HERMES_SOURCE_ENV}; see docs/plugin-packaging.md#required-hermes-host-contract"
        )
    source = Path(value).resolve()
    if not (source / "hermes_cli" / "main.py").is_file():
        pytest.fail(f"{HERMES_SOURCE_ENV} does not name a Hermes source tree")
    return source


def _run(
    arguments: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """Run one bounded command and retain a bounded failure diagnostic."""
    result = subprocess.run(
        arguments,
        cwd=cwd,
        env=environment,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
        timeout=_COMMAND_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode:
        output = f"{result.stdout}\n{result.stderr}"[-_DIAGNOSTIC_CHARACTER_LIMIT:]
        pytest.fail(f"command failed ({result.returncode}): {arguments[1:]}\n{output}")
    return result


def _prepare_git_source(destination: Path, environment: dict[str, str]) -> None:
    """Create the committed local source required by the standard command."""
    if shutil.which("git") is None:
        pytest.skip("Git is required by the standard Hermes plugin command")
    destination.mkdir()
    for relative in _PACKAGE_ENTRIES:
        source = REPO_ROOT / relative
        target = destination / relative
        if source.is_dir():
            shutil.copytree(
                source,
                target,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        else:
            shutil.copy2(source, target)
    _run(["git", "init"], cwd=destination, environment=environment)
    _run(["git", "add", "."], cwd=destination, environment=environment)
    _run(
        [
            "git",
            "-c",
            "user.name=Toqraq Test",
            "-c",
            "user.email=toqraq-test@example.invalid",
            "commit",
            "-m",
            "test: stage plugin package",
        ],
        cwd=destination,
        environment=environment,
    )


def _run_hermes(
    source: Path,
    environment: dict[str, str],
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    """Invoke the public Hermes command from its source checkout."""
    return _run(
        [str(_hermes_python(source)), "-m", "hermes_cli.main", *arguments],
        cwd=source,
        environment=environment,
    )


def _hermes_python(source: Path) -> Path:
    """Resolve the interpreter owned by the Hermes source environment."""
    candidates = (
        source / "venv" / "Scripts" / "python.exe",
        source / ".venv" / "Scripts" / "python.exe",
        source / "venv" / "bin" / "python",
        source / ".venv" / "bin" / "python",
        Path(sys.executable),
    )
    return next(candidate for candidate in candidates if candidate.is_file())


def _assert_active_surfaces(source: Path, environment: dict[str, str]) -> None:
    """Prove that one enabled package exposes every Phase 1 surface."""
    code = """
import asyncio
import json
from hermes_cli.plugin_desktop import read_enabled_desktop_plugin
from hermes_cli.plugins import discover_plugins, get_plugin_manager
from tools import tts_tool
from tools.registry import registry
from tools.skills_tool import skill_view

discover_plugins(force=True)
manager = get_plugin_manager()
rows = [row for row in manager.list_plugins() if row["name"] == "toqraq"]
assert len(rows) == 1
assert rows[0]["configured_enabled"] is True
assert rows[0]["enabled"] is True
assert rows[0]["manifest_version"] == 2
assert rows[0]["desktop_entry"] == "desktop/plugin.js"
assert rows[0]["tools"] == __EXPECTED_TOOL_COUNT__
assert rows[0]["hooks"] == 2
desktop = read_enabled_desktop_plugin("toqraq")
assert desktop is not None
assert desktop[0].enabled is True
skill_names = ["asset-workflow", "balance", "game-development", "playtest-debug"]
assert manager.list_plugin_skills("toqraq") == skill_names
skill_contents = {}
for skill_name in skill_names:
    result = json.loads(skill_view(f"toqraq:{skill_name}"))
    assert result["success"] is True
    assert result["name"] == f"toqraq:{skill_name}"
    skill_contents[skill_name] = result["content"]
    assert "independent `task_id`" in result["content"]
    assert "child's task, not the parent's" in result["content"]
    assert "retains every live-game" in result["content"]
    assert "verifies the returned summary" in result["content"]
    assert "never ask a child to control or verify the parent game" in result["content"]

asset_skill = skill_contents["asset-workflow"]
assert "`image_generate` and `vision_analyze`" in asset_skill
assert "enabled `video_gen` toolset" in asset_skill
assert "active backend" in asset_skill
assert "enabled `video` toolset" in asset_skill
assert "suitable model" in asset_skill
assert "`text_to_speech`" in asset_skill
assert "enabled `tts` toolset" in asset_skill
assert "configured provider" in asset_skill
assert registry.get_entry("text_to_speech") is not None
assert tts_tool.TTS_SCHEMA["name"] == "text_to_speech"
for unsupported_claim in (
    "`audio_generate`",
    "`transcribe`",
    "Hermes artifact record",
    "Hermes artifact store",
):
    assert unsupported_claim not in asset_skill

from hermes_cli import web_server

dashboard = [
    row
    for row in asyncio.run(web_server.get_dashboard_plugins())
    if row["name"] == "toqraq"
]
assert len(dashboard) == 1
assert dashboard[0]["entry"] is None
assert dashboard[0]["tab"]["hidden"] is True
assert dashboard[0]["has_api"] is True
assert any(
    getattr(route, "path", "").startswith("/api/plugins/toqraq")
    for route in web_server.app.routes
)
""".replace("__EXPECTED_TOOL_COUNT__", str(len(TOOL_SPECS)))
    _run([str(_hermes_python(source)), "-c", code], cwd=source, environment=environment)


def _assert_disabled_surfaces(source: Path, environment: dict[str, str]) -> None:
    """Prove that disabling the package prevents every presenter from loading."""
    code = """
import asyncio
from hermes_cli.plugin_desktop import read_enabled_desktop_plugin
from hermes_cli.plugins import discover_plugins, get_plugin_manager

discover_plugins(force=True)
rows = [row for row in get_plugin_manager().list_plugins() if row["name"] == "toqraq"]
assert len(rows) == 1
assert rows[0]["configured_enabled"] is False
assert rows[0]["enabled"] is False
assert read_enabled_desktop_plugin("toqraq") is None

from hermes_cli import web_server

assert not any(row["name"] == "toqraq" for row in asyncio.run(web_server.get_dashboard_plugins()))
assert not any(
    getattr(route, "path", "").startswith("/api/plugins/toqraq")
    for route in web_server.app.routes
)
"""
    _run([str(_hermes_python(source)), "-c", code], cwd=source, environment=environment)


def _assert_removed_surfaces(source: Path, environment: dict[str, str]) -> None:
    """Prove that removal leaves no discoverable package surface."""
    code = """
import asyncio
from hermes_cli.plugin_desktop import discover_desktop_plugins
from hermes_cli.plugins import discover_plugins, get_plugin_manager

discover_plugins(force=True)
assert not any(row["name"] == "toqraq" for row in get_plugin_manager().list_plugins())
assert not any(row.id == "toqraq" for row in discover_desktop_plugins())

from hermes_cli import web_server

assert not any(row["name"] == "toqraq" for row in asyncio.run(web_server.get_dashboard_plugins()))
"""
    _run([str(_hermes_python(source)), "-c", code], cwd=source, environment=environment)


def test_standard_install_update_disable_enable_and_remove(tmp_path: Path) -> None:
    """Exercise the complete public package lifecycle in an isolated home."""
    hermes_source = _require_hermes_source()
    plugin_source = tmp_path / "plugin-source"
    hermes_home = tmp_path / "hermes-home"
    environment = os.environ.copy()
    environment["HERMES_HOME"] = str(hermes_home)
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(hermes_source), environment.get("PYTHONPATH", "")) if value
    )
    _prepare_git_source(plugin_source, environment)

    _run_hermes(
        hermes_source,
        environment,
        "plugins",
        "install",
        plugin_source.as_uri(),
        "--enable",
    )
    installed = hermes_home / "plugins" / "toqraq"
    assert installed.is_dir()
    assert (installed / "desktop" / "plugin.js").is_file()
    assert (installed / "desktop" / "plugin.js").read_bytes() == (
        REPO_ROOT / "desktop" / "plugin.js"
    ).read_bytes()
    _assert_active_surfaces(hermes_source, environment)

    _run_hermes(hermes_source, environment, "plugins", "disable", "toqraq")
    _assert_disabled_surfaces(hermes_source, environment)

    _run_hermes(
        hermes_source,
        environment,
        "plugins",
        "enable",
        "toqraq",
        "--no-allow-tool-override",
    )
    _assert_active_surfaces(hermes_source, environment)

    _run_hermes(hermes_source, environment, "plugins", "update", "toqraq")
    _assert_active_surfaces(hermes_source, environment)

    _run_hermes(hermes_source, environment, "plugins", "remove", "toqraq")
    assert not installed.exists()
    _assert_removed_surfaces(hermes_source, environment)
