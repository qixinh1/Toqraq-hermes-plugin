# Development and Verification

This document contains commands for the repository as it exists. Product and
architecture decisions live in [product.md](product.md) and
[architecture.md](architecture.md); evidence requirements live in
[testing.md](testing.md).

## Local setup

Use Python 3.11+, Node.js, and PowerShell on Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
npm ci
```

Desktop development also requires a chosen paired Hermes source checkout.
Install its Desktop workspace dependencies, then point Toqraq at it:

```powershell
Push-Location C:\path\to\hermes-agent
npm run install:desktop
Pop-Location
$env:TOQRAQ_HERMES_SOURCE = "C:\path\to\hermes-agent"
```

`npm run typecheck` reads that checkout's Desktop `tsconfig.json`, public
`@hermes/plugin-sdk` mapping, TypeScript compiler, and React declarations. It
creates one no-emit strict Program for every renderer production and test
source; it never enables `allowJs` or `checkJs`. Record the checkout's exact
HEAD and dirty state: it is authoritative only for that local run, not evidence
of released Hermes support. Toqraq does not install a second compiler.

The plugin never performs this installation at runtime. Hermes supplies the
base interpreter dependencies; local development extras belong only to the
repository environment.

Generate contracts and build the committed Desktop companion:

```powershell
python -m scripts.generate_contracts
npm run typecheck
npm run build
```

Contract generation atomically writes
`src/renderer/contracts/openapi.json`,
`src/renderer/contracts/generated.d.ts`, and
`src/renderer/contracts/runtimeRules.ts`. The Desktop build writes
`desktop/plugin.js`. All four are generated artifacts and are never edited by hand.

Every other file below `src/renderer/` is handwritten `.ts` or `.test.ts`.
There is no `.tsx`: rendering calls `jsx()` and `jsxs()` directly. Relative
runtime imports keep `.js` specifiers for final ESM, while type-only imports use
`import type`. Explicit `any`, `@ts-check`, and JSDoc type scaffolding fail the
repository contract.

## Source direction

Backend calls move in one direction:

```text
HTTP or Hermes tool -> focused service -> core port -> concrete adapter
```

`toqraq/services/container.py` is the only process-local composition root.
Hermes tools and Dashboard routes use the same container. Engine packages own
engine facts, Windows owns process/display primitives, and presenters own no
engine logic.

For a structural change:

1. update `docs/architecture.md` and the focused contract;
2. change pure values and ports;
3. change focused services;
4. change the owning adapter;
5. change contracts and thin presenters;
6. regenerate Desktop contracts and the ESM entry;
7. delete displaced code, tests, and documentation;
8. run the smallest complete verification matrix.

## Baseline checks

```powershell
python -m ruff check toqraq dashboard tests scripts __init__.py
python -m ruff format --check toqraq dashboard tests scripts __init__.py
python -m mypy
python -m pytest
python -m scripts.generate_contracts --check
npm run typecheck
npm test
npm run build
```

The unit suite runs without an engine. It covers dependency rules, strict
contracts, empty-catalog behavior, component transactions, Bridge transport,
session ownership, process cleanup, Windows display operations, and renderer
state. `npm run typecheck` checks all renderer production and test sources with
the complete strict option set. `npm test` uses existing esbuild to compile
them into a command-owned temporary directory, invokes `node --test`, and
removes the output. `npm run build` rejects generated-contract drift before
producing the single ESM entry.

## Standard Hermes lifecycle

The only package path exercised by users is:

```text
hermes plugins install <owner>/<repository> --enable
```

The external lifecycle suite uses a temporary committed source and isolated
Hermes home. It never copies the Desktop entry into a profile or changes the
developer's active installation:

```powershell
$env:TOQRAQ_HERMES_SOURCE = "C:\path\to\hermes-agent"
python -m pytest -m hermes_integration
```

That suite proves local-Git installation, installed Desktop-byte identity,
surface discovery, enable/disable/update/remove state, and post-removal absence
against the selected paired development tree. It does not execute the Electron
companion or prove finalizer awaiting, active-instance disposer ordering,
failure retention, force reload, or host shutdown. Those require focused host
and interactive evidence. A release still requires the published repository
and clean published host in [plugin-packaging.md](plugin-packaging.md).

Because the production engine and certified component catalogs are empty, a
standard local install currently proves only read-only Godot project
recognition and the setup pane's `runtime_unavailable` state. It does not prove
a playable Godot release.

## Godot candidate verification

The candidate pipeline builds the module beside an exact untouched upstream
Godot checkout. Follow [godot-candidate-build.md](godot-candidate-build.md);
do not copy the module into an upstream tree or patch upstream files.

For a Windows editor built with `tests=yes`, supply that exact candidate as a
test artifact:

```powershell
$env:TOQRAQ_GODOT_CANDIDATE_DIR = "C:\candidate"
python -m pytest tests/python/test_integration_godot_native_bridge.py -m integration -vv
```

The integration test strictly verifies canonical evidence and checksums,
extracts through the production component policy, and exercises that exact
packaged executable through the production listener and feature adapters. It
covers eight native capabilities, five input families, pause/step/resume,
bounded PNG capture, and cleanup without creating a component release or
catalog registration.

The repository records an earlier local Godot 4.7.1 observation of 27 native
cases with 197 assertions and the production host-adapter exercise. This is
native-boundary history only. It does not create a digest-pinned component
record or close clean-store, standard-install, and interactive preview gates.

## Interactive Desktop checks

Before a user-visible release, use a clean Hermes profile and the exact
certified component candidate under review. Verify:

1. the package loads through the standard command;
2. setup shows only catalog-backed choices and exact component facts;
3. install progress, cancellation, retry, and remount recovery remain owned;
4. Start attaches the real game surface;
5. wide and tall pane resizing preserves the complete game frame;
6. minimize, restore, redock, and session switching keep ownership correct;
7. all model reads, input forms, simulation controls, and capture work;
8. finalization and plugin disposal leave no process, window, socket, task,
   temporary file, or lease.

## Diagnostics

| Symptom | Check |
| --- | --- |
| Setup reports no engine | expected while the production catalog is empty; inspect bundled certified records before changing UI |
| Component job fails | use its stable error, operation ID, phase, source, digest, and trace ID |
| Start is unavailable | confirm the exact release is certified, listed by Setup, and already prepared |
| Bridge does not become ready | compare intrinsic build, owner, protocol, capability, and bootstrap facts |
| Native preview cannot attach | inspect the typed `/preview/native/attach` failure and physical pane geometry |
| Preview does not follow resize | inspect `/preview/native/rect`, attachment ownership, authoritative viewport size, and server-side aspect-fit geometry |
| Capture is rejected | inspect request ceilings, announcement, binary length, digest, PNG, and dimensions |
| Cleanup fails | retry the same owner operation; do not discard the retained resource graph |
