# AGENTS.md

Read this file before editing the repository. The complete document map is
[docs/README.md](docs/README.md).

## Mission

Toqraq is a Hermes Desktop plugin that lets a user and model perceive and
develop a standard game-engine project without leaving Hermes. A running game
is owned by exactly one Hermes session and uses that session ID. Finalizing the
session releases its process tree, bridge, preview, tasks, and temporary
resources.

The current production engine catalog is empty. A Godot 4.7.1 Windows candidate
exercises the first engine contribution without making that engine selectable.
The target is one standard Hermes plugin with isolated versioned engine
contributions, a common capability baseline, native-window and web previews,
bundled skills, conditional model context, and creative tooling. Unity, Unreal,
and Cocos enter the selectable catalog only after the gates in
`docs/engine-support.md` close. Publishing is deferred.

## Sources of truth

Read in this order:

1. `docs/product.md` — product outcomes and non-goals.
2. `docs/architecture.md` — structural truth and ownership.
3. the focused target document for the boundary being changed.
4. `docs/coding-standards.md` — binding code and design rules.
5. `docs/testing.md` — completion evidence.
6. `docs/implementation-status.md` — current phase and exit criteria.

`docs/godot-candidate-build.md` owns the untouched-upstream candidate pipeline.
`docs/api.md`, `docs/bridge.md`, and `docs/development.md` describe current
implementation only. Do not use Godot-native concepts as new multi-engine
abstractions.

## Non-negotiable design rules

1. Update `docs/product.md` before a product-scope change and
   `docs/architecture.md` before a structural change.
2. Before adding code, ask whether it must exist, whether Hermes, the engine,
   the platform, an approved component, or existing code already provides it,
   and what displaced code can be deleted.
3. Enforce SRP, OCP, ISP, and dependency inversion through small real
   boundaries. Do not create layers merely to name a design pattern.
4. Prefer deletion, direct composition, immutable values, and explicit
   ownership. Do not retain alternate paths, unused settings, dead events, or
   speculative extension points.
5. Every handwritten source and test file is at most 500 physical lines. At
   450 lines, review its responsibilities. Generated, lock, vendor, upstream,
   and built files are exempt and never hand-edited.
6. A small or one-line file is justified when it owns a stable responsibility
   or boundary. Forwarding shells and generic `utils`, `helpers`, `common`, or
   `manager` buckets are prohibited.
7. Variable user text, paths, engine versions, download sources, product
   policies, timeouts, provider choices, and limits do not appear as scattered
   literals. Stable protocol and safety constants live in their owning module
   and have direct tests.
8. Application errors carry stable code, category, safe parameters/details,
   cause, and trace ID. Desktop translates user-visible text through Hermes
   plugin i18n. Technical diagnostics remain bounded source text.
9. Internal layers use typed values. `Any` or `unknown` exists only at an
   external decode boundary and is converted immediately.
10. Every task, process, socket, subscription, native mutation, temporary file,
    and component job has one strong owner, cancellation, bounded waits,
    observed failure, and idempotent cleanup.

## Architecture boundaries

- `core` contains pure values, ports, errors, and ownership models and imports
  only the standard library.
- `contracts` uses Pydantic as the single source for HTTP, Hermes tool, result,
  event, and generated Desktop DTO schemas.
- services implement use cases and import no concrete engine, component,
  media, process, or platform adapter.
- the process-local composition root explicitly registers all concrete
  contributions.
- engine packages own project detection, version syntax, distribution,
  provisioning policy, launch, bridge mapping, and preview location.
- platform packages own process-tree and native-display primitives, not engine
  semantics.
- API, sockets, Hermes registration, tools, hooks, and Desktop are thin
  presenters over the same services and contracts.

Adding an engine means one engine package, one explicit catalog registration,
and conformance tests. It must not add engine switches to common services,
tools, API routes, or the ordinary Desktop flow.

## User and project boundaries

- Ordinary source changes use visible Hermes file tools.
- Instrumentation never silently writes to a project.
- Managed engines and tools live below `$HERMES_HOME/toqraq/` and use absolute
  paths.
- Existing user engine installations are ignored; behavior must be identical
  whether they exist or not.
- Never install a Python package into the shared Hermes interpreter at plugin
  runtime or mutate `PATH`, file associations, global engine settings, or a
  user engine installation.
- Vendor authentication and license acceptance remain explicit user actions in
  the Hermes setup flow.
- Secrets stay in Hermes or vendor secret stores and never enter renderer
  storage, source, logs, events, command lines, or model context.

## Hermes contracts

- Python entry: `plugin.yaml` and `register(ctx)`.
- Game tool handlers target the caller's Hermes `task_id` and return JSON
  strings; they do not accept another game-session selector.
- under the required manifest-v2 host contract, async `on_session_finalize` is
  awaited and uses the same stop and cleanup operation as explicit stop;
- the container registers one async disposer; that host contract must await it
  before unload and retain a failed old plugin instance for retry;
- Dashboard routes remain below Hermes' Toqraq plugin API namespace.
- The Desktop entry is one ESM default export using public Hermes SDK
  contributions.
- Bundled skills are namespaced and loaded explicitly.
- Specialist work uses Hermes `delegate_task`; Toqraq does not register a
  permanent agent system.
- `pre_llm_call` context is conditional and bounded; it never includes full
  trees, logs, media bytes, or a large fixed prompt.

Toqraq's required manifest-v2 contract makes the Desktop companion entry part
of the standard plugin lifecycle. The public host does not implement it yet;
the required behavior is defined in `docs/plugin-packaging.md`. Do not conceal
missing host behavior with an out-of-band deployment path.

## Current repository map

| Path | Current responsibility |
| --- | --- |
| `plugin.yaml`, `__init__.py` | standard Hermes manifest and minimal Python entry |
| `toqraq/core/` | current pure models, errors, and ports |
| `toqraq/components/` | managed-package records, catalog, extraction, and lifecycle primitives |
| `toqraq/services/` | engine-neutral setup, session, display, perception, control, and component use cases |
| `toqraq/engines/godot/` | candidate Godot project, runtime, launch, bridge, and preview contributions |
| `toqraq/platforms/windows/` | standard-library process-tree and native-display adapters |
| `toqraq/hermes/` | Hermes tools, schemas, registration, hooks, and bounded context |
| `dashboard/` | API-only Dashboard backend loaded in the plugin namespace |
| `desktop/plugin.js` | generated, committed Desktop companion entry |
| `src/renderer/` | current JavaScript Desktop source |
| `engine/godot/modules/toqraq/` | authenticated JSON-RPC Godot bridge module source |
| `scripts/` | deterministic Desktop build script |
| `tests/` | Python, renderer, and integration tests |

The package layout and dependency direction are defined in
`docs/architecture.md`. Candidate engine-native details must stay inside their
engine contribution and must not become common service abstractions.

## Editing and dependencies

- Use `rg` and `rg --files` for discovery.
- Use `apply_patch` for hand edits.
- Never edit `desktop/plugin.js`, generated contracts, lockfiles, or
  upstream/vendor source by hand.
- Keep unrelated worktree changes intact.
- Add no dependency before updating `docs/dependencies.md` and
  `CONTRIBUTING.md` with its exact role and review evidence.
- Python uses Ruff, strict Mypy, Google-style docstrings, and argument-vector
  subprocess calls.
- Target Desktop source is strict TypeScript compiled to ESM and uses
  `jsx()`/`jsxs()`, not JSX syntax.
- Comments explain invariants, ownership, bounds, or non-obvious reasons; they
  do not narrate change history.

## Verification

Current baseline:

```powershell
python -m ruff check toqraq dashboard tests scripts __init__.py
python -m ruff format --check toqraq dashboard tests scripts __init__.py
python -m mypy
python -m pytest
npm test
$env:TOQRAQ_HERMES_SOURCE = "C:\path\to\hermes-agent"
npm run typecheck
npm run build
```

Run the smallest complete matrix in `docs/testing.md`, including real-engine,
standard-install, and interactive Desktop tests when their boundaries change.
The final report names commands run and external suites not run.

## Change agreement

- Use Conventional Commits.
- Update `CHANGELOG.md` for user-visible behavior.
- Update docs, schemas, translations, notices, generated artifacts, tests, and
  deleted code in the same cohesive change.
- Do not call an engine/version supported without complete baseline
  conformance and clean-install evidence.
- Do not call a task complete while required work, cleanup, or verification
  remains.
