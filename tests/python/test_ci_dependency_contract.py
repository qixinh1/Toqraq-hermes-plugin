"""Reproducible contributor and CI dependency contracts."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
EXPECTED_DEV_REQUIREMENTS = {
    "fastapi": "0.138.1",
    "httpx": "0.28.1",
    "mypy": "2.3.0",
    "pydantic": "2.13.4",
    "pyyaml": "6.0.3",
    "pytest": "9.1.1",
    "ruff": "0.15.22",
    "starlette": "1.3.1",
    "websockets": "15.0.1",
}
EXPECTED_CANDIDATE_REQUIREMENTS = {
    "pydantic": "2.13.4",
    "pytest": "9.1.1",
    "websockets": "15.0.1",
}
_LOCK_ENTRY = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+).*?"
    r"(?=^[A-Za-z0-9][A-Za-z0-9._-]*==|\Z)",
    re.MULTILINE | re.DOTALL,
)


def _canonical_name(value: str) -> str:
    """Return one PEP 503-style project name."""
    return re.sub(r"[-_.]+", "-", value).lower()


def _declared_dev_requirements() -> dict[str, str]:
    """Read the exact direct verification requirements."""
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = project["project"]["optional-dependencies"]["dev"]
    result: dict[str, str] = {}
    for requirement in requirements:
        name, separator, version = requirement.partition("==")
        assert separator == "=="
        result[_canonical_name(name)] = version
    return result


def _locked_requirements(path: Path) -> tuple[dict[str, str], tuple[str, ...]]:
    """Read exact versions and complete entry blocks from the generated closure."""
    source = path.read_text(encoding="utf-8")
    matches = tuple(_LOCK_ENTRY.finditer(source))
    versions = {_canonical_name(match.group(1)): match.group(2) for match in matches}
    assert len(versions) == len(matches)
    return versions, tuple(match.group(0) for match in matches)


def test_python_verification_closure_has_every_exact_direct_requirement() -> None:
    assert _declared_dev_requirements() == EXPECTED_DEV_REQUIREMENTS
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["build-system"]["requires"] == ["setuptools==83.0.0"]

    locked, blocks = _locked_requirements(REPO_ROOT / "requirements-dev.txt")
    assert {name: locked[name] for name in EXPECTED_DEV_REQUIREMENTS} == (EXPECTED_DEV_REQUIREMENTS)
    assert blocks
    assert all("--hash=sha256:" in block for block in blocks)


def test_godot_candidate_verification_closure_has_one_direct_source() -> None:
    direct = (REPO_ROOT / "engine" / "godot" / "candidate-test-requirements.in").read_text(
        encoding="utf-8"
    )
    assert tuple(direct.splitlines()) == tuple(
        f"{name}=={version}" for name, version in EXPECTED_CANDIDATE_REQUIREMENTS.items()
    )

    locked, blocks = _locked_requirements(
        REPO_ROOT / "engine" / "godot" / "candidate-test-requirements.txt"
    )
    assert {name: locked[name] for name in EXPECTED_CANDIDATE_REQUIREMENTS} == (
        EXPECTED_CANDIDATE_REQUIREMENTS
    )
    assert blocks
    assert all("--hash=sha256:" in block for block in blocks)

    workflow = (REPO_ROOT / ".github" / "workflows" / "godot-candidate.yml").read_text(
        encoding="utf-8"
    )
    expected_versions = " ".join(EXPECTED_CANDIDATE_REQUIREMENTS.values())
    assert f"if ($versions -cne '{expected_versions}')" in workflow


def test_ci_installs_only_the_hash_pinned_python_closure() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "\npermissions:\n  contents: read\n" in workflow
    assert "pip install .[dev]" not in workflow
    assert workflow.count("--require-hashes") == 2
    assert workflow.count("--only-binary=:all:") == 2
    assert workflow.count("--requirement requirements-dev.txt") == 2

    checkout_blocks = workflow.split("      - uses: actions/checkout@")[1:]
    assert len(checkout_blocks) == 3
    for block in checkout_blocks:
        assert "persist-credentials: false" in block.split("      - ", 1)[0]


def test_node_verification_manifest_and_lock_are_exact() -> None:
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((REPO_ROOT / "package-lock.json").read_text(encoding="utf-8"))
    assert package["engines"] == {"node": ">=22"}
    assert package["devDependencies"] == {"esbuild": "0.25.12"}
    assert lock["packages"][""]["devDependencies"] == package["devDependencies"]

    installed = lock["packages"]["node_modules/esbuild"]
    assert installed["version"] == "0.25.12"
    external_packages = [entry for path, entry in lock["packages"].items() if path]
    assert external_packages
    assert all(
        entry["resolved"].startswith("https://registry.npmjs.org/") for entry in external_packages
    )
    assert all(entry["integrity"].startswith("sha512-") for entry in external_packages)


def test_dependency_update_discovery_covers_every_package_surface() -> None:
    source = (REPO_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    assert source.count("interval: weekly") == 3
    assert {match.group(1) for match in re.finditer(r"package-ecosystem: ([a-z-]+)", source)} == {
        "pip",
        "npm",
        "github-actions",
    }
