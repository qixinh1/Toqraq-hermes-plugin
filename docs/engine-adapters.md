# Engine Contribution Contract

This document defines the implemented contribution contract and the admission
rules for adding engines to Toqraq. Production currently composes an empty
catalog. Godot has candidate runtime-catalog, provisioner, launch-planner,
preview-locator, and native-module code plus a verified Windows 4.7.1 candidate,
but none of those runtime ports is instantiated by production; Unity, Unreal,
and Cocos remain outside the catalog.

## Objective

Toqraq presents one Hermes Desktop experience across supported engines:

- detect and understand the current project;
- select and prepare an exact engine version;
- start and stop a play session owned by the current Hermes session;
- display the live game inside the Toqraq pane;
- observe, control, capture, and debug the running game;
- expose the same baseline Agent capabilities without leaking engine setup
  details into ordinary workflows.

Uniform user intent does not require identical engine internals. Each contribution
uses the engine's official project format, distribution mechanism, editor
extension system, runtime API, and debugger where they are the strongest fit.

## Design rules

1. An abstraction marks a real project, distribution, process, bridge, or
   display boundary.
2. Adding an engine changes composition and the new engine package. Existing
   use cases do not gain engine-specific branches.
3. Common contracts describe operations that Hermes and users perform. They do
   not invent a lowest-common-denominator engine object model.
4. Exact engine and bridge identities are resolved before launch and remain
   fixed for the session.
5. Capabilities are discovered from the selected installation and confirmed by
   the live bridge. They are never inferred from a directory name.
6. An engine is presented as supported only after it satisfies the baseline
   contract on a real project and a clean Hermes Desktop installation.
7. Toqraq keeps explicit composition. It does not implement a second plugin
   loader inside the Hermes plugin.

## Project-format recognition and engine contribution

An `EngineProjectFormat` is the smallest engine-specific boundary: one stable
engine ID and one side-effect-free `ProjectProbe`. It may be registered for
perception before any runtime is admitted. A complete engine contribution is a
cohesive bundle that reuses that exact format and adds only ports backed by a
real, admitted engine boundary.

```text
EngineContribution
|-- EngineProjectFormat
|   |-- engine ID
|   `-- ProjectProbe
|-- RuntimeCatalog
|-- RuntimeProvisioner
|-- GameLaunchPlanner
`-- PreviewLocator
```

The composition root registers formats in one immutable
`ProjectFormatCatalog` and complete contributions in one immutable
`EngineCatalog`. Both reject duplicate engine IDs and preserve explicit
composition order. A format entry proves only bounded recognition. An empty
engine catalog is valid when no engine has completed its runtime admission
gates; a recognized project then produces an explicit runtime-unavailable
result and Start returns the matching typed failure. A placeholder
contribution or a complete-looking contribution with zero certified releases
is not an empty catalog substitute. Services depend on the ports below and
never import `engines/godot`, `engines/unity`, `engines/unreal`, or
`engines/cocos`.

### ProjectProbe

`ProjectProbe` reads project-owned metadata and returns a bounded
`ProjectDescription`:

- engine ID and confidence;
- project root and project marker;
- engine version declared by the project, when present;
- display-size hint;
- relevant entry scene, map, or startup configuration;
- diagnostics that block preparation.

Detection is side-effect free. Multiple probes may recognize a directory. An
unambiguous result is selected automatically; otherwise the pane asks the user
to choose. A user selection is stored in Toqraq state, not encoded as a hidden
change to the project.

### RuntimeCatalog

`RuntimeCatalog` returns selectable, exact `RuntimeRelease` records. Version
syntax belongs to the engine provider; core treats it as an opaque validated
identifier.

For one `(engine ID, public version, platform, architecture)` tuple, the
catalog exposes at most one currently selectable certified release. Build and
distribution IDs preserve exact internal identity; they do not create a second
ordinary user choice. Duplicate selectable tuples make catalog composition
fail. Replacing a build in a later plugin release makes the former build
unselectable for new sessions without deleting an installed component that may
still be leased or explicitly removed.

A release records:

- engine ID;
- exact version and build ID;
- distribution ID;
- platform and architecture;
- required components;
- expected bridge identity;
- complete contribution capability set;
- exact native bridge capability subset, which may be empty for a
  handshake-only non-selectable candidate;
- download size and license requirements;
- immutable package manifest reference.

The ordinary UI lists releases that have passed Toqraq's engine contract. It
does not expose repository names, archive patterns, or internal channels.

### RuntimeProvisioner

`RuntimeProvisioner.prepare` accepts the exact `RuntimeRelease` object already
returned by the shared project-runtime selection service and turns it into a
verified `PreparedRuntime`. It does not accept a user choice, query
`RuntimeCatalog`, call `resolve` again, substitute another release, or prove
identity by comparing the input with a newly resolved equivalent object. It
acquires component leases and resolves the engine's named entry points and
bridge identity. Every runtime entry-point binding names its exact opaque
component release ID and that component's certified entry-point name. The
provisioner validates those bindings; it does not search component trees or
choose the first matching filename.

The setup component jobs perform network acquisition, publication, repair, and
removal. `RuntimeProvisioner.prepare` on the Start path only verifies those
already installed exact releases, acquires leases, and resolves bindings. A
missing or invalid component returns readiness failure; Start never turns into
a hidden installation request.

The prepared runtime records its component installations and named entry
points instead of assuming that every engine is one executable. Examples
include `editor`, `player`, `hub`, `compiler`, and `bridge_host`.

### GameLaunchPlanner

`GameLaunchPlanner` receives a resolved project, exact `PreparedRuntime`,
bridge endpoint, explicit base environment, and already encoded one-shot
bootstrap. It returns one immutable `ProcessLaunch` and owns no process or
resource. The platform `ProcessTreeLauncher` executes that exact plan and
transfers its process-tree owner to `PendingStart`.

The planner:

- uses absolute managed paths;
- constructs arguments without a command shell;
- does not consult `PATH` to select an engine;
- adds only engine-native non-secret activation facts to the explicit child
  environment;
- retains the caller-supplied private bootstrap unchanged;
- performs no platform process operation or runtime reselection.

Argument construction remains pure and directly tested inside each engine
package.

### Runtime feature binding

The common controlled bridge, not an engine contribution factory, constructs
the focused observation and control adapters after exact authentication. The
wire methods and Python contracts are shared across engines; engine-native
mapping and typed extension facts stay inside each native bridge. This avoids
one factory per engine that only repeats the same common method table.

The handshake contains:

- engine and engine version;
- bridge implementation and protocol identity;
- Hermes session nonce;
- exactly the native RPC capability IDs implemented by the process;
- engine-native limits required by the client.

An unexpected identity or message shape closes the connection and produces a
typed diagnostic. The client does not guess a protocol from an installation
label. Project inspection, preparation, lifecycle ownership, restart, and
preview placement are contribution capabilities and are never falsely claimed
by a native bridge. A selectable supported release still provides the complete
user baseline; an isolated candidate may authenticate an empty native set so
the handshake itself can be tested before any feature port exists.

### PreviewLocator

`PreviewLocator` identifies the playable surface created by an engine. It does
not position or render that surface. It returns a `PreviewSurface` consumed by
the renderer and platform adapters.

## Exact runtime chain

One application selection service owns project and runtime choice for Setup,
Start, and Hermes tools. It probes the normalized project through the format
catalog, applies an explicit workspace engine choice, and then resolves the
matching admitted contribution. If none exists, it returns the recognized
project with runtime-unavailable state and never consults components. For an
admitted contribution it applies the explicit version choice or exact project
declaration, filters for the host platform and architecture, and returns either
one catalog-owned `RuntimeRelease` or one focused choice result. It never
applies a generic "latest" heuristic.

Setup is a read-only projection of that service. It shows the returned
release's exact component requirements and starts explicit component jobs only
after user consent. Setup does not mint a persisted launch ticket. Start reruns
the same deterministic selection service against the immutable bundled catalog
and workspace choice, then passes its returned release object through the
complete launch path without resolving it again:

```text
ProjectDescription from ProjectFormatCatalog + workspace choice + host identity
  -> matching admitted EngineContribution
  -> project-runtime selection returns one catalog RuntimeRelease
  -> RuntimeProvisioner.prepare(that exact RuntimeRelease)
  -> PreparedRuntime(that release, verified entry points, owned leases)
  -> PendingStart owns prepared runtime and every later launch resource
  -> GameLaunchPlanner.plan(...) returns one exact ProcessLaunch
  -> ProcessTreeLauncher.launch(that exact plan)
  -> registry CAS promotes the live process tree and retained resources
  -> EngineSession settles bridge, feature, and preview readiness independently
```

The workspace choice is an application input containing only user-facing
engine and version policy. `RuntimeIdentity` records the complete certified
build identity inside a `RuntimeRelease`; it is not another user choice.
`RuntimeRelease` is the sole runtime launch credential. `PreparedRuntime` holds
leases for that release's verified components while a pending start or active
session uses it. `EngineSession` exposes the selected engine version and bridge
identity in its public state. Neither the provisioner nor launch planner can
perform an implicit second selection. Start performs no acquisition, download,
repair, or release substitution.

Bridge authentication is not the process commit point. A launched playable
process may remain active while bridge, perception, or control readiness is
failed. Only an authenticated matching bridge can create feature ports.

## Capabilities

Capability IDs are validated strings. Shared capabilities use the `toqraq.`
namespace; engine-only capabilities use the engine namespace. New capability
IDs do not require editing a central enumeration.

The native bridge set is a subset of the complete release set and never
contains host-owned project inspection, runtime preparation, process
lifecycle, restart, or preview placement. Those capabilities remain available
through their owning contribution ports without being claimed in a handshake.

### Supported-engine baseline

An engine must provide these user-visible operations before it appears as
supported:

| Capability | User intent |
| --- | --- |
| `toqraq.project.inspect` | Understand the current engine project |
| `toqraq.runtime.prepare` | Prepare an exact managed engine version |
| `toqraq.play.lifecycle` | Start and stop a Hermes-owned play session |
| `toqraq.play.restart` | Restart through the same exact prepared runtime |
| `toqraq.play.pause` | Pause and resume simulation |
| `toqraq.play.step` | Advance simulation by a bounded number of frames |
| `toqraq.preview.display` | Show the playable surface in the Hermes pane |
| `toqraq.observe.frame` | Capture the current rendered frame |
| `toqraq.observe.hierarchy` | Read the live entity hierarchy |
| `toqraq.observe.properties` | Inspect selected runtime objects |
| `toqraq.observe.diagnostics` | Read structured runtime diagnostics |
| `toqraq.observe.performance` | Read a bounded performance snapshot |
| `toqraq.control.input` | Inject bounded player input |

An engine contribution may expose more capabilities. Services check capabilities at the
operation boundary and return a typed error when a requested operation is not
present.

### Common observations

The common hierarchy is deliberately small:

- opaque runtime object reference;
- display name;
- engine-native type;
- parent ID;
- bounded component or property summaries;
- optional engine-native facts under a namespaced field.

Godot nodes, Unity GameObjects, Unreal Actors, and Cocos nodes retain their
native type names. Core does not translate them into a fictional universal
component system.

## Preview surfaces

An engine contribution owns only its `PreviewLocator`: it identifies the
playable surface and reports the authoritative viewport size. It does not own
pane layout, geometry, platform attachment, Web authorization, or renderer
state. The implemented native path and the separate Web admission gate are
defined once in [preview.md](preview.md).

## Process ownership

The start use case creates a session-scoped `PendingStart` before its first
fallible resource acquisition. That owner successively receives the prepared
runtime, bridge listener and credential, launched process tree, bounded output
collectors, attachment tasks, and preview discovery. A live process tree and a
compare-and-swap against the exact expected session-registry owner promote it
to `EngineSession`; bridge authentication and feature readiness settle after
that process commit.

Failure or cancellation retains every acquired resource in `PendingStart`
until the same idempotent cleanup operation succeeds. Stack unwinding and a
module-global task set are never the final owner. Cleanup releases dependents
before their prerequisites and keeps failed ownership retryable.

An active play session owns a process tree rather than one PID. The process
port exposes:

- the stable root process identity;
- bounded stdout and stderr tails;
- bounded complete-tree exit observation;
- idempotent bounded close, whose platform implementation owns graceful then
  forced termination.

Child membership is not a common observation surface. The Windows adapter
uses Job membership internally to prove atomic ownership, authorize graceful
window closure, and terminate all descendants.

On supported Windows hosts, a helper and Job Objects establish process-lifetime
and session ownership before the game can execute. Only explicit standard
handles and the bounded one-shot standard-input bootstrap reach the child; the
adapter neither inherits the parent environment nor exposes the credential in
arguments. Failed native acquisition or rollback stays owned and blocks a new
launch until cleanup succeeds.

Shutdown first attempts bounded graceful window closure after rechecking exact
Job membership, then terminates the complete job and waits for exit. Host exit
retains kill-on-close as the crash guarantee. Exact handle, helper, pipe,
environment, Job, and fault-injection requirements belong to
[security.md](security.md) and [testing.md](testing.md), not engine semantics.

This model supports engines that spawn an editor, game player, shader worker,
or bridge host. Preview discovery may select a child process window without
transferring lifecycle ownership.

Natural exit, explicit stop, session replacement, Hermes session finalization,
and plugin shutdown use the same cleanup operation. Plugin shutdown first
rejects new starts, then cancels pending starts, and finally drains pending and
active owners with bounded waits. A cleanup failure remains observable and
owned for retry; a registry entry is not discarded merely because one native
release operation failed.

## Engine-native bridges

Complete observation and control require an engine-native bridge. The table
records the intended technical form if the engine passes its independent
authorization and support gates; it is not a support matrix:

| Engine | Runtime source | Bridge form | Preview |
| --- | --- | --- | --- |
| Godot | Toqraq instrumented upstream build | custom engine module | native window |
| Unity | official Unity distribution | UPM editor/runtime package | standalone native window |
| Unreal | official binary or authorized source build | Unreal plugin | standalone native window |
| Cocos | official Creator distribution | editor extension | web or native preview |

Only Godot currently has an unobstructed implementation path. Unity is blocked
by current agentic-access and integration authorization requirements; Unreal
and Cocos remain gated by installation, extension, and distribution evidence.
The dated facts and unblock conditions are in
[engine-support.md](engine-support.md).

Project bridge changes, when required by an engine, are explicit and
reviewable workspace changes. The engine adapter describes the required
change; Hermes applies it through its normal file-editing boundary. The
adapter does not silently rewrite user source files during launch.

## Godot instrumented runtime

Toqraq does not maintain a long-lived Godot source branch. The engine build
pipeline:

1. checks out an exact upstream Godot tag and commit;
2. supplies `engine/godot/modules/toqraq` through Godot's official
   `custom_modules` SCons option;
3. builds the editor runtime without modifying upstream source files;
4. runs the bridge handshake and real-project contract suite;
5. publishes the runtime archive, digest, notices, and build provenance, then
   adds its certified record to the same plugin release that passed the suite.

The module contains only facilities that must run inside the engine. It uses
Godot's native APIs internally and exposes only the common Toqraq bridge. The
module begins with a handshake and adds deterministic control or observation
that an external process cannot provide.

An upstream change that breaks the custom module fails the build. The engine
version is not added to the selectable catalog until the module compiles and
the complete contract suite passes. No upstream file patch or merge branch is
required. The executable workflow and evidence boundary are in
[godot-candidate-build.md](godot-candidate-build.md).

The repository records an earlier local Windows 4.7.1 observation of 27
focused native cases with 197 assertions and a production
listener/feature-adapter exercise across all eight native capabilities. It
remains outside production composition until an exact published component and
the clean-store, standard-install, and interactive Desktop gates pass.

## Vendor installation realities

Godot can be acquired without an account and can complete preparation from the
Toqraq pane.

Vendor-managed engines may require authentication, license acceptance, a
written integration authorization, or an official interactive installer. A
login flow is not evidence that agentic integration or bridge redistribution
is permitted.

Toqraq never accepts license terms on the user's behalf and never retrieves a
vendor package from an unofficial mirror. The pane keeps the workflow inside
Hermes by showing the required action, launching the official authorization
surface, observing completion, and resuming the same installation task.

Large engines are installed on demand. They are not bundled with the Hermes
plugin repository.

## Adding an engine

An engine contribution is complete when it provides:

1. one engine package with the contribution ports it actually needs;
2. project detection fixtures;
3. exact release catalog and managed installation tests;
4. pure launch argument tests;
5. bridge handshake and message-contract tests;
6. PreviewSurface integration;
7. the supported-engine baseline on a real fixture project;
8. first-run Hermes Desktop verification from an empty component store;
9. English and Simplified Chinese user-facing messages;
10. engine-specific setup, license, and troubleshooting documentation.

Composition adds the contribution in one place. Existing services, tools, API
routes, and renderer controls remain unchanged.

## Non-goals

- Reimplementing an engine editor in Hermes.
- Hiding a missing capability behind an approximate operation.
- Using arbitrary shell commands as an engine adapter.
- Selecting or launching a user-installed engine.
- Installing or modifying a global engine, `PATH`, file association, or system
  default.
- Placing vendor credentials or license material in project files.

## Official extension and installation references

- [Godot custom C++ modules](https://docs.godotengine.org/en/stable/contributing/development/core_and_modules/custom_modules_in_cpp.html)
- [Unity custom packages](https://docs.unity3d.com/Manual/CustomPackages.html)
  and [Unity installation](https://docs.unity3d.com/6000.1/Documentation/Manual/GettingStartedInstallingUnity.html)
- [Unreal Engine plugins](https://dev.epicgames.com/documentation/unreal-engine/plugins-in-unreal-engine)
  and [Unreal Engine installation](https://dev.epicgames.com/documentation/unreal-engine/install-unreal-engine)
- [Cocos Creator editor extensions](https://docs.cocos.com/creator/3.8/manual/en/editor/extension/readme.html)
