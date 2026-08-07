# Plugin Packaging and Component Delivery

This document defines how Toqraq is installed, enabled, updated, and removed
as one standard Hermes Desktop plugin. It also defines how large engines and
tools are acquired after installation without depending on the user's global
environment.

## Delivery outcome

The end-user entry point is one Hermes command:

```text
hermes plugins install <owner>/<repository> --enable
```

That command must install the Python and Desktop surfaces of Toqraq as one
package. Afterward, all required setup occurs in Hermes Desktop. A runtime,
bridge, media tool, or model may be downloaded separately because of size or
vendor terms, but the choice, explanation, progress, and recovery remain in
the Toqraq UI.

No end-user script, manual file copy, second plugin command, external setup
wizard, `PATH` edit, or terminal-only engine configuration is part of the
product flow.

## Current package boundary

The repository root is the plugin package. It contains `plugin.yaml`, the
minimal Python entry, the `toqraq` package, an API-only Dashboard backend, and
the prebuilt Desktop ESM entry. The manifest declares version 2 and points to
`desktop/plugin.js`; no repository-owned workflow copies a second plugin surface.

The Desktop entry is a deterministic generated artifact. `.gitattributes`
fixes that file to LF so a standard Git installation preserves its exact bytes
on Windows and Unix hosts. The isolated lifecycle suite compares the installed
entry byte-for-byte with the repository artifact.

The Dashboard manifest declares `entry: null` and a hidden tab. Its API module
derives imports from the package namespace assigned by Hermes, so the Python
entry and Dashboard routes resolve one process-local service container. The
Windows native adapter uses only the standard library, and plugin loading does
not install into or otherwise mutate the Hermes Python environment.

This repository structure is necessary but not sufficient evidence for the
delivery outcome. Three observed executions of the isolated lifecycle suite
against the locally modified paired Hermes worktree produced mixed results:

- one execution completed install, enable, discovery, disable, re-enable,
  update, remove, and post-removal absence;
- one execution reached remove after every earlier step passed, then the host
  rolled the package and activation config back after its removal transaction
  failed;
- one execution published the installed generation, then failed its final
  journal write and retained a recoverable journal at `state=new_visible`.

Each public CLI step ran in a new process. Hermes treats `plugins` as a built-in
management command, so that path skipped plugin discovery and agent startup.
Neither failed transaction imported Toqraq nor invoked its instance disposer.
The failures therefore exercise host package/config transaction durability,
not Toqraq cleanup.

The failed commands retained only stable transaction errors, and the rolled
back remove cleaned its journal, so the original operating-system call cannot
be recovered exactly. A controlled Windows reproduction held `journal.json`
without delete sharing: the next host journal replacement raised
`PermissionError` with `winerror=5` and `errno=13`, then succeeded immediately
after the handle closed. Subsequent direct operations and one complete suite
execution also succeeded. This is high-confidence evidence of a missing
bounded Windows atomic-replace retry, not proof of which external process held
either original file.

A standard-command install from a committed local package source loaded the
rebuilt Desktop after the paired gateway and Desktop restarted. Hermes created
and opened a project backed by `tests/fixtures/godot_project`; the pane recognized Godot and
reported no certified production runtime. These results prove only that local
pair, not a clean published host, source, active-instance drain, or full
interactive journey. A secondary deployment path is not a substitute.

In the same run, Minimize entered Hermes' persisted narrow rail. Computer Use
reported no actionable geometry for Restore and did not establish a working
coordinate target; Desktop restart retained the minimized state. The paired
host source declares restore handlers on the rail and its tab, so this is an
interactive evidence gap rather than a confirmed host defect.

Upstream `main` was checked on 2026-08-07. Its public
[`PluginManifest`](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/plugins.py)
still has no Desktop companion entry or awaited instance disposer. The open
[manifest contract issue](https://github.com/NousResearch/hermes-agent/issues/64165)
and [lifecycle ownership issue](https://github.com/NousResearch/hermes-agent/issues/64229)
confirm that these host surfaces are not released contracts. The local paired
worktree is therefore test evidence only; it is not an upstream API claim.

## Required Hermes host contract

Toqraq's required manifest-v2 host contract lets a plugin point to a Desktop
entry inside the same installed package:

```yaml
manifest_version: 2
desktop_entry: desktop/plugin.js
```

The host contract provides these semantics:

1. Resolve the entry only inside the installed plugin root.
2. Validate that it is one ESM file accepted by the Desktop plugin loader.
3. Discover the Desktop entry when the package is enabled.
4. Disable both Python and Desktop surfaces through one plugin decision.
5. Update the package and both surfaces as one package operation.
6. Stop loading the entry before package removal.
7. Expose load failures and the required gateway or Desktop reload in Hermes.
8. Honor the active Hermes profile and its resolved `HERMES_HOME`.
9. Load the plugin root as one deterministic Python package namespace and load
   its Dashboard API below that namespace.
10. Treat `entry: null` as an API-only Dashboard and never request a Dashboard
    JavaScript bundle for it.
11. Await an async `on_session_finalize` callback before declaring the Hermes
    session finalized.
12. Let a plugin register one instance-scoped async disposer and await it
    before disable, update, remove, force reload, or host shutdown unregisters
    that instance.
13. If disposal fails, fail the lifecycle transaction and retain the old
    plugin instance, registrations, and resource owners for an explicit retry;
    an update loads no new instance until the old one drains successfully.
14. Treat a pane contribution's placement, dock, and size as initial adoption
    hints only. Re-registering the same stable pane ID preserves the user's
    existing layout instead of moving it again.
15. Persist native pane drag, drop, and resize results and expose the same
    layout editor to plugin panes as to bundled panes.
16. Keep a minimized plugin pane reachable through an unobstructed operable
    Restore target after the persisted layout reloads.
17. Keep package journals and plugin configuration atomic while applying a
    bounded retry for transient Windows sharing and access failures. A journal
    never falls back to an in-place copy, and an exhausted retry leaves the
    transaction recoverable.

The preferred implementation loads `desktop/plugin.js` directly from the
installed package root. It does not make a second unmanaged copy. The contract
is useful to any Hermes plugin with a gateway and Desktop surface; it contains
no Toqraq-specific engine behavior.

Toqraq's Python registration does not copy its own Desktop artifact. Under the
required host contract, package installation must be atomic: Hermes either
accepts the complete manifest-v2 package or rejects it without activating a
partial plugin.

`register(ctx)` binds the exact process-local container to one async disposer.
That operation first invokes `Container.close()`, which rejects new starts and
component jobs, seals every session slot, cancels pending starts, drains pending
and active process trees, and stops component jobs. Only after that barrier
succeeds does the composition root compare-and-clear the same container from
its instance slot. A failed or cancelled barrier retains the sealed instance,
registrations, and resource owners for the same disposer to retry. Re-enable in
the same Python module therefore builds a fresh service graph after successful
disposal, while a stale disposer can never clear a newer instance. Clearing
callbacks or modules before the barrier succeeds is forbidden.

## Standard repository layout

The repository root itself is the installable plugin root:

```text
/
  plugin.yaml
  __init__.py
  toqraq/
  dashboard/
    __init__.py
    manifest.json
    plugin_api.py
  desktop/
    plugin.js
  skills/
    game-development/SKILL.md
    asset-workflow/SKILL.md
    balance/SKILL.md
    playtest-debug/SKILL.md
  docs/
  LICENSE
  THIRD_PARTY_NOTICES.md
```

Python deployment source lives directly in this root layout so the standard
Hermes clone is immediately loadable. Focused Desktop authoring source remains
below `src/renderer/`; its deterministic build writes the committed
`desktop/plugin.js` artifact. Engine module source, tests, and development
configuration may coexist at repository root but are not runtime imports. No
generated file is edited by hand.

The installed base package contains:

- the Python plugin and Desktop backend;
- the prebuilt Desktop ESM entry;
- locale bundles included in the Desktop entry;
- four self-contained, explicitly loadable Hermes skills;
- licenses, notices, and user documentation.

Component catalog metadata enters only with certified releases. Skill
registration does not imply that the separate context-capsule or creative-tool
work is complete.

The package does not contain a full engine merely to make installation appear
self-contained. Large or vendor-controlled payloads are managed components.

## Base dependency policy

The base plugin must load in the Hermes-owned Python runtime immediately after
standard installation. Its direct dependencies are limited to the Python
standard library and APIs already guaranteed by Hermes. A small pure-Python
module may be bundled under the Toqraq package when its license permits and
the repository records why it is needed.

Native integration that would otherwise require mutation of the Hermes
environment uses one of these forms:

- standard-library operating-system bindings, such as focused `ctypes`
  adapters for Win32;
- a digest-pinned, versioned helper delivered as a managed component;
- an engine-owned executable reached through an adapter.

The native adapter follows this policy today. It prevents one plugin from
changing the dependency graph of the Hermes Agent process.

The Desktop entry is prebuilt. Its permitted runtime imports remain exactly
the public Hermes Desktop imports: `@hermes/plugin-sdk`, `react`,
`react/jsx-runtime`, and `react/jsx-dev-runtime`. Engine clients, schemas,
translations, and UI modules are bundled into that one ESM artifact by the
repository build.

## Managed component model

Managed components live below:

```text
$HERMES_HOME/toqraq/
  components/<identity-key>/
  downloads/
  staging/
  locks/
  logs/
```

Executable and immutable content is shared by exact identity. Session
processes and temporary files are not stored here. Workspace preferences refer
to component identities; they never rely on an executable found incidentally
on `PATH`.

Each catalog entry contains only fields needed to acquire and run an exact
component:

| Field | Meaning |
| --- | --- |
| `id` and `kind` | Stable component identity and engine, bridge, tool, or model role |
| `version` | Exact upstream or Toqraq component version |
| `platform` and `architecture` | Supported target |
| `source` | Official or project-controlled download location |
| `size` and `sha256` | User-visible size and verified payload identity |
| `license` | License identifier and notice or acceptance location |
| `entrypoints` | Validated executable paths inside the component |
| `protocol` | Exact bridge protocol identity when applicable |
| `capabilities` | Complete contribution features the component enables |
| `bridge.capabilities` | Exact native RPC features compiled into its bridge |

Catalog parsing, selection, archive policy, path confinement, digest
verification, and entrypoint validation are pure tested operations. The
catalog does not encode UI prose; UI receives codes and structured metadata.

### Provisioning transaction

A component installation follows one recoverable sequence:

```text
resolve exact catalog entry
  -> show source, terms, and size
  -> confirm sufficient storage
  -> resume into the identity-scoped download path
  -> verify size and digest
  -> extract with confined archive paths
  -> validate declared entrypoints and protocol
  -> atomically publish the exact component directory
  -> record structured readiness
```

Concurrent requests in one process share one installation task. Processes
coordinate through an identity-scoped lock before modifying download, staging,
or publication paths. Cancellation retains only a bounded, non-executable
package prefix; the next attempt re-hashes that prefix before an exact range
request. Unique extracted staging content is removed on cancellation or
failure. A verified published component is never modified in place. Failure
leaves a typed reason and a retry action rather than a partially ready
directory.

The Desktop UI receives progress events and reconciles through REST. Engine
start depends on a ready component identity; it never performs an undisclosed
download while the pane merely says "starting."

## Engine acquisition

The adapter contract presents the same project intentions for every engine,
but acquisition obeys each vendor's distribution and licensing rules.

### Godot

Toqraq can distribute an exact managed Godot build that contains the Toqraq
debug module. The build records its upstream tag, Toqraq module revision,
platform, architecture, protocol identity, licenses, and digest. The user's
installed Godot is neither required nor modified.

Toqraq does not keep edited upstream Godot files. CI checks out an exact
upstream tag and supplies `engine/godot/modules/toqraq` through Godot's custom
module boundary. Generated engine artifacts do not enter the source patch.
Following a new upstream tag changes the build input; any required Toqraq
change remains confined to the module and build metadata. The module protocol
and fixture suite pass before a catalog entry is published.

### Vendor-gated engines

Some engine versions cannot be redistributed as a Toqraq archive or may
require a vendor account, license acceptance, written integration approval, or
official manager. A contribution is not implemented or registered until the
current gates in [engine-support.md](engine-support.md) are closed. An admitted
adapter declares its acquisition strategy instead of embedding vendor details
in common services.

The Toqraq surface shows the official source and required action, launches an
allowed vendor flow from Hermes into a Toqraq-managed destination, detects the
exact resulting installation, validates it, and records the workspace choice.
If silent installation is permitted, it still uses the same visible component
transaction. If user authentication or license acceptance is required, Toqraq
pauses with one clear action and resumes in Hermes after validation. Existing
system engine installations are ignored.

## Media and transformation components

Hermes owns credentials and model selection for media tools exposed to the
active task. Image generation and analysis use their host toolsets;
`video_generate` and `video_analyze` additionally require their opt-in toolsets
and runtime prerequisites. Conditional `text_to_speech` uses the user's Hermes
TTS provider and voice for spoken dialogue or narration. Toqraq does not
package duplicate provider clients merely to show them in its settings, and it
assumes no music or sound-effect generator, agent-callable transcription, or
generic artifact-store surface.

Deterministic local operations may require components such as an image codec,
audio processor, video processor, or metadata inspector. They use the same
catalog and provisioning transaction as engines. Toqraq selects the smallest
tool that satisfies an operation and exposes its source, license, size, and
readiness. A large optional model is downloaded only when the user invokes a
feature that needs it and approves the component.

## Install, enable, update, and removal

Once the required host contract is released, package lifecycle is:

### Install and enable

1. Hermes acquires the release root and validates `plugin.yaml`.
2. Hermes registers the Python plugin and declared Desktop entry as one
   package.
3. Hermes enables the package and reports the required gateway/Desktop reload.
4. The Desktop entry connects to the mounted plugin backend.
5. Toqraq probes the active workspace and offers required components.

No engine download is required merely to load the Toqraq pane or explain an
unsupported project.

### Update

Hermes updates the base package as one unit. Certified component release
records are tied to that package release, and a component is selected by exact
identity. A running session keeps its resolved executable for its lifetime; a
new start resolves from the active bundled records. The UI explains when a
package or component update requires an engine restart.

### Disable

Disabling Toqraq stops new API and Desktop activity and finalizes every
Toqraq-owned live session resource before unloading the surfaces. If cleanup
fails, disable reports failure and retains the loaded instance so cleanup can
be retried. Managed components remain inert on disk and are visible for later
removal.

### Remove

Removal first drains owned processes through the same disposer, then unloads
the Desktop entry and Python plugin and removes the installed package root. A
failed drain leaves the package loaded and installed. Hermes then offers a
separate, explicit choice to remove Toqraq-managed component storage. User
projects are never deleted or rewritten by uninstall logic.

A standalone management process with no loaded instance cannot perform that
drain by importing a fresh plugin. The released host must quiesce the actual
Desktop or gateway owner before mutation; the current built-in CLI exercise
proves only its process-local package transaction.

## Build and release pipeline

The release pipeline performs these stages:

1. lint, format, type-check, unit-test, renderer-test, and integration-test;
2. generate shared API clients and schemas from one source contract;
3. bundle the renderer into `desktop/plugin.js`;
4. copy the repository to a clean staging directory exactly as the standard
   Hermes package manager will acquire it;
5. validate root manifest paths, ESM imports, licenses, file size limits, and
   the skills or catalogs owned by the current implementation phase;
6. install the staged root into a clean temporary Hermes profile;
7. run Desktop/backend discovery and lifecycle smoke tests;
8. publish immutable release metadata and component catalogs;
9. build and publish engine or tool components in their own
   provenance-producing jobs.

Engine artifacts are not rebuilt merely because documentation or renderer
code changed. A component job is selected by its source, toolchain, platform,
architecture, and exact version inputs.

## Verification matrix

A release is not complete until automated or documented interactive checks
cover:

- a clean Hermes Desktop profile with no engine on `PATH`;
- the single standard installation command;
- Python backend and Desktop entry discovery under one plugin identity;
- enable, disable, rescan, update, and removal behavior;
- bounded Windows journal/config replacement under a controlled no-delete
  sharing handle, with persistent failure retaining recovery state;
- repeated complete lifecycle executions with no command or test-harness
  retry hiding a failed transaction;
- missing backend and required-reload recovery;
- component download progress, cancellation, retry, digest failure, and
  insufficient storage;
- archive path rejection and executable validation;
- concurrent requests for the same component;
- exact engine/version selection for every published adapter fixture;
- an official vendor flow that requires user action;
- session finalization during download, launch, and live preview;
- a non-English Hermes locale and keyboard-only setup journey;
- host-owned minimize and restore through pointer, keyboard, and accessibility after layout reload;
- removal that leaves every user project untouched.

## Current implementation delta

| Area | Current state | Open release gate |
| --- | --- | --- |
| Standard lifecycle | one complete paired-host execution passed; two independent executions hit transient host transactions, at remove rollback and final install journal publication; that isolated CLI suite does not execute the companion in Electron, while a separate standard-command local run loaded it | add bounded atomic-replace retry to the host, prove stable repeated execution without test-level retries, then repeat with a clean published Hermes build, published plugin repository, and interactive Desktop |
| Active-instance drain | same-process host tests cover composed disposal and failure retention; the external CLI exercise starts a new process per operation | define and prove cross-process owner handoff plus Desktop quiesce acknowledgement before mutation |
| Package ownership | Python, API-only Dashboard, and ESM entry share one manifest-v2 root | prove clean host reload, failure retention, and renderer/backend generation ordering |
| Pane recovery | a standard-command paired-host run minimized the pane; Computer Use could not establish an actionable Restore target, while source declares rail and tab restore handlers | independently complete pointer, keyboard, accessibility, persistence, and restart checks |
| Python dependencies | native display uses standard-library `ctypes`; Bridge uses Hermes's exact `websockets` pin | preserve the no-runtime-install boundary |
| Components | exact transaction, jobs, inventory, leases, repair, and removal exist; certified catalog is empty | admit one published digest-pinned release after complete conformance |
| Start | selection performs no download and production catalog is empty | prove explicit setup and local-only Start with the admitted release |
| Godot | real 4.7.1 candidate native and host-adapter exercise passes | clean-store, standard-install, and interactive component admission |
| Other engines | no production contribution exists | close each vendor and complete-baseline gate independently |
| Context and skills | four skills and bounded live/recognized-workspace capsules are registered | prove representative standard-install model flows |
| Media tools | no creative transform component is admitted | choose and certify focused tools before exposing operations |
