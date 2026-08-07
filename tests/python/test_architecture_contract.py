"""Executable dependency and package invariants from the architecture."""

from __future__ import annotations

import ast
import json
import re
import tomllib
from pathlib import Path

from scripts.godot_candidate_evidence import GODOT_CANDIDATE_SCONS_ARGUMENTS
from toqraq.engines.godot.identity import GODOT_RUNTIME_DISTRIBUTION_ID
from toqraq.hermes.tools import TOOL_SPECS

REPO_ROOT = Path(__file__).parents[2]
BACKEND = REPO_ROOT / "toqraq"
RENDERER = REPO_ROOT / "src" / "renderer"
_MARKDOWN_LINK = re.compile(r"\[[^]]*]\(([^)]+)\)")
_PINNED_ACTION = re.compile(r"\buses:\s+[^@\s]+@([0-9a-f]{40})(?:\s|$)")
_HANDWRITTEN_SUFFIXES = {".cpp", ".gd", ".h", ".js", ".mjs", ".py", ".ts", ".tsx"}
_KNOWN_SIZE_DEBT: dict[str, int] = {}
_GENERATED_SOURCE_PATHS = {"src/renderer/contracts/generated.d.ts"}


def _module_package(path: Path) -> list[str]:
    """Return the canonical package containing one backend module."""
    relative = path.relative_to(BACKEND)
    parents = list(relative.parent.parts)
    return ["toqraq", *parents]


def _imports(path: Path) -> set[str]:
    """Collect canonical imports, resolving package-relative statements."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = _module_package(path)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level == 0:
            if node.module:
                names.add(node.module)
            continue
        trim = node.level - 1
        anchor = package[: len(package) - trim] if trim else package
        if node.module:
            names.add(".".join([*anchor, *node.module.split(".")]))
        else:
            names.update(".".join([*anchor, alias.name]) for alias in node.names)
    return names


def _manifest_list(source: str, key: str) -> set[str]:
    """Read one top-level scalar list from the constrained plugin YAML."""
    lines = source.splitlines()
    try:
        start = lines.index(f"{key}:") + 1
    except ValueError:
        return set()
    values: set[str] = set()
    for line in lines[start:]:
        if line.startswith("  - "):
            values.add(line.removeprefix("  - ").strip())
            continue
        if line and not line.startswith(" "):
            break
    return values


def _manifest_scalar(source: str, key: str) -> str:
    """Read one required top-level scalar from the constrained plugin YAML."""
    prefix = f"{key}:"
    return next(
        line.removeprefix(prefix).strip() for line in source.splitlines() if line.startswith(prefix)
    )


def test_core_is_independent_of_outer_layers() -> None:
    violations: list[str] = []
    for path in (BACKEND / "core").glob("*.py"):
        for name in _imports(path):
            if name.startswith("toqraq.") and not name.startswith("toqraq.core"):
                violations.append(f"{path.name}: {name}")
    assert violations == []


def test_runtime_contribution_boundary_has_only_focused_core_dependencies() -> None:
    expected = {
        "runtime.py": {
            "toqraq.core.absolute_path",
            "toqraq.core.capability_ids",
            "toqraq.core.resource",
        },
        "engine_contribution.py": {
            "toqraq.core.absolute_path",
            "toqraq.core.bridge",
            "toqraq.core.geometry",
            "toqraq.core.preview",
            "toqraq.core.process_tree",
            "toqraq.core.runtime",
        },
    }

    actual = {
        name: {
            dependency
            for dependency in _imports(BACKEND / "core" / name)
            if dependency.startswith("toqraq.")
        }
        for name in expected
    }

    assert actual == expected


def test_component_catalog_is_explicit_in_memory_registration() -> None:
    catalog = BACKEND / "components" / "catalog.py"
    tree = ast.parse(catalog.read_text(encoding="utf-8"), filename=str(catalog))
    dependencies = {
        dependency for dependency in _imports(catalog) if dependency.startswith("toqraq.")
    }
    top_level_functions = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert dependencies == {
        "toqraq.components.identity",
        "toqraq.components.release",
        "toqraq.core.errors",
    }
    assert top_level_functions == set()


def test_production_runtime_and_component_catalogs_are_empty() -> None:
    container = BACKEND / "services" / "container.py"
    tree = ast.parse(container.read_text(encoding="utf-8"), filename=str(container))
    calls: dict[str, list[ast.Call]] = {"CertifiedComponentCatalog": [], "EngineCatalog": []}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in calls:
            calls[node.func.id].append(node)

    assert all(len(selected) == 1 for selected in calls.values())
    for selected in calls.values():
        call = selected[0]
        assert len(call.args) == 1
        assert isinstance(call.args[0], ast.Tuple)
        assert call.args[0].elts == []
        assert call.keywords == []


def test_concrete_adapters_do_not_leak_into_use_cases_or_presenters() -> None:
    violations: list[str] = []
    roots = [BACKEND / "api", BACKEND / "services", BACKEND / "hermes"]
    for root in roots:
        for path in root.glob("*.py"):
            if path == BACKEND / "services" / "container.py":
                continue
            for name in _imports(path):
                if name.startswith(("toqraq.bridge", "toqraq.engines", "toqraq.platforms")):
                    violations.append(f"{path.relative_to(BACKEND)}: {name}")
    assert violations == []


def test_bridge_package_is_independent_of_presenters_and_other_adapters() -> None:
    violations: list[str] = []
    for path in (BACKEND / "bridge").rglob("*.py"):
        for name in _imports(path):
            if name.startswith("toqraq.") and not name.startswith(
                ("toqraq.bridge", "toqraq.contracts", "toqraq.core")
            ):
                violations.append(f"{path.relative_to(BACKEND)}: {name}")
    assert violations == []


def test_api_package_contains_only_fastapi_presenters() -> None:
    api = BACKEND / "api"
    modules = list(api.rglob("*.py"))
    nested = [str(path.relative_to(BACKEND)) for path in modules if path.parent != api]
    non_presenters = [
        path.name
        for path in modules
        if path.name != "__init__.py"
        and not any(name.startswith(("fastapi", "starlette")) for name in _imports(path))
    ]

    assert nested == []
    assert non_presenters == []


def test_managed_home_location_belongs_to_hermes_boundary() -> None:
    assert (BACKEND / "hermes" / "paths.py").is_file()
    assert not (BACKEND / "core" / "paths.py").exists()


def test_engine_and_platform_adapters_do_not_import_outer_layers() -> None:
    violations: list[str] = []
    for root in (BACKEND / "engines", BACKEND / "platforms"):
        for path in root.rglob("*.py"):
            for name in _imports(path):
                if name.startswith(
                    ("toqraq.api", "toqraq.bridge", "toqraq.hermes", "toqraq.services")
                ):
                    violations.append(f"{path.relative_to(BACKEND)}: {name}")
    assert violations == []


def test_production_package_uses_relative_internal_imports() -> None:
    violations: list[str] = []
    paths = [*BACKEND.rglob("*.py"), REPO_ROOT / "dashboard" / "plugin_api.py"]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(
                    alias.name == "toqraq" or alias.name.startswith("toqraq.")
                    for alias in node.names
                ):
                    violations.append(str(path.relative_to(REPO_ROOT)))
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module
                and (node.module == "toqraq" or node.module.startswith("toqraq."))
            ):
                violations.append(str(path.relative_to(REPO_ROOT)))
    assert violations == []


def test_handwritten_source_size_debt_is_exact_and_does_not_expand() -> None:
    roots = [
        BACKEND,
        REPO_ROOT / "dashboard",
        REPO_ROOT / "engine" / "godot" / "modules" / "toqraq",
        REPO_ROOT / "scripts",
        RENDERER,
        REPO_ROOT / "tests",
    ]
    paths = [REPO_ROOT / "__init__.py"]
    for root in roots:
        paths.extend(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix in _HANDWRITTEN_SUFFIXES
        )
    oversized = {
        path.relative_to(REPO_ROOT).as_posix(): count
        for path in paths
        if path.relative_to(REPO_ROOT).as_posix() not in _GENERATED_SOURCE_PATHS
        if (count := len(path.read_text(encoding="utf-8").splitlines())) > 500
    }
    assert oversized == _KNOWN_SIZE_DEBT


def test_design_documents_respect_the_same_review_limit() -> None:
    oversized = {
        path.relative_to(REPO_ROOT).as_posix(): len(path.read_text(encoding="utf-8").splitlines())
        for path in (REPO_ROOT / "docs").glob("*.md")
        if len(path.read_text(encoding="utf-8").splitlines()) > 500
    }

    assert oversized == {}


def test_workflow_actions_are_immutable_commit_references() -> None:
    violations: list[str] = []
    for path in (REPO_ROOT / ".github" / "workflows").glob("*.yml"):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if "uses:" in line and _PINNED_ACTION.search(line) is None:
                violations.append(f"{path.name}:{line_number}")

    assert violations == []


def test_godot_candidate_build_cannot_select_or_publish_a_runtime() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "godot-candidate.yml").read_text(
        encoding="utf-8"
    )
    requirements = (REPO_ROOT / "engine" / "godot" / "build-requirements.txt").read_text(
        encoding="utf-8"
    )
    assert "upstream_tag:" in workflow
    assert "upstream_commit:" in workflow
    assert "custom_modules=$moduleCollection" in workflow
    option_block = re.search(r"GODOT_SCONS_ARGS: >-\n((?:    .+\n)+)", workflow)
    assert option_block is not None
    assert tuple(re.findall(r"[a-z0-9_]+=[A-Za-z0-9._+-]+", option_block.group(1))) == (
        GODOT_CANDIDATE_SCONS_ARGUMENTS
    )
    assert f"TOQRAQ_DISTRIBUTION_ID: {GODOT_RUNTIME_DISTRIBUTION_ID}" in workflow
    assert "git -C godot diff --exit-code" in workflow
    assert "scripts.package_godot_candidate" in workflow
    assert "TOQRAQ_GODOT_CANDIDATE_DIR" in workflow
    assert "test_integration_godot_native_bridge.py" in workflow
    assert "candidate-test-requirements.txt" in workflow
    assert "--only-binary=:all:" in workflow
    assert "toqraq.godot-candidate.v1" not in workflow
    assert "ConvertTo-Json" not in workflow
    assert "candidate.invalid" not in workflow
    assert "contents: read" in workflow
    assert "schedule:" not in workflow
    assert "release create" not in workflow
    assert "qixinh1/godot" not in workflow
    assert "--require-hashes" in workflow
    assert re.fullmatch(r"scons==[0-9.]+ --hash=sha256:[0-9a-f]{64}\n?", requirements)


def test_manifest_registration_and_schema_tool_names_match() -> None:
    manifest = (REPO_ROOT / "plugin.yaml").read_text(encoding="utf-8")
    assert _manifest_list(manifest, "provides_tools") == {spec.name for spec in TOOL_SPECS}
    assert _manifest_list(manifest, "provides_hooks") == {
        "on_session_finalize",
        "pre_llm_call",
    }


def test_standard_plugin_root_is_the_only_deploy_layout() -> None:
    required = [
        REPO_ROOT / "plugin.yaml",
        REPO_ROOT / "__init__.py",
        REPO_ROOT / "toqraq" / "hermes" / "registration.py",
        REPO_ROOT / "dashboard" / "__init__.py",
        REPO_ROOT / "dashboard" / "manifest.json",
        REPO_ROOT / "dashboard" / "plugin_api.py",
        REPO_ROOT / "desktop" / "plugin.js",
        REPO_ROOT / "skills" / "game-development" / "SKILL.md",
        REPO_ROOT / "skills" / "asset-workflow" / "SKILL.md",
        REPO_ROOT / "skills" / "balance" / "SKILL.md",
        REPO_ROOT / "skills" / "playtest-debug" / "SKILL.md",
        REPO_ROOT / "docs" / "README.md",
        REPO_ROOT / "LICENSE",
        REPO_ROOT / "THIRD_PARTY_NOTICES.md",
        REPO_ROOT / "README.md",
    ]
    assert all(path.is_file() for path in required)
    assert not (REPO_ROOT / "src" / "plugin").exists()
    assert not (REPO_ROOT / "dist").exists()
    required_scripts = {
        "build-renderer.mjs",
        "godot_candidate_evidence.py",
        "generate_contracts.py",
        "package_godot_candidate.py",
        "test-renderer.mjs",
        "typecheck-renderer.mjs",
        "verify_godot_candidate.py",
    }
    scripts = {path.name for path in (REPO_ROOT / "scripts").iterdir() if path.is_file()}
    assert required_scripts <= scripts
    assert not (REPO_ROOT / "component-catalog").exists()


def test_manifest_declares_the_v2_desktop_companion() -> None:
    manifest = (REPO_ROOT / "plugin.yaml").read_text(encoding="utf-8")
    assert _manifest_scalar(manifest, "manifest_version") == "2"
    assert _manifest_scalar(manifest, "desktop_entry") == "desktop/plugin.js"


def test_dashboard_manifest_is_api_only() -> None:
    manifest = json.loads((REPO_ROOT / "dashboard" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["api"] == "plugin_api.py"
    assert manifest["entry"] is None
    assert manifest["tab"] == {"hidden": True}


def test_package_identity_and_versions_match() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((REPO_ROOT / "package-lock.json").read_text(encoding="utf-8"))
    plugin = (REPO_ROOT / "plugin.yaml").read_text(encoding="utf-8")
    dashboard = json.loads((REPO_ROOT / "dashboard" / "manifest.json").read_text(encoding="utf-8"))
    renderer = (RENDERER / "index.ts").read_text(encoding="utf-8")
    runtime_version = (BACKEND / "version.py").read_text(encoding="utf-8")
    runtime_version_match = re.search(r'PLUGIN_VERSION\s*=\s*["\']([^"\']+)', runtime_version)
    assert runtime_version_match is not None
    versions = {
        project["project"]["version"],
        package["version"],
        lock["version"],
        lock["packages"][""]["version"],
        _manifest_scalar(plugin, "version"),
        dashboard["version"],
        runtime_version_match.group(1),
    }
    assert versions == {"0.1.0"}
    assert dashboard["name"] == _manifest_scalar(plugin, "name") == "toqraq"
    assert re.search(r"\bid:\s*['\"]toqraq['\"]", renderer)
    assert project["project"]["dependencies"] == []
    assert "version=PLUGIN_VERSION" in (REPO_ROOT / "scripts" / "contract_openapi.py").read_text(
        encoding="utf-8"
    )
    assert project["tool"]["mypy"]["strict"] is True
    assert "C90" in project["tool"]["ruff"]["lint"]["select"]
    assert project["tool"]["ruff"]["lint"]["mccabe"] == {"max-complexity": 15}
    assert project["tool"]["setuptools"]["packages"]["find"] == {
        "where": ["."],
        "include": ["toqraq", "toqraq.*"],
    }


def test_lockfile_uses_canonical_npm_registry() -> None:
    lock = (REPO_ROOT / "package-lock.json").read_text(encoding="utf-8")
    assert "registry.npmmirror.com" not in lock
    assert "https://registry.npmjs.org/" in lock


def test_relative_documentation_links_resolve() -> None:
    missing: list[str] = []
    documents = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "CONTRIBUTING.md",
        *REPO_ROOT.glob("docs/*.md"),
    ]
    for document in documents:
        for target in _MARKDOWN_LINK.findall(document.read_text(encoding="utf-8")):
            path_text = target.split("#", 1)[0]
            if not path_text or "://" in path_text or path_text.startswith("mailto:"):
                continue
            if not (document.parent / path_text).resolve().exists():
                missing.append(f"{document.relative_to(REPO_ROOT)} -> {target}")
    assert missing == []


def test_native_host_lookup_documentation_matches_the_current_port() -> None:
    """Keep preview trust claims within the evidence carried by NativeDisplay."""
    security = (REPO_ROOT / "docs" / "security.md").read_text(encoding="utf-8")
    preview = (REPO_ROOT / "docs" / "preview.md").read_text(encoding="utf-8")
    port = (BACKEND / "core" / "native_display.py").read_text(encoding="utf-8")

    assert "excluded_process_id: int" in port
    assert "pane screen point" in security
    assert "does not prove that\nthe selected host belongs to Hermes Desktop" in security
    assert "does\n  not prove that the selected window belongs to Hermes Desktop" in preview
    assert "- the selected host belongs to Hermes Desktop" not in security
