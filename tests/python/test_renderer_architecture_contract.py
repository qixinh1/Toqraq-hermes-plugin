"""Executable source, type, build, and host-boundary rules for Desktop."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
RENDERER = REPO_ROOT / "src" / "renderer"
_IMPORT = re.compile(r"\bfrom\s+['\"]([^'\"]+)['\"]|\bimport\s+['\"]([^'\"]+)['\"]")
_EXTERNALS = {"@hermes/plugin-sdk", "react", "react/jsx-runtime"}
_TYPE_SCRIPTING = re.compile(r"@(typedef|type|param|returns|template|satisfies)\b")
_EXPLICIT_ANY = re.compile(r"\bas\s+any\b|:\s*any\b|<any>|\bany\[\]|\bArray\s*<\s*any\s*>")
_GENERATED_TYPESCRIPT = {
    RENDERER / "contracts" / "generated.d.ts",
    RENDERER / "contracts" / "runtimeRules.ts",
}


def _handwritten_typescript() -> list[Path]:
    return sorted(path for path in RENDERER.rglob("*.ts") if path not in _GENERATED_TYPESCRIPT)


def _production_typescript() -> list[Path]:
    return [path for path in _handwritten_typescript() if not path.name.endswith(".test.ts")]


def test_renderer_has_one_strict_typescript_source_shape() -> None:
    forbidden = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in RENDERER.rglob("*")
        if path.is_file() and path.suffix in {".js", ".jsx", ".tsx"}
    )
    source = _handwritten_typescript()

    assert forbidden == []
    assert source
    assert (RENDERER / "index.ts") in source
    assert any(path.name.endswith(".test.ts") for path in source)


def test_renderer_types_do_not_use_javascript_type_escape_hatches() -> None:
    scripting: list[str] = []
    explicit_any: list[str] = []
    for path in _handwritten_typescript():
        source = path.read_text(encoding="utf-8")
        relative = path.relative_to(REPO_ROOT).as_posix()
        if "@ts-check" in source or _TYPE_SCRIPTING.search(source):
            scripting.append(relative)
        if _EXPLICIT_ANY.search(source):
            explicit_any.append(relative)

    assert scripting == []
    assert explicit_any == []


def test_renderer_external_import_closure_is_exact() -> None:
    external: set[str] = set()
    for path in _production_typescript():
        source = path.read_text(encoding="utf-8")
        for match in _IMPORT.finditer(source):
            module = match.group(1) or match.group(2)
            if module and not module.startswith("."):
                external.add(module)

    assert external == _EXTERNALS


def test_renderer_translation_calls_use_the_positional_sdk_contract() -> None:
    named_object_call = re.compile(
        r"(?<![\w.])t\(\s*(?:'[^']+'|`[^`]+`)\s*,\s*\{",
        flags=re.DOTALL,
    )
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in _production_typescript()
        if named_object_call.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []


def test_status_chip_checks_the_public_status_dot_props() -> None:
    source = (RENDERER / "ui" / "StatusChip.ts").read_text(encoding="utf-8")

    assert "satisfies ComponentProps<typeof StatusDot>" in source
    assert re.search(r"jsx\(StatusDot,\s*\{\s*status:", source) is None


def test_generated_contracts_are_type_only_dependencies() -> None:
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in _handwritten_typescript()
        if re.search(
            r"\bimport\s+(?!type\b)[^;\n]*contracts/generated(?:\.js)?['\"]",
            path.read_text(encoding="utf-8"),
        )
    ]
    assert offenders == []


def test_runtime_decoders_consume_generated_structure_without_restating_it() -> None:
    consumers = [
        RENDERER / "bridge" / "componentDecoders.ts",
        RENDERER / "bridge" / "decoders.ts",
        RENDERER / "bridge" / "errorBoundary.ts",
        RENDERER / "bridge" / "previewDecoders.ts",
        RENDERER / "bridge" / "sessionDecoders.ts",
    ]
    displaced_apis = (
        "boundedString(",
        "closedString(",
        "exactRecord(",
        "finiteNumber(",
        "matchingString(",
        "nullableString(",
        "optionalRecord(",
        "safeInteger(",
    )
    for path in consumers:
        source = path.read_text(encoding="utf-8")
        assert "../contracts/runtimeRules.js" in source
        assert not any(api in source for api in displaced_apis)
        assert re.search(r"const\s+\w+\s*=\s*/\^", source) is None


def test_generated_runtime_rules_are_exactly_the_imported_decoder_set() -> None:
    generated = (RENDERER / "contracts" / "runtimeRules.ts").read_text(encoding="utf-8")
    exports = set(re.findall(r"^export const (\w+Rules) =", generated, flags=re.MULTILINE))
    imports: set[str] = set()
    for path in _production_typescript():
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(
            r"import\s*{([^}]*)}\s*from\s*['\"]\.\./contracts/runtimeRules\.js['\"]",
            source,
            flags=re.DOTALL,
        ):
            imports.update(name.strip() for name in match.group(1).split(",") if name.strip())

    assert imports == exports


def test_hermes_owns_layout_workspace_and_pane_chrome() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in _production_typescript())
    contribution = (RENDERER / "contributions" / "main.ts").read_text(encoding="utf-8")
    viewport = (RENDERER / "ui" / "ViewportPane.ts").read_text(encoding="utf-8")
    viewport_setup = (RENDERER / "hooks" / "useViewportSetup.ts").read_text(encoding="utf-8")
    setup_guide = (RENDERER / "ui" / "SetupGuide.ts").read_text(encoding="utf-8")

    assert "placement: 'bottom'" in contribution
    assert "useViewportSetup" in viewport
    assert "host.state.cwd" in viewport_setup
    assert "ctx.storage" not in source
    assert "panePlacement" not in source
    assert "pane.placement" not in source
    assert "SegmentedControl" not in source
    assert "paneOpen" not in source
    assert "project.${hermesSession" not in source
    assert "onCommitDir" not in source
    assert "KEYBINDS_AREA" not in source
    assert "setup.action.start" in setup_guide
    assert not (RENDERER / "lib" / "settings.ts").exists()
    assert not (RENDERER / "state" / "viewportState.ts").exists()


def test_renderer_has_one_plugin_lifetime_session_and_preview_projection() -> None:
    session_sync = (RENDERER / "state" / "rendererSessionSync.ts").read_text(encoding="utf-8")
    contribution = (RENDERER / "contributions" / "main.ts").read_text(encoding="utf-8")
    native_display = (RENDERER / "hooks" / "useNativeDisplay.ts").read_text(encoding="utf-8")
    viewport = (RENDERER / "ui" / "ViewportPane.ts").read_text(encoding="utf-8")
    status = (RENDERER / "ui" / "StatusChip.ts").read_text(encoding="utf-8")
    surface = (RENDERER / "ui" / "ViewportSurface.ts").read_text(encoding="utf-8")

    assert re.search(r"ctx\.own\(\s*startRendererSessionSync", contribution)
    assert "createSessionEventConsumer" in session_sync
    assert "openEvents" in session_sync
    assert "sessionStore.gameState" in viewport
    assert "sessionStore.gameState" in status
    assert "sessionStore.currentSession()" in contribution
    assert "startRendererSessionSync" not in viewport
    assert not (RENDERER / "hooks" / "useHermesGame.ts").exists()
    assert "listSessions" not in "\n".join(
        path.read_text(encoding="utf-8") for path in _production_typescript()
    )
    assert "projectNativePreview(session, attachmentState)" in native_display
    assert "previewView" in viewport
    assert "previewView" in surface
    for duplicate in ("toqraq.preview.display", "preview.state", "preview.surface"):
        assert duplicate not in viewport
        assert duplicate not in surface


def test_renderer_query_cache_identity_has_one_owner() -> None:
    owner = RENDERER / "state" / "queryKeys.ts"
    owner_source = owner.read_text(encoding="utf-8")
    hardcoded = re.compile(r"\[\s*['\"]toqraq['\"]\s*,")
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in _production_typescript()
        if path != owner and hardcoded.search(path.read_text(encoding="utf-8"))
    ]
    consumers = [
        RENDERER / "contributions" / "main.ts",
        RENDERER / "hooks" / "useComponentSetup.ts",
        RENDERER / "hooks" / "useViewportSetup.ts",
    ]

    assert offenders == []
    for function in (
        "hermesSessionQueryKey",
        "componentCatalogQueryKey",
        "activeComponentJobsQueryKey",
        "componentJobQueryKey",
        "workspaceSetupQueryRoot",
        "workspaceSetupQueryKey",
    ):
        assert f"function {function}" in owner_source
    for consumer in consumers:
        assert "../state/queryKeys.js" in consumer.read_text(encoding="utf-8")
    workspace_sync = (RENDERER / "state" / "workspaceContextSync.ts").read_text(encoding="utf-8")
    assert "QueryKey" not in workspace_sync
    assert not hardcoded.search(workspace_sync)


def test_renderer_build_owns_the_committed_companion_entry() -> None:
    build = (REPO_ROOT / "scripts" / "build-renderer.mjs").read_text(encoding="utf-8")
    ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "src/renderer/index.ts" in build
    assert "desktop/plugin.js" in build or "outdir = 'desktop'" in build
    assert "dist/desktop-plugins" not in build
    assert "dist/" in {line.strip() for line in ignored}


def test_renderer_typecheck_uses_one_paired_strict_program() -> None:
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    typecheck = (REPO_ROOT / "scripts" / "typecheck-renderer.mjs").read_text(encoding="utf-8")

    assert package["scripts"]["typecheck"] == "node scripts/typecheck-renderer.mjs"
    assert "TOQRAQ_HERMES_SOURCE" in typecheck
    assert "@hermes/plugin-sdk" in typecheck
    assert "rendererTypeScript(RENDERER_ROOT)" in typecheck
    assert ".test.ts" not in typecheck
    for option in (
        "exactOptionalPropertyTypes: true",
        "isolatedModules: true",
        "noUncheckedIndexedAccess: true",
        "noUnusedLocals: true",
        "noUnusedParameters: true",
        "strict: true",
        "verbatimModuleSyntax: true",
    ):
        assert option in typecheck
    assert "allowJs: true" not in typecheck
    assert "checkJs: true" not in typecheck
    assert "SyntaxKind.AnyKeyword" in typecheck
    assert "typescript" not in package["devDependencies"]


def test_renderer_tests_compile_in_one_owned_temporary_directory() -> None:
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    runner = (REPO_ROOT / "scripts" / "test-renderer.mjs").read_text(encoding="utf-8")

    assert package["scripts"]["test"] == "node scripts/test-renderer.mjs"
    assert "endsWith('.test.ts')" in runner
    assert "mkdtemp" in runner
    assert "spawnSync(process.execPath, ['--test'" in runner
    assert "discardOwnedTestDirectory" in runner
    assert "from 'esbuild'" in runner
