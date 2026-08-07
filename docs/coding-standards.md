# Coding Standards

This document defines the binding implementation rules for Toqraq. The
architecture and product boundaries remain authoritative in
[architecture.md](architecture.md). When a rule appears to conflict with the
architecture, stop and resolve the architecture first.

## Decision order

For every new file, abstraction, dependency, and non-trivial block, answer
these questions before writing code:

1. Must this behavior exist for the current Perceive or Develop contract?
2. Does Hermes, an engine SDK, the standard library, or a maintained component
   already provide it?
3. Can an existing cohesive implementation be extended without gaining a
   second reason to change?
4. Is the proposed boundary real: engine, operating system, process, network,
   persistence, media executable, or Hermes host?
5. What is the simplest typed design that keeps ownership and failure paths
   explicit?
6. Does the design add policy, state, indirection, or configuration that no
   current requirement needs?
7. How will the behavior be tested, cancelled, cleaned up, localized, and
   diagnosed?

Delete code that has no current caller or contract. Do not retain alternate
implementations, speculative extension points, or unused configuration.

## Core design rules

### Single responsibility principle

A module, class, or function has one reason to change.

- A service implements one use case or one tightly cohesive use-case family.
- A protocol models one external boundary or one focused runtime capability.
- Parsing, validation, transport, presentation, and persistence are separate
  responsibilities.
- Engine-native rules remain inside their engine contribution.
- Platform-native rules remain inside their platform adapter.
- User-visible formatting remains in presenters and Desktop i18n.
- Composition belongs only in the process-local composition root.

A small file is acceptable when it owns a real concept. A one-line forwarding
module with no boundary, policy, ownership, or stable import purpose is not.

### Open/closed principle

Stable application behavior is extended through declared contribution points,
not by adding engine conditionals throughout the codebase.

- Adding an engine adds one engine package, one explicit catalog registration,
  and conformance tests.
- Adding an engine version adds a catalog record, its exact managed component,
  and conformance evidence.
- Adding an engine-native capability uses a validated namespaced capability ID
  and an engine-owned typed extension.
- Services, ordinary tools, API routes, and the preview flow do not branch on
  `godot`, `unity`, `unreal`, or `cocos`.
- Distribution channels, executable names, bridge formats, and vendor install
  details are private to the owning engine contribution.

Open/closed does not mean dynamic class scanning or a plugin system inside the
plugin. Explicit composition is preferred. Adding one registration at the
composition root is an intended extension, not an architectural violation.

### Interface segregation principle

Consumers depend only on the operations they use.

- Do not create a universal engine base class with every possible operation.
- Use focused ports such as `ProjectProbe`, `RuntimeProvisioner`,
  `HierarchyReader`, `FrameCapture`, `InputController`, and
  `SimulationController`.
- Do not use an untyped `execute(name, payload)` escape hatch for baseline
  capabilities.
- Optional capabilities are independently discoverable and independently
  fail with a typed capability error.
- Public object references are opaque values; core does not assume an engine's
  integer IDs or object hierarchy.

### Dependency inversion

The required direction is:

```text
Hermes, HTTP, socket, and Desktop presenters
  -> application services
  -> core values and ports
  <- engine, component, media, process, and platform adapters
```

- `core` imports only the Python standard library.
- `contracts` may import Pydantic and converts to or from core values.
- Services do not import concrete engines, platforms, or media backends.
- Presenters do not call concrete adapters.
- Engine packages do not import other engine packages.
- Tests enforce these directions from the Python syntax tree.

## Avoiding over-design

Use a design pattern only when it names and solves an observed design problem.
There is no pattern quota.

Do not introduce:

- a dependency injection framework around the explicit container;
- a broker for process-local events;
- a database while project files are authoritative;
- dynamic discovery where one explicit catalog is sufficient;
- factories that only call one constructor and encode no selection policy;
- repositories for in-memory collections with no persistence boundary;
- abstract base classes with one implementation and no external contract;
- configuration for a value that has one stable protocol-defined meaning;
- a generic utility or helpers bucket.

Prefer deletion, direct composition, immutable values, small protocols, and
plain functions. Extract shared code only after the callers share the same
semantics, bounds, failure policy, and reason to change.

## File-size gate

Every handwritten source and test file must contain at most 500 physical
lines. CI rejects a larger file.

- At 450 lines, the author must review the file's responsibilities before
  adding more behavior.
- Generated files, lockfiles, vendored upstream sources, and compiled bundles
  are excluded from the size gate and must never be edited by hand.
- A file is not split merely to hide lines behind forwarding wrappers.
- Split along parsing, encoding, transport, ownership, policy, or presentation
  boundaries.
- Tests may be split by behavior or invariant, never by arbitrary line ranges.

The gate is a trigger for design review, not permission to create empty
layers.

## Types and contracts

- Python is 3.11 or newer and uses postponed annotations.
- Public functions, methods, attributes, callbacks, and return values are
  completely typed.
- Internal application code does not pass `Any`, arbitrary dictionaries, or
  unvalidated JSON between layers.
- `Any` is confined to a named external decoding boundary and is converted
  immediately to a typed value or rejected.
- Prefer immutable, keyword-only dataclasses for core values.
- Use enums only for genuinely closed vocabularies. Extensible capability IDs
  are validated namespaced strings, not a central enum.
- Pydantic models in `contracts` are the single boundary-schema source for
  HTTP, Hermes tools, results, and events.
- Core models never depend on Pydantic and never serialize themselves for a
  particular presenter.
- Engine bridge payloads are validated again at the process boundary because
  they are untrusted data, not because boundary contracts may be duplicated.
- Avoid boolean parameters whose call sites do not explain their meaning; use
  an enum, command value, or separate method when that is clearer.
- Use opaque identifiers for engine objects, attachments, operations, and
  components. Validate them before lookup or path construction.

## Functions and control flow

- A function operates at one level of abstraction.
- Use guard clauses to reject invalid state before the main path.
- Keep ownership transactions explicit; do not hide process creation, file
  publication, or native mutation in a property accessor.
- Do not catch `Exception` inside core logic. Catch only errors that can be
  translated, compensated, or deliberately isolated.
- Broad exception guards are allowed at task, plugin, tool, HTTP, socket, and
  native callback boundaries and must log a trace ID.
- Never discard an exception silently. An intentionally ignored error needs a
  concise ownership or best-effort reason.
- Do not use mutable module globals for sessions, jobs, caches, or task
  ownership. The container owns process-local state.
- Do not make a domain model responsible for HTTP, tool, UI, or event JSON.

## Async, process, and resource ownership

- Use async code for concurrent I/O. Keep pure parsing, geometry, hashing,
  argument construction, and schema conversion synchronous.
- Blocking process, filesystem, archive, native-window, and media operations
  run outside the event-loop thread.
- Every background task has a strong owner, descriptive name, cancellation
  path, completion observation, and logged failure path.
- Fire-and-forget calls without an owning task supervisor are prohibited.
- Every wait has an explicit timeout or is tied to an owned process lifetime.
- Cancellation must not interrupt atomic publication or ownership cleanup.
  Complete the transaction, then propagate cancellation.
- A launched game is an owned process tree, not only a PID.
- Standard output and error are bounded and observed; they are never sent to
  `DEVNULL` for an interactive development launch.
- Resource cleanup is idempotent, runs in reverse acquisition order, and keeps
  failed resources owned for retry.
- Natural exit, explicit stop, replacement, plugin shutdown, and Hermes
  finalization use the same cleanup operation.

## Configuration and literals

Every variable value has one owner, as defined by the architecture.

The following must not appear as scattered literals:

- user-visible text and labels;
- engine versions, distribution URLs, archive names, and executable paths;
- provider or model selections;
- component storage paths;
- product policy, retry policy, and user-experience timeouts;
- cross-layer identifier and payload limits.

Stable protocol IDs, error codes, file signatures, and security bounds may be
constants. They must be named, colocated with their owning protocol or policy,
and directly tested. Do not create a global constants bucket.

Secrets are obtained from Hermes-owned secure configuration. They never enter
Desktop storage, source files, subprocess command text visible to the model,
logs, events, or context injection.

## Error and localization rules

- Internal failures use the typed system in
  [errors-and-i18n.md](errors-and-i18n.md).
- Core and services carry error code, category, parameters, safe details,
  cause, and trace ID; they do not format user-interface prose.
- Tool, HTTP, and validation failures use one public error envelope.
- Desktop is the owner of localized user-visible text.
- Hermes plugin translation forwards interpolation arguments positionally.
  Locale functions and call sites use the same declared order; a named object
  is not an alternate interpolation protocol.
- Technical engine output is bounded diagnostic data and is not localized.
- Comments, docstrings, logs, protocol identifiers, and code symbols are
  concise English.

## Python

- Ruff formatting and linting are authoritative.
- Cyclomatic complexity is bounded at 15. A violation is closed by reducing a
  real responsibility or state transition, not by suppression or mechanical forwarding.
- Mypy runs in strict project mode; new ignores require a reason on the same
  line and a test of the unsafe boundary.
- Public modules, classes, and functions have concise Google-style docstrings.
- Prefer structural `Protocol` ports over inheritance when implementations do
  not share code or state.
- Use `pathlib.Path` at filesystem boundaries and resolve before security
  decisions.
- Use `logging`; do not add a second logging framework. Structured context is
  supplied through adapters or `extra` fields.
- Do not invoke shell text when an argument-vector subprocess API is available.

## Desktop TypeScript

- Every handwritten production and test source below `src/renderer/` is strict
  TypeScript with a `.ts` or `.test.ts` suffix. Handwritten `.js` and `.tsx`
  files are prohibited there.
- Production and tests compile in one no-emit Program using the paired Hermes
  compiler, SDK mapping, and React declarations. `allowJs` and `checkJs` are
  never enabled.
- Imports are limited to the Hermes plugin SDK, React, and
  `react/jsx-runtime` unless the public Hermes contract changes.
- Source uses `jsx()` and `jsxs()`, not JSX syntax. Relative runtime imports
  retain final ESM `.js` specifiers; type-only edges use `import type`.
- The low-level JSX runtime does not validate a component's props object.
  Component-specific Hermes SDK props are checked explicitly with
  `satisfies ComponentProps<typeof Component>` when ordinary DOM props do not
  already prove the public vocabulary.
- `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`,
  `isolatedModules`, `verbatimModuleSyntax`, `noUnusedLocals`, and
  `noUnusedParameters` are enabled.
- Explicit `any`, `@ts-check`, and JSDoc type scaffolding are prohibited.
  Untrusted values enter as `unknown` only at an external boundary and are
  decoded immediately into an internal type.
- `contracts/generated.d.ts`, `contracts/runtimeRules.ts`, and
  `contracts/openapi.json` come from the Pydantic source, and
  `desktop/plugin.js` comes from the renderer build. These generated artifacts
  are never hand-edited or used as handwritten-code exceptions elsewhere.
- Renderer tests use the existing esbuild dependency to compile into one
  invocation-owned temporary directory, run through `node --test`, and remove
  that directory. The test path adds no compiler or runtime dependency.
- Use public Hermes SDK state, storage, i18n, notification, and component
  surfaces instead of private Desktop internals or local host replacements.
- A small session-keyed store owns REST reconciliation and event updates.
  Introduce no general state framework until repeated cross-contribution state
  behavior demonstrates the need.
- Every effect has symmetric cleanup. Network requests and long mutations are
  cancellable.
- Components render state and user intent; backend ownership and engine policy
  remain in services.
- Use Hermes theme variables and components. Hardcoded colors and visible
  strings are prohibited.

## Engine bridge languages

Engine bridges follow both these standards and the engine's official style.

- Godot and Unreal C++ use their engine allocation, threading, naming, and
  error conventions. Do not introduce C++ exceptions where the engine forbids
  them.
- Unity C# follows the supported Unity/.NET profile, avoids blocking the main
  thread, and makes cancellation and object lifetime explicit.
- Cocos TypeScript uses strict types and the supported editor/runtime APIs.
- Engine object access occurs on the engine-approved thread.
- Network parsing never directly mutates engine objects; validated commands
  are transferred to the engine thread.
- Every bridge implements one exact protocol version and fails the handshake
  on any mismatch.
- Bridge additions change schemas, adapter code, native implementation,
  documentation, and contract tests together.

## Dependencies and reuse

Choose implementations in this order:

1. a public Hermes host capability;
2. an official engine or platform API;
3. a maintained, appropriately scoped open-source component;
4. a small repository-owned implementation when the contract is unique.

A new dependency requires documentation of:

- the single responsibility it replaces;
- maintenance and license status;
- package and installed size;
- security and update policy;
- why existing Hermes, engine, standard-library, or repository code is
  insufficient.

Do not add frameworks for dependency injection, state machines, events,
logging, or HTTP while the direct implementation remains clear. Exact engine
wire codecs and bounded archive policies may remain repository-owned when a
general package cannot implement their contract safely.

## Review checklist

A change is ready for review only when:

- its behavior belongs to the current architecture scope;
- displaced code, options, tests, and documentation are deleted;
- dependency direction and ownership remain explicit;
- the design satisfies SRP, OCP, and ISP without speculative layers;
- every handwritten file is at most 500 lines;
- no new scattered product, path, version, timeout, UI, or error literals were
  introduced;
- public and wire inputs are bounded and typed;
- async work has cancellation and cleanup;
- errors and UI text follow the shared localization system;
- tests cover success, failure, cancellation, and cleanup where applicable;
- the required matrix in [testing.md](testing.md) passes.
