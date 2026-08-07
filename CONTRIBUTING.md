# Contributing

Every contribution must improve the product contract in
[product.md](docs/product.md) and move the repository toward
[architecture.md](docs/architecture.md). Binding implementation rules live in
[coding-standards.md](docs/coding-standards.md).

## Before writing code

1. Read [AGENTS.md](AGENTS.md) and the relevant entries in
   [the documentation map](docs/README.md).
2. Inspect current callers, tests, contracts, and external host or engine APIs.
3. Answer the decision questions in `coding-standards.md`: must the behavior
   exist, who already provides it, what can be deleted or extended, where is
   the real boundary, and what is the smallest typed design?
4. Update `product.md` first for a scope change and `architecture.md` first for
   a structural change. Update the focused target document before code.
5. State the user outcome, ownership, failure path, deletion scope, and tests
   in the change description.

Do not reduce discovery, reasoning, failure handling, or verification because
a task appears small. Small changes cross the same product and security
boundaries as large changes.

## Change shape

- Keep a change cohesive and reviewable, but complete its selected ownership
  path from contract through adapter and presenter.
- Prefer deletion and direct composition over wrappers and indirection.
- Keep one execution path for each behavior; delete displaced code in the
  same cohesive change.
- Remove unused options, events, settings, helpers, tests, documentation, and
  translations in the same cohesive change.
- Preserve unrelated user changes in a dirty worktree.
- Generated artifacts are rebuilt by their owning command and never edited by
  hand.
- Every handwritten source and test file must contain at most 500 physical
  lines. Review responsibilities at 450 lines.

## Architecture and organization

- Core contains pure values, ports, errors, and ownership models.
- Contracts are the Pydantic source for HTTP, Hermes tools, application DTOs,
  events, and generated Desktop types.
- Services implement product use cases and depend only on core ports.
- Engine, component, media, process, and platform implementations remain at
  their external boundaries.
- Only the composition root imports and assembles concrete contributions.
- A new engine adds one package, one catalog registration, and conformance
  tests. It does not add engine conditionals to ordinary use cases or UI.
- A module and file have one reason to change. Do not create generic `utils`,
  `helpers`, `common`, or `manager` buckets.

Production currently registers no engine. The verified Godot candidate may
enter only through the complete admission gates in
[implementation-status.md](docs/implementation-status.md). Engine-native types never become
the multi-engine contract.

## Dependencies

Follow [dependencies.md](docs/dependencies.md). Prefer a public Hermes or
engine API, then a maintained focused component, then a small owned
implementation.

A dependency change must document its one role, maintenance, license,
redistribution, security, size, packaging location, update path, and removal
cost. Update lockfiles, notices, component manifests, and tests together.

Python verification uses the generated, hash-pinned `requirements-dev.txt`
directly from the source tree. Never replace it with an unconstrained
`pip install .[dev]`. Change exact direct versions in `pyproject.toml`,
regenerate the complete wheel closure with the command in `dependencies.md`,
review every transitive change, and prove a clean Python 3.11 install with
`--only-binary=:all: --require-hashes` on Windows and Linux.

Build dependencies follow the same rule. Godot's SCons requirement is exact
and hash-pinned; workflow actions use full commits. Updating either requires a
candidate build, provenance review, and the affected real-engine matrix.
The post-link Godot verification environment is separately closed and
hash-pinned in `engine/godot/candidate-test-requirements.txt`; update every
direct and transitive wheel together, prove Windows/Python 3.12 resolution with
`--require-hashes`, and rerun packaging, tamper, and real Bridge tests. Change
its three direct pins in `engine/godot/candidate-test-requirements.in` and
regenerate the lock with the command in `godot-candidate-build.md`.

The engine listener uses the exact `websockets` version supplied by Hermes;
the plugin never installs it. A Hermes pin change requires the bridge
handshake, framing, flow-control, timeout, disconnect, cleanup, and
clean-profile tests before Toqraq may rely on the new version.

Renderer type checking likewise uses the paired Hermes Desktop checkout's
TypeScript compiler, React declarations, and public SDK mapping. Install that
checkout's Desktop dependencies and set `TOQRAQ_HERMES_SOURCE`; do not add a
second TypeScript dependency to Toqraq. Renderer tests use Toqraq's existing
esbuild dependency only as a temporary compiler before `node --test`.

Never install a package into the shared Hermes interpreter at plugin runtime or
depend implicitly on a system executable.

## Language and documentation rules

- Python 3.11+ uses complete types, Ruff, strict Mypy, Google-style public
  docstrings, `pathlib`, argument-vector subprocess calls, and owned asyncio
  tasks.
- Every handwritten renderer production and test file is strict `.ts`; `.js`
  and `.tsx` are prohibited below `src/renderer/`. Rendering uses
  `jsx()`/`jsxs()` rather than JSX syntax.
- One paired-Hermes TypeScript Program checks production and tests with
  `strict`, unchecked-index, exact-optional, isolated-module, verbatim-module,
  and unused-symbol rules. It never enables `allowJs` or `checkJs`.
- Explicit `any`, `@ts-check`, and JSDoc type scaffolding are prohibited.
  Relative runtime imports use final ESM `.js` specifiers and type-only edges
  use `import type`.
- OpenAPI, `generated.d.ts`, `runtimeRules.ts`, and `desktop/plugin.js` are
  generated; every other renderer source follows the handwritten TypeScript rules.
- Native bridges follow the official Godot, Unity, Unreal, or Cocos language
  and thread rules.
- Comments and docstrings are concise English and explain reasons, invariants,
  bounds, or ownership. They do not narrate edit history.
- Visible Desktop text, accessibility labels, and user errors use Hermes
  plugin i18n. English and Simplified Chinese key sets are identical.
- Follow the status and single-owner documentation rules in
  [docs/README.md](docs/README.md).

## Errors, security, and resources

- Raise typed application errors internally and serialize only at presenter
  boundaries.
- Use the envelope, categories, localization, diagnostic, and trace rules in
  [errors-and-i18n.md](docs/errors-and-i18n.md).
- Treat engine, network, archive, component, media, path, and native-window
  data as untrusted at their boundaries.
- Bound before allocation or dispatch.
- Every process, task, socket, subscription, native mutation, temporary file,
  and component job has a strong owner and idempotent cleanup.
- Never log or place secrets in source, events, renderer storage, subprocess
  arguments visible to the model, or context capsules.
- Follow [security.md](docs/security.md) for the full trust model.

## Tests

Use [testing.md](docs/testing.md) to select the smallest complete matrix. Every
change covers relevant success, invalid input, external failure, cancellation,
race, and cleanup behavior.

In an activated Python 3.11 virtual environment, current baseline commands are:

```powershell
python -m pip install --disable-pip-version-check --only-binary=:all: --require-hashes --requirement requirements-dev.txt
$env:TOQRAQ_HERMES_SOURCE = "C:\path\to\hermes-agent"
python -m ruff check toqraq dashboard tests scripts __init__.py
python -m ruff format --check toqraq dashboard tests scripts __init__.py
python -m mypy
python -m pytest
npm run typecheck
npm test
npm run build
```

Real-engine, standard-install, and interactive Desktop jobs are required when
their boundaries change. A final report names every command run and every
external suite not run. A passing unit suite is not sufficient evidence for a
user-visible release.

## Change and release metadata

- Use Conventional Commits with an imperative subject.
- Keep commits cohesive and do not mix unrelated formatting.
- Update `CHANGELOG.md` for user-visible behavior.
- Update package identity, catalogs, notices, generated contracts, and built
  artifacts together.
- Use exact engine and component versions with provenance in release evidence.
- Do not label an engine/version supported until its baseline conformance and
  clean-install gates pass.

## Review checklist

A reviewer should be able to answer yes to all of these:

- Does this implement a current Perceive or Develop outcome?
- Is every new abstraction backed by a real variation or external boundary?
- Could existing Hermes, engine, platform, dependency, or project code do it?
- Are responsibilities separated without speculative layers?
- Can a new engine implement the common intention without editing this use
  case?
- Is every value typed and every untrusted input bounded?
- Are ownership, cancellation, cleanup, diagnostics, and recovery explicit?
- Are user text and errors localized without losing technical evidence?
- Are all handwritten files within the size gate?
- Were displaced code and documents deleted?
- Do the relevant automated and real-boundary tests pass?
