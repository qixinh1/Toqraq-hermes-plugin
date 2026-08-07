# Toqraq Architecture

This document is the structural source of truth for Toqraq. Current admission
status and remaining release gates are in
[implementation-status.md](implementation-status.md).

## Product boundary

Toqraq's outcomes, priority, active scope, deferred Publish scope, and non-goals live only in [product.md](product.md); architecture does not expand them.

## Current composition truth

The composed plugin process registers the standard Godot 4 project format in
the read-only `ProjectFormatCatalog`, while `EngineCatalog` and the certified
component catalog are empty. Setup can recognize a Godot workspace and returns
`runtime_unavailable` with bounded project facts; an unrecognized workspace is
reported as such. Start returns a typed unavailable failure. Godot runtime and
native-module code exists. The repository records an earlier local 4.7.1
candidate observation covering the focused native and production host-adapter
exercise, but no published digest-pinned component record has passed all
admission gates. No engine/version is currently selectable.

The plugin registers eighteen tools, four skills, `on_session_finalize`, a
bounded `pre_llm_call` capsule, and one async instance disposer. The capsule
prefers an exact live game and otherwise the recognized active workspace bound
to the same task. Publishing remains deferred.

The manifest-v2 package shape exists, but the public Hermes manifest has no companion field or shared Desktop lifecycle. The required behavior was exercised only in a paired local host with unpublished changes. This external gate permits no alternate Toqraq deployment path.

## Invariants

1. A running game is owned by exactly one Hermes session and uses that Hermes
   session ID. One Hermes session owns at most one running game.
2. Finalizing the Hermes session ends its game, process tree, bridge,
   attachments, temporary files, subscriptions, and background tasks.
3. Before launch, the active Hermes workspace is the ordinary project's sole
   identity source; the renderer never persists a competing path. Workspace
   preferences belong to that workspace. The renderer treats a transient
   empty or relative host value as unresolved and sends no setup request;
   services remain the authority for normalization and confinement. A running
   session retains its exact project root and resources even when the visible
   workspace changes.
   Process-wide component installations belong to Toqraq.
4. Ordinary source changes use visible Hermes editing tools. Runtime
   instrumentation never secretly writes to the project.
5. Every launch uses one exact prepared engine build. Detection, installation,
   launch, session state, and diagnostics refer to the same build identity.
6. Only engine packages know engine-native project, runtime, launch, and bridge
   details. Only platform packages know native windows and process primitives.
7. Tools, HTTP, sockets, hooks, and Desktop contributions are thin presenters
   over the same application services and typed contracts.
8. Engine and media components are isolated below `$HERMES_HOME/toqraq/`.
   Existing user engine installations are never selected or changed.
9. Loopback bridge connections authenticate the owning session, declare their
   exact protocol and capabilities, and reject any mismatch.
10. User-visible text is localized by the Hermes Desktop plugin i18n surface.
    Domain failures carry codes and parameters, not preformatted UI prose.
11. Large results are bounded, pageable, and retrievable on demand. Project
    inventory reads bind to one task and one live-game or workspace
    incarnation; context injection never includes trees, logs, binary media,
    or unbounded data.
12. A supported engine version passes the complete baseline capability and
    installation conformance suite for its platform.
13. A plugin-lifetime Desktop observer owns each task's workspace binding
    independently of pane visibility; newer probes, task finalization, and
    disposal prevent stale facts from returning.

## System shape

```text
Hermes Desktop
  -> lifecycle workspace observer and plugin presenters -> services -> core ports
                                     <- engine, component, and platform adapters
  -> task-bound project inventory -> engine project-format reader
  -> exact prepared runtime -> owned engine process tree
                               <-> authenticated engine bridge
  <- native preview (current) or admitted web preview -> Hermes pane
```

One process-local composition root uses no dependency injection framework, dynamic scanning, broker, database, or daemon without a demonstrated boundary.

## Standard Hermes plugin shape

The required distributable repository root is one Hermes plugin:

```text
/
|-- plugin.yaml
|-- __init__.py
|-- toqraq/
|-- dashboard/
|-- desktop/plugin.js
`-- skills/
```

The standard install command is
`hermes plugins install <owner>/<repository> --enable`.

Toqraq declares `manifest_version: 2` and `desktop_entry: desktop/plugin.js`.
The released Hermes host must load that entry from the installed plugin root;
install, update, enable, disable, and remove must own both plugin surfaces as
one lifecycle. The host must load the complete package or reject installation.
This is Toqraq's only deployment path. The unreleased host work and remaining
transaction semantics are in [plugin-packaging.md](plugin-packaging.md).

The package contains its prebuilt Desktop entry, skills, translations, notices,
and exact admitted release records. Large components install on demand; the
API-only Dashboard backend and Python entry share one process-local container.

## Source boundaries

The target package structure follows product capabilities and external boundaries:

```text
toqraq/
|-- core/                 pure values, ports, errors, and ownership models
|-- contracts/            Pydantic boundary requests, results, and events
|-- services/             application use cases and the composition root
|-- engines/              project formats and admitted engine contribution packages
|   |-- godot/
|   |-- unity/
|   |-- unreal/
|   `-- cocos/
|-- components/           download, verify, install, repair, and remove
|-- platforms/            process and display implementations
|-- bridge/               authenticated engine transport and feature adapters
|-- hermes/               exact tool routing/results, hooks, lifecycle, context, and managed-home location
`-- api/                  FastAPI routes and event sockets
```

The handwritten Desktop source and tests are strict TypeScript; every hand-edited file below `src/renderer/` ends in `.ts`. `.js` and `.tsx` are prohibited there. Rendering continues through `jsx()`/`jsxs()`. Relative runtime imports use final ESM `.js` specifiers; type-only edges use `import type`. Generated `contracts/openapi.json`, `contracts/generated.d.ts`, and `contracts/runtimeRules.ts` remain Pydantic-derived schema outputs; `desktop/plugin.js` remains the build output.

```text
src/renderer/
|-- bridge/               focused REST/event clients, transport, safe reads, and semantic decoders
|-- contracts/            generated DTO declarations and structural runtime rules
|-- contributions/        pane, status, and Stop palette registration
|-- hooks/                React ownership effects
|-- i18n/                 locale bundles and parity checks
|-- lib/                  focused geometry and safe-value primitives
|-- state/                workspace sync, session, setup, component, event, and preview owners
`-- ui/                   setup, component, toolbar, status, and preview views
```

Dependency direction is enforced:

```text
presenters -> services -> core ports
                         ^
engine, component, and platform adapters
```

- `core` imports only the standard library.
- `contracts` may use Pydantic and converts to or from core values.
- services never import a concrete engine or platform package.
- presenters never call concrete adapters.
- the composition root explicitly registers engine contributions and concrete
  adapters.
- an engine package never imports another engine package.

## Engine contribution contract

Read-only project perception and runtime admission are separate. An
`EngineProjectFormat` composes one stable engine ID, side-effect-free
`ProjectProbe`, and read-only `ProjectInventoryReader`; all three identities
must agree. A complete `EngineContribution` owns that exact format plus runtime
catalog, provisioner, launch planner, and preview locator. The format catalog
may therefore recognize and inventory a standard project before a launchable
engine is admitted; `EngineCatalog` contains only complete certified runtime
contributions. Neither operation implies installation, launch, Bridge,
preview, or support.

An engine contribution is explicit composition of small, typed boundaries, not a universal base class:

```text
EngineContribution
|-- EngineProjectFormat
|   |-- engine ID
|   |-- ProjectProbe
|   `-- ProjectInventoryReader
|-- RuntimeCatalog
|-- RuntimeProvisioner
|-- GameLaunchPlanner
`-- PreviewLocator
```

- `descriptor` owns the stable engine ID, display metadata, settings schema,
  supported platform policy, and capability declarations.
- `ProjectProbe` detects and analyzes a project and reports only a version the
  project format actually declares.
- `RuntimeCatalog` lists exact builds that passed Toqraq conformance.
- `RuntimeProvisioner` locally verifies and leases the selected installed build; component jobs mutate it.
- `GameLaunchPlanner` converts one project, `PreparedRuntime`, bridge endpoint,
  child environment, and bootstrap into the platform-owned `ProcessLaunch`.
- `PreviewLocator` returns a preview surface without common lookup rules.

One shared adapter set creates focused ports from the authenticated common bridge. Engine differences stay in native mappings and extension facts; no per-engine feature factory exists.

Adding an engine requires one engine package, one explicit catalog registration, and its conformance tests. Session services, tools, API routes, and the Desktop flow do not change.

The process-local format catalog is an immutable explicit set of project
formats. The engine catalog is an immutable explicit set of complete runtime
contributions, each reusing the exact format registered for its ID. Both
preserve order, reject duplicate IDs, and only provide lookup; probing,
inventory, and runtime selection remain application use cases.
The engine set may be empty when no runtime has passed every admission gate.
That is a valid standard-plugin setup state, not permission to register an
incomplete contribution or one with no selectable certified release. Shared
selection still probes registered formats; a recognized format with no engine
contribution becomes runtime-unavailable. With no registered format, selection
returns a distinct engine-unavailable outcome without probing. Start translates
both unavailable outcomes to stable typed application failures.

Project and runtime selection are one application policy shared by setup,
tools, and Start:

1. normalize one project root and run either the explicitly selected format
   probe or every registered format probe;
2. return a focused choice when zero or several formats match instead of
   defaulting to Godot;
3. return runtime-unavailable when the selected format has no admitted engine
   contribution;
4. filter the selected contribution's releases to the exact host platform and
   architecture;
5. apply an exact workspace version choice, otherwise an exact project-declared
   version, otherwise select only when one certified release remains;
6. return a version choice when several releases remain, never a common-layer
   "latest" heuristic;
7. pass the resulting `RuntimeRelease` object directly into local preparation
   and launch during Start.

Setup is a read-only projection of this policy and returns the selected
release's opaque component IDs for consent and component jobs. It is not a
persisted launch ticket. Start reruns the same deterministic policy against the
immutable bundled catalog and the workspace choice, then performs no further
selection inside the provisioner or launch planner.

The detailed contract lives in [engine-adapters.md](engine-adapters.md).

## Common capability baseline

The stable user intentions are:

- detect and analyze a project;
- list, select, install, verify, repair, and remove an exact engine version;
- start, stop, restart, pause, resume, and step a game;
- show the game in the Hermes preview pane;
- capture a frame;
- read a bounded runtime hierarchy;
- inspect selected runtime objects and properties;
- read bounded diagnostics and process output;
- send semantic, keyboard, pointer, text, and gamepad input;
- read a bounded performance snapshot;
- report feature readiness and exact runtime identity.

These intentions are expressed through focused ports such as
`HierarchyReader`, `ObjectReader`, `DiagnosticsReader`, `FrameCapture`,
`SimulationController`, `InputController`, and `MetricsReader`. Public object
references are opaque strings. Engine packages retain native Node,
GameObject/Component, Actor/Component, and Cocos object semantics in their
typed result extensions.

Capability IDs are validated namespaced strings. Core defines the mandatory
baseline IDs; an engine contribution may add namespaced capabilities without
editing a central enumeration. A missing baseline capability means that exact
engine build is not offered as supported.

## Exact runtime and component ownership

Runtime selection is a single unbroken value flow:

```text
ProjectProbe result + workspace choice
  -> project-runtime selection returns one catalog RuntimeRelease
  -> RuntimeProvisioner.prepare(that exact release)
  -> PreparedRuntime(that release, verified entry points, owned leases)
  -> PendingStart owns prepared runtime, bridge listener, and launch resources
  -> GameLaunchPlanner.plan(...) returns one exact ProcessLaunch
  -> ProcessTreeLauncher.launch(that exact plan)
  -> EngineSession owns the resulting process tree and feature ports
```

`RuntimeRelease` is the only runtime launch credential. A provisioner does not
query a catalog, resolve a selection again, replace the release, or compare it
with a newly created equivalent object. For one `(engine ID, public version,
platform, architecture)` the catalog exposes at most one selectable certified
release. Build and distribution identities remain exact internal facts, but do
not create an unexplained second choice for the user.

The selected `RuntimeRelease` is also the sole source of its ordered, opaque
component release IDs. Setup results return those IDs verbatim. Desktop,
presenters, and common services must never reconstruct a component identity
from an engine ID, display label, version string, filename, or naming
convention. Each runtime entry point is bound explicitly to one of those
component release IDs and to one certified component entry-point name; runtime
preparation never searches several installed components and chooses a matching
filename or name by convention.

Distribution channel, archive name, executable search, and vendor installer
details remain private to the engine contribution. The ordinary UI asks only
when detection is ambiguous or the user explicitly overrides engine or
version.

Managed components live only below `$HERMES_HOME/toqraq/`. Explicit jobs own acquisition, repair, removal, progress, cancellation, and atomic publication before Start. The launch path only verifies the selected installation, acquires its lease, and resolves certified entry points. Lease transfer is the ownership commit; any later cancellation uses normal session cleanup.

Selectable releases are immutable `ComponentRelease` values explicitly constructed by composition.
Runtime has no generic record loader or second catalog; a new build updates its adapter, value, tests, notices, digest, and provenance together.

Vendor login and license acceptance remain explicit Hermes setup states. Component storage,
resumption, locking, integrity, leases, and failure semantics are defined only in
[component-management.md](component-management.md).

## Runtime bridge

Every engine has a small native bridge written against its official extension
system and in its supported language.

The common transport is authenticated JSON-RPC 2.0 over a loopback WebSocket. Messages use
schema-defined bounded JSON; captures use bounded binary frames or artifact references.

The first message is an exact handshake containing session token, engine ID, build identity, bridge protocol, and native RPC capabilities. An undecodable or wrong-credential candidate is rejected without consuming the launch.
Once the credential is proven, any certified owner, runtime, bridge, protocol, or capability mismatch atomically consumes the listener and terminal-fails feature readiness instead of waiting
for another candidate.

Each launch receives bounded one-shot bootstrap bytes containing its random session credential.
On Windows the exact child environment contains only validated `SYSTEMROOT` and private `APPDATA`.
It inherits neither `PATH` nor parent variables. A private pipe delivers bootstrap before creation;
credentials never enter arguments or environment. Listeners bind only to loopback, accept only the owner, bound work, and close every waiter on teardown.

Authentication transfers the winning socket into a session-owned controlled connection: the sole
reader and owner of IDs, correlation, deadlines, cancellation, invalidation, and close. A listener
owner holds authentication and exactly-once claim; a connection owner arbitrates termination,
retryable transport close, and disconnection publication. Raw sockets never enter feature ports.
One dispatcher correlates and decodes responses; one transfer owner consumes an announced binary
frame or fails the connection. Seven focused Core adapters close over their original query or
command and return only correlated Core values. Services never receive sockets, JSON-RPC
envelopes, transfer announcements, or a generic engine-execution surface. Exact wire and teardown
rules live in [bridge.md](bridge.md).

Session use cases depend on one `RuntimeFeatureConnection`: its endpoint is available for launch,
`wait_ready` returns the seven focused ports after authentication, and `close` owns every listener
and connection state. A factory opens this boundary from an exact handshake expectation.

Live feature use cases do not cache, wrap, or own those borrowed ports. `HierarchyService`,
`ObjectInspectionService`, `DiagnosticsService`, `MetricsService`, `FrameCaptureService`, and
`InputService` each acquire the same session-scoped operation gate used by lifecycle mutations,
resolve the exact current owner from `SessionRegistry`, require the corresponding namespaced
Bridge capability and feature-group readiness, and invoke the focused port through the session's
`GameRunResources.invoke_owned`. The gate remains held until the bounded call and result
correlation complete, so stop, replacement, and finalization cannot withdraw a borrowed port
mid-operation.

`ProcessOutputService` is independent of Bridge readiness and capabilities. It acquires that
same session gate, resolves the exact current owner, and synchronously snapshots the
session-owned `ProcessTree` before releasing the gate. The public projection preserves global
stdout/stderr sequence order and the source snapshot's loss and failed-stream state, while
retaining only the latest 16,384 Unicode characters. It has no cursor, history store, polling
task, or persistence layer; stop, replacement, and finalization therefore cannot withdraw the
process owner during a read.

Hierarchy, object, diagnostic, metric, frame-query, and input request/result shapes reuse the
strict Pydantic Bridge parameter and value models where their public JSON meaning is identical.
Services never accept JSON-RPC envelopes or binary-transfer announcements. Frame capture alone
has a separate public result: it replaces the Bridge transfer announcement with one canonical,
strictly validated base64 PNG while preserving viewport, encoded size, revision, timestamp,
length, MIME type, and digest. The binary transfer ID and socket ownership never cross the Bridge
adapter.

Godot upstream source remains unmodified. CI checks out an exact upstream tag,
adds `engine/godot/modules/toqraq` through Godot's custom module build path,
tests the built executable, then build-only scripts reuse production component
algorithms to emit and independently verify a deterministic candidate ZIP before
its exact executable enters Bridge. Neither script enters runtime composition.

## Session lifecycle

`EngineSession.id` is the owning Hermes session ID. Starting a replacement for the same session is
transactional: validation and runtime preparation finish before ownership changes exactly once.

The start use case completes project/runtime selection before issuing a run
revision, credential, or `PendingStart`; rejected selection owns no cleanup.
Immediately before first fallible resource acquisition, a new `PendingStart`
owns runtime, bridge listener and credential, process tree, bounded output,
attachment tasks, and preview discovery. A live process and successful exact
compare-and-swap promote it to `EngineSession`; feature readiness then settles
independently. An unauthenticated bridge creates no feature port but does not
hide or destroy an otherwise playable process. Failure or cancellation leaves
every acquired resource owned until idempotent cleanup succeeds.

Process state and feature readiness are independent facts:

```text
process: preparing -> starting -> running <-> paused -> stopping -> ended
                              `-> crashed

features:
  preview: unavailable | connecting | ready | failed
  perceive: unavailable | connecting | ready | failed
  control: unavailable | connecting | ready | failed
```

This avoids a state for every combination while still telling the user whether
the game is alive and whether the model can observe or control it.

The session owns:

- a process-tree owner exposing the stable root identity, bounded exit and
  output observation, and idempotent complete-tree cleanup rather than a
  public child-process inventory;
- bounded stdout and stderr collectors;
- the authenticated bridge and feature ports;
- the active preview surface and display attachment;
- subscriptions, temporary artifacts, cancellation scopes, and cleanup tasks.

On supported Windows hosts the process tree enters both process-lifetime and session
kill-on-close Job Objects atomically before its initial thread executes. No Hermes handle becomes
inheritable, no suspended or post-create recovery path exists, and failed native cleanup remains owned
and blocks another launch. Child membership remains a Windows-internal authority check for atomic
launch, window closure, and complete-tree termination; it is not a common runtime query. Exact
process and window rules live in
[engine-adapters.md](engine-adapters.md) and [security.md](security.md).

The Windows output collector owns both read pipes until one explicit close mode completes. Once
the complete process tree and root writer have ended, cleanup drains both pipes to EOF before
releasing them so buffered tail output remains observable. If writers may still be alive, rollback
or failed termination aborts collection instead of waiting for EOF. Both paths are bounded; a
drain timeout retains the collector and pipe ownership for the next cleanup retry rather than
silently discarding unread bytes.

Natural exit, explicit stop, replacement, plugin shutdown, and `on_session_finalize` use the same
idempotent cleanup operation. Failed cleanup remains owned and retryable. Successful session cleanup
removes the active run; Toqraq stores no execution history.

The host disposer is the sole process-container release path. It awaits `Container.close()`, then
under the composition lock compare-and-clears only that exact process-local instance. Failure or
cancellation retains the sealed instance for retry; re-enable builds a fresh graph only after success.

The registry rejects an unqualified overwrite. Replacement supplies the expected prior session and
an internal run revision, and commits only if that exact owner is current; it is not a user selector.
Desktop stop carries the revision it observed and the service compares that owner inside the same
gate; the client accepts only a response for that revision. A stale request cannot stop or clear a
replacement run and refreshes presentation from an authoritative read. The Hermes tool intentionally
stops the current run owned by its own calling session.
One process-local keyed operation gate serializes ownership changes for the same Hermes session
across host event loops. Waiting cancellation cannot strand a successor; unrelated sessions remain parallel.
`SessionOwnership` synchronizes pending starts, orphan runs, finalization, and one 64-slot reservation per distinct active or pending Hermes ID.
Successful terminal cleanup releases that slot and the registry's completed revision after host finalization.
Finalization tombstones reject duplicate work until plugin closure clears them after every owner has drained.
Session tasks and Desktop session state have incarnation owners, never module globals. One plugin-lifetime `RendererSessionSync` owns host-readiness checks, the selected REST snapshot, and its event subscription; it projects readiness plus session truth into one injected `RendererSessionStore` after host status succeeds. Pane and status subscribe to that projection, palette actions read it directly, and pane unmount never ends synchronization. One focused query-key module owns every TanStack cache identity. `ViewportPane` composes setup, lifecycle, display, and view results, while `ComponentSetup` composes one managed-component plan and controller over presentation-only cards and progress.

## Preview contract

One session owns one engine-located preview surface; one stable renderer pane delegates layout and chrome to Hermes. The current presenter path is a reversible Windows `NativeWindowSurface` with authoritative aspect-fit geometry; one pure renderer projection alone determines native attachability and pane placeholder state. `WebSurface` is only a validated Core value until a real contribution closes its security, renderer, lifecycle, and interactive gates. See [preview.md](preview.md).

## Perception

Perception is read-only, typed, bounded, and source-attributed. The explicit
project-inventory service first captures the caller task's exact live session,
or otherwise its recognized workspace object, and resolves that format's
reader. Scope reaches the reader before one owned, cooperatively cancelled
filesystem worker scans only that subtree.
After scanning, the service re-resolves the preferred binding and rejects a
replacement before sorting, filtering, revisioning, or paging. Its strict
stateless cursor binds shape revision, scope, categories, and offset; it owns no cache,
watcher, index, REST route, file-content read, or project write. See
[project-inventory.md](project-inventory.md) and [perception.md](perception.md).

## Hermes agent-harness integration

Toqraq registers focused tools, lifecycle hooks, namespaced skills, and a conditional bounded context capsule. It projects an exact cached live game or recognized workspace for that task. Every delegated child has an independent task ID, while task-owned tools bind only to their caller. The parent gathers bounded evidence, retains game control, and verifies child summaries; children perform bounded independent leaves. Workspace synchronization owns ordering and stale clearing. No permanent agents or large prompt are added. See [hermes-integration.md](hermes-integration.md).

## Development and media workflows

Hermes owns ordinary file work and the media tools enabled for a task. Toqraq adds engine-aware validation, observation, control, provenance, license filters, and narrow managed transformations. See [development-capabilities.md](development-capabilities.md).

## Contracts, errors, configuration, and i18n

Pydantic is the single boundary-schema source; core stays Pydantic-free. Domain errors carry code,
category, safe fields, cause, and trace ID; Desktop owns localized text. See
[configuration.md](configuration.md) and [errors-and-i18n.md](errors-and-i18n.md).

## Security and supply chain

Components have verified identity and provenance. External data and processes cross explicit
bounded trust boundaries; secrets remain in Hermes or vendor stores. See [security.md](security.md).

## Verification gates

Architecture tests enforce dependency, generation, i18n, renderer source-extension, explicit-`any`,
and size invariants; the renderer type gate includes production and tests in one strict Program.
Every offered engine/version still passes the complete real-engine gates in [testing.md](testing.md).
