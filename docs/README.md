# Documentation Map

Toqraq documentation is an executable product and architecture contract. Read
the documents in the authority order below. A document that describes a future
gate says so explicitly; otherwise it describes the repository as it exists.

## Authority order

1. [product.md](product.md) defines product outcomes and non-goals.
2. [architecture.md](architecture.md) defines structure and ownership.
3. The focused document for a boundary defines its exact contract.
4. [coding-standards.md](coding-standards.md) defines binding implementation
   rules.
5. [testing.md](testing.md) defines acceptable evidence.
6. [implementation-status.md](implementation-status.md) records implementation status and
   remaining release gates.

A product change updates `product.md` first. A structural change updates
`architecture.md` before code. A focused contract links to its owner instead
of repeating it.

## Product and architecture

| Document | Responsibility |
| --- | --- |
| [product.md](product.md) | Perceive, Develop, deferred Publish, user journey, and support promise |
| [architecture.md](architecture.md) | dependency direction, ownership, catalog, session, bridge, and preview shape |
| [implementation-status.md](implementation-status.md) | current implementation status and the gates still open |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | contribution workflow and required checks |
| [coding-standards.md](coding-standards.md) | design, language, size, error, ownership, and review rules |

## Focused contracts

| Document | Responsibility |
| --- | --- |
| [api.md](api.md) | current REST, event, and seventeen Hermes tool contracts |
| [bridge.md](bridge.md) | current authenticated JSON-RPC engine bridge |
| [bridge-values.md](bridge-values.md) | common read and frame values carried by the bridge |
| [engine-adapters.md](engine-adapters.md) | complete engine contribution and capability baseline |
| [preview.md](preview.md) | preview surface ownership, native path, geometry, and Web admission |
| [godot-candidate-build.md](godot-candidate-build.md) | untouched-upstream Godot candidate build and admission boundary |
| [engine-support.md](engine-support.md) | current engine admission and vendor gates |
| [component-management.md](component-management.md) | exact managed components, jobs, leases, repair, and removal |
| [plugin-packaging.md](plugin-packaging.md) | one standard Hermes package and paired lifecycle |
| [hermes-integration.md](hermes-integration.md) | tools, hooks, finalization, disposer, skills, delegation, and bounded context |
| [desktop-ux.md](desktop-ux.md) | setup, preview, components, state, errors, and accessibility |
| [perception.md](perception.md) | bounded project, runtime, visual, diagnostic, and media evidence |
| [development-capabilities.md](development-capabilities.md) | editing, assets, design, balance, and playtest composition |
| [configuration.md](configuration.md) | setting owners, lifetimes, secrets, and literal policy |
| [errors-and-i18n.md](errors-and-i18n.md) | typed failures, trace IDs, envelopes, and translation ownership |
| [security.md](security.md) | trust boundaries, supply chain, process, bridge, path, and secret policy |
| [dependencies.md](dependencies.md) | dependency admission, reuse, packaging, and removal |
| [testing.md](testing.md) | automated unit, contract, native, real-engine, CI, and release gates |
| [interactive-testing.md](interactive-testing.md) | human-operated Desktop, preview, accessibility, cleanup, and release-journey evidence |
| [development.md](development.md) | current contributor setup and verification commands |

## Current availability

The manifest-v2 plugin package, seventeen tools, two hooks, four skills,
service graph, component machinery, common bridge, Windows process/display
adapters, and Godot candidate adapter/native-module source exist. The public
Hermes plugin manifest has no Desktop companion or shared instance lifecycle;
the host work used locally is not upstream or released. The plugin deliberately composes an empty
`EngineCatalog` and an empty certified component catalog, while separately
registering side-effect-free recognition of standard Godot 4 projects.
Therefore Setup can report a detected Godot project with
`runtime_unavailable`, and ordinary Start cannot launch an engine.

The repository records an earlier local Godot 4.7.1 observation covering the
native focused suite and production listener/feature-adapter exercise. That
history does not provide a published digest-pinned component, clean-store
admission, or interactive standard-install evidence. The deterministic
candidate package and verifier have synthetic tamper coverage but no recorded
real workflow artifact. Godot is consequently not selectable or advertised as
supported. Unity, Unreal, and Cocos remain outside the catalog. Publishing
games is deferred.

The `pre_llm_call` hook injects at most 2,048 characters of cached safe facts
for the exact `task_id`, preferring its live game and otherwise using its
recognized active-workspace summary. Toqraq asset sources and deterministic
media inspectors or transformers are not implemented.

## Documentation rules

- Write concise English and localize only product UI.
- Keep every handwritten document at or below 500 physical lines.
- State current, candidate, gated, or deferred status precisely.
- Do not document deleted routes, transports, adapters, or deployment paths.
- Link to the owning definition instead of copying large contracts.
- Use exact terms from `architecture.md`.
- Update links, schemas, examples, notices, and tests with their contract.
- Never call an engine supported without the evidence required by
  [testing.md](testing.md).

## Change routing

| Change | Document updated before code |
| --- | --- |
| product capability or non-goal | `product.md`, then `architecture.md` |
| ownership, dependency direction, or boundary | `architecture.md` |
| public request, result, event, or tool | `api.md` |
| engine contribution or bridge | `engine-adapters.md` or `bridge.md` |
| component or package lifecycle | `component-management.md` or `plugin-packaging.md` |
| Hermes hook, tool, skill, delegation, or context | `hermes-integration.md` |
| visible Desktop flow | `desktop-ux.md` and translation contract |
| human Desktop or real-engine interaction evidence | `interactive-testing.md` |
| dependency, security, or verification rule | its focused document |
