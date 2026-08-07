# Toqraq

Toqraq is a Hermes Desktop plugin for perceiving and developing normal
game-engine projects without leaving Hermes. It combines Hermes editing and
agent capabilities with owned engine processes, an in-pane preview, structured
runtime observation, deterministic input, and engine-aware verification.

Publishing games is outside the current scope.

## Current status

This repository contains one manifest-v2 Hermes plugin package:

- a minimal Python entry and API-only Dashboard backend sharing one container;
- one generated Desktop ESM companion entry;
- strict Pydantic contracts, short REST paths, sequenced session events, and
  seventeen generated-schema Hermes tools;
- four explicitly registered skills for game development, asset workflow,
  balance, and playtest/debug;
- an awaited session finalizer and a bounded `pre_llm_call` capsule for the
  calling task's live game or recognized active workspace;
- an exact managed-component store and asynchronous component jobs;
- session-owned process trees, bridge connections, native preview attachments,
  tasks, leases, and idempotent cleanup;
- a common authenticated JSON-RPC bridge and a Godot native module;
- focused hierarchy, object, diagnostic, process-output, metric, frame,
  simulation, and input services.

The public Hermes plugin manifest currently has no Desktop companion or shared
instance lifecycle. The manifest-v2 behavior used by local verification exists
only in the paired Hermes development worktree and have not been committed
upstream or released. A current public Hermes installation therefore cannot
yet install this package through the intended standard command.

The production composition is intentionally honest: read-only standard Godot
4 project recognition is registered, while `EngineCatalog` and the certified
component catalog are empty. Setup can identify a Godot project but reports
`runtime_unavailable`; Start returns a stable unavailable error. A normal
plugin installation cannot currently select or launch Godot, Unity, Unreal, or
Cocos.

The context capsule is capped at 2,048 characters. It prefers exact
live-session identity, process, readiness, preview, capability, and skill facts;
without a live game it may contain only the task-bound recognized-workspace
setup summary and skill names.

Godot 4.7.1 is the active candidate on Windows. A real instrumented editor has
passed the focused native suite and a production listener/feature-adapter
exercise covering all eight native capabilities, five input families,
pause/step/resume, and aspect-preserving PNG capture. No digest-pinned release
component has been published and admitted through the clean component-store,
standard-install, and interactive Desktop gates. This candidate is not a
supported ordinary runtime. A deterministic package and strict verification
workflow exists, but no real artifact from this repository revision has run
through it. See
[godot-candidate-build.md](docs/godot-candidate-build.md) and
[engine-support.md](docs/engine-support.md).

## Product model

Toqraq is organized around a simple user journey:

1. **Perceive** the project, running game, media, diagnostics, and performance.
2. **Develop** with Hermes editing, preview, control, debugging, assets,
   design, balance, and playtesting.
3. **Publish** later through a separately designed boundary.

Toqraq augments Hermes. It does not duplicate Hermes file, shell, Git,
provider, or delegation capabilities. It does not introduce a
proprietary project format, permanent agent organization, or mandatory game
production workflow.

The normative decisions are in [product.md](docs/product.md) and
[architecture.md](docs/architecture.md). The exact current API and remaining
release gates are in [api.md](docs/api.md) and
[implementation-status.md](docs/implementation-status.md).

## Installation contract

The only end-user installation path is:

```text
hermes plugins install <owner>/<repository> --enable
```

Under Toqraq's required manifest-v2 host contract, Hermes owns the Python,
Dashboard, Desktop, skill, finalizer, and disposer surfaces as one plugin
lifecycle. No manual file copy, separate Desktop deployment, runtime `pip
install`, executable-path setting, or globally installed engine is part of the
product flow. Engines and optional tools enter the managed component store only
after explicit setup in Hermes.

The repository and paired Hermes development worktree pass an isolated package
state/discovery exercise. That evidence does not prove a published host or a
cross-process drain of an already running plugin instance. Upstream host
integration, a released Desktop build, and an interactive clean-profile run
remain required; see [plugin-packaging.md](docs/plugin-packaging.md).

## Development

Use Python 3.11, Node 22 or later, and the checked-in dependency closures:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --disable-pip-version-check --only-binary=:all: --require-hashes --requirement requirements-dev.txt
npm ci
```

Run the baseline:

```powershell
python -m ruff check toqraq dashboard tests scripts __init__.py
python -m ruff format --check toqraq dashboard tests scripts __init__.py
python -m mypy
python -m pytest
python -m scripts.generate_contracts --check
npm test
npm run build
```

Candidate native, isolated Hermes lifecycle, and interactive Desktop suites
have additional explicit inputs. [development.md](docs/development.md) lists
the commands; [testing.md](docs/testing.md) defines what they prove.

## Documentation and contribution

Read [docs/README.md](docs/README.md) for the complete authority map and
[CONTRIBUTING.md](CONTRIBUTING.md) before editing. Every offered engine/version
must pass the full common baseline and clean-install evidence before any
support claim or catalog registration.

## License

[MIT](LICENSE)
