# Implementation Status and Release Gates

This document records what the repository currently provides and what must be
proved before a user-facing claim changes.

The product boundary is [product.md](product.md), structural ownership is
[architecture.md](architecture.md), and evidence requirements are
[testing.md](testing.md).

## Current production composition

The standard plugin currently composes:

- one manifest-v2 package root with Python, API-only Dashboard, generated
  Desktop ESM, translations, and bundled skills;
- one process-local container shared by HTTP, sockets, tools, hooks, and the
  async disposer;
- strict Pydantic contracts and generated OpenAPI/Desktop declarations and runtime rules;
- seventeen Hermes tools and four explicitly registered namespaced skills;
- async `on_session_finalize`, synchronous bounded live/workspace
  `pre_llm_call`, and one async plugin-instance disposer; awaiting the async
  callbacks is a required host behavior rather than something plugin code can
  enforce;
- an immutable `ProjectFormatCatalog` containing standard Godot 4 recognition;
- an immutable `EngineCatalog(())` with no production engine contribution;
- an empty in-memory `CertifiedComponentCatalog(())` with no runtime record loader;
- exact component-store, job, verification, lease, and removal machinery;
- shared project/runtime selection, pending-start, session registry,
  operation gate, event stream, and cleanup owners;
- one task-keyed recognized-workspace context owner with stale-update
  suppression, driven by plugin-lifetime Desktop state rather than pane mount,
  with finalization/disposal invalidation;
- one plugin-lifetime Desktop session synchronizer projecting host readiness,
  the selected REST snapshot, and session events into a single store shared by
  pane, status, and palette contributions;
- a Bridge connection factory and focused runtime feature adapters; listener
  and credential acquisition occur only after a ready runtime selection and
  are unreachable while the production engine catalog is empty;
- Windows process-tree and native-display implementations.

Production registers only `GODOT_PROJECT_FORMAT`. The Godot runtime catalog,
provisioner, launch planner, preview locator, and native custom-module source
are candidate code and are not instantiated by the production composition root.

An empty engine catalog is a valid loadable state. `POST /setup` recognizes a
standard Godot project through the independent format catalog and returns
`runtime_unavailable`; an unrecognized project reports the exact format probes.
Start returns the stable unavailable failure. The Desktop must render those
facts; it must not invent a runtime, component, or install action.

The repository Desktop typing gate is closed. Every handwritten renderer
production and test file is strict `.ts`; the generated declaration is checked
in the same Program. The paired Hermes compiler checks the whole graph with the
required strict and unused-symbol rules and rejects explicit `any`. Renderer
tests compile with the existing esbuild dependency into one invocation-owned
temporary directory before Node runs them, and cleanup also covers build or
test failure. This evidence does not replace the clean published-host gate.

## Evidence already obtained

### Standard package boundary

The repository root has the required one-package shape. Across three observed
executions against a temporary committed local Git source and the locally
modified paired Hermes worktree, one completed isolated-profile install,
enable, Python registration, API-only Dashboard mount, Desktop source
discovery, disable, re-enable, update, removal, and post-removal absence.

Two independent executions exposed a host transaction stability gate. One
passed through update and then failed remove; Hermes restored the installed
package and activation config. The other made the install generation visible
but failed its final journal publication, retaining a recoverable
`state=new_visible` transaction. Later direct operations succeeded.

Each external CLI step runs in a new process. `plugins` is a built-in
management path that skips Toqraq discovery, so neither failure loaded Toqraq
or called its disposer. These results do not implicate session cleanup, and
they do not prove draining an already active instance or Electron companion
teardown.

A controlled Windows no-delete-sharing handle reproduced the host journal
failure as `PermissionError` with `winerror=5` and `errno=13`; the same write
succeeded after handle release. Because the failed host commands retained only
stable error categories and the remove rollback cleaned its journal, the exact
original operating-system call is unavailable. The combined evidence makes a
missing bounded Windows atomic-replace retry the high-confidence host cause.

This proves only the exact local Toqraq snapshot and dirty paired Hermes
worktree. The host behavior is not reproducible from its recorded commit alone
because manifest-v2 companion changes remain uncommitted. A clean published
Hermes build, published `<owner>/<repository>` install, cross-process lifecycle
proof, and interactive Desktop journey remain release gates.

A standard-command install from a committed local package source then loaded
the rebuilt companion after the paired gateway and Desktop restarted. Hermes
created and opened a project backed by `tests/fixtures/godot_project`; Toqraq recognized the Godot
project and reported `runtime_unavailable` from the empty production catalogs.
This closes that current-composition scenario only.

The same run minimized the pane into Hermes' persisted narrow rail. Computer
Use exposed a Restore accessibility node without actionable geometry and did
not establish a working coordinate target; restarting Desktop correctly
retained the minimized layout. The paired host source declares pointer restore
handlers on both the rail and its tab, so this run does not prove a host defect
or an unreachable layout. Pointer, keyboard, accessibility, persistence, and
restart recovery remain an interactive evidence gap.

### Host transaction prerequisite

No release gate can close until the paired Hermes host:

1. retries transient Windows sharing/access failures inside a bounded atomic
   journal and config replacement operation;
2. keeps journal replacement strictly atomic and retains recoverable state
   after the retry budget is exhausted;
3. records safe numeric operating-system diagnostics and the failed
   transaction phase without paths or exception text;
4. passes the complete standard lifecycle repeatedly without a CLI wrapper,
   test, or CI retry converting a failed transaction into a pass;
5. proves that the real loaded Desktop/gateway instance is quiesced before a
   cross-process disable, update, or remove mutation.

The controlled handle regression and the repeated lifecycle job are both
required. A single successful rerun is evidence of intermittence, not closure.

### Shared contracts and ownership

Current tests cover:

- exact catalog selection and the empty-catalog result;
- component identity, download bounds, archive confinement, atomic
  publication, verification, leases, jobs, cancellation, and retry;
- exact `RuntimeRelease` propagation through prepare, launch, and public
  session identity;
- pending-start and active-session ownership across failure, cancellation,
  replacement, natural exit, finalization, and plugin shutdown;
- cross-loop session operation serialization and cleanup retention;
- focused hierarchy, object, diagnostic, metric, frame, simulation, and input
  services with request/result correlation;
- all mounted REST operations and seventeen tools, including one-to-one
  focused-service routing, request/result models, and shared error boundaries;
- native preview attachment, follow, visibility, detach, restoration, and
  stale-owner rejection;
- Bridge handshake, limits, framing, correlation, binary transfer,
  cancellation, invalidation, disconnect, and close.

These are code-boundary results. They do not make an engine selectable.

### Godot 4.7.1 candidate

The repository records an earlier local Windows Godot 4.7.1 editor observation
containing the external Toqraq module. The recorded focused native suite passed
27 cases and 197 assertions. The production Python listener and feature
adapters then completed a process exercise covering:

- intrinsic identity and authenticated bootstrap;
- all eight native capability declarations;
- hierarchy, object, diagnostics, and metrics reads;
- pause, two-frame step, and resume;
- semantic, W3C keyboard, pointer, text, and standard-layout gamepad input;
- 960x540 to 480x270 aspect-preserving PNG capture with length, digest, and
  dimension verification;
- disconnect and owned cleanup.

The exercised executable is a candidate, not an admitted release. There is no
published component URL, package digest, immutable certified release record,
clean-store installation proof, or complete interactive standard-install run.
Production therefore remains empty.

The repository now has a deterministic ZIP packager, an independent strict
candidate verifier, tamper tests, and a manual exact-source workflow. That
workflow packages notices and canonical evidence, then runs the production
Bridge exercise only against the final ZIP's verified extracted executable.
It has not produced a recorded real artifact from this repository revision, so
the earlier executable evidence has not acquired package or tree digests and
does not close any component-admission step.

## Open gate 1: repository contract closure

Before release admission, the current public graph must be internally closed:

1. every mounted REST route and all seventeen tools use the same focused service
   and result contracts;
2. generated OpenAPI, Desktop declarations, structural runtime rules, and
   `desktop/plugin.js` match their sources;
3. Desktop decoders and state consume exact session, readiness, preview,
   component, and event DTOs;
4. every handwritten renderer production and test file is `.ts`, with no
   `.js`, `.tsx`, explicit `any`, `@ts-check`, or JSDoc type scaffolding;
5. one strict Program checks production and tests using all required compiler
   options, and the esbuild test runner owns and removes its temporary output;
6. all source, test, and document files meet the 500-line gate and unused
   imports, options, events, fixtures, and documentation are absent;
7. Ruff, format, strict Mypy, Python tests, renderer tests, generation check,
   strict renderer typecheck, and deterministic build pass together.

No adapter or presenter may conceal a failed item in this gate.

## Open gate 2: certify one Godot component

The exact Godot candidate bytes must acquire a release identity through the
component boundary:

1. build from one exact upstream stable tag and full commit with an untouched
   upstream tree;
2. record module tree, build recipe, toolchain, intrinsic build ID,
   distribution ID, archive digest, content-tree digest, notices, and license;
3. publish the immutable package to its reviewed source;
4. create one exact component release record and one exact Godot
   `RuntimeRelease` mapped to it;
5. install, interrupt, resume, verify, repair, lease, and remove those same
   bytes from an empty component store;
6. pass the complete service and public-presenter conformance suite;
7. pass native preview attach, wide/tall resize, minimize/restore, detach, and
   finalization on an interactive Windows desktop;
8. prove the standard plugin journey in an empty Hermes profile.

Only the bytes that pass all eight steps may be called certified.

## Open gate 3: production Godot admission

After gate 2 closes, composition may register one complete Godot contribution
and its release records. Admission must prove:

- Setup and Start select the same catalog-owned `RuntimeRelease` object;
- Setup exposes only its opaque component release IDs;
- Start performs local verification and lease acquisition only;
- the prepared, launched, bridged, and reported build identities are exact;
- bridge failure leaves an independently visible playable process state;
- every terminal path drains process tree, bridge, preview, tasks, temporary
  resources, and leases;
- a failed cleanup remains owned and blocks unsafe reuse until retry succeeds.

The empty catalog is replaced by this explicit complete registration. A
placeholder contribution, a contribution with no release, or a test fixture
must never enter production composition.

## Open gate 4: complete the Desktop journey

The Desktop release must prove:

- an empty Hermes workspace causes no setup request and presents one focused
  open-project instruction;
- the active Hermes workspace is the sole pre-launch project source, while a
  live session retains its own immutable project root;
- engine-unavailable, project choice, version choice, install, start, running,
  failed, and stopped states from authoritative backend facts;
- setup exposes at most one primary action and runtime controls appear only
  while a game exists;
- component progress, cancellation, retry, removal, and remount recovery;
- session-keyed state with sequence-gap REST reconciliation;
- pane-independent session synchronization with no full-session-list polling;
- centered contain scaling through every pane geometry change;
- stale native effects cannot move, hide, or detach the current owner;
- keyboard-accessible controls, focus release, localized labels, and localized
  recovery actions;
- no raw exception, backend English message, secret, native handle, or
  unbounded log reaches UI state.

The generated Desktop entry remains part of the standard plugin lifecycle;
there is no secondary installation mechanism.

## Open gate 5: workspace context and creative tooling

The four skills and both bounded capsule forms are registered now.
`pre_llm_call` prefers cached `SessionResult` facts for its exact `task_id` and
otherwise uses only the recognized-project summary synchronized by Desktop.
Both forms have a 2,048-character ceiling. Workspace replacement, empty or
unrecognized results, finalization, and disposal invalidate the cached summary;
late probes cannot restore it. The public hook carries no workspace, so the
first turn is best-effort until the plugin-lifetime Desktop observer completes
its initial synchronization. Every skill states that a delegated child has an
independent task ID, receives only bounded evidence for an independent leaf,
and cannot use Toqraq tools to reach its parent's game. The parent retains live
control and final verification. The asset skill names conditional image,
opt-in video, and configured `text_to_speech` tools while distinguishing
spoken voice from music, sound effects, transcription, and artifact storage.
Remaining work is:

- keep detailed reads behind explicit tools;
- add bounded project-inventory reads instead of implying that the current
  setup summary can inspect scenes, assets, dependencies, settings, or inputs;
- add detected engine/version-specific guidance before claiming conditional
  engine skill loading;
- exercise representative `delegate_task` review flows without adding a
  permanent agent system;
- add media inspection and deterministic transforms only through approved
  managed components with provenance and license metadata.

The focused source suite and isolated standard-package lifecycle both verify
these exact installed skill bodies against the paired development host.

Provider credentials and model selection remain in Hermes. Context contains
no tree, logs, media bytes, tokens, or general game-development prompt.

## Additional engines

Unity, Unreal, and Cocos remain absent from production composition. An engine
enters only after its authorization, acquisition, extension, redistribution,
complete baseline, clean-install, and interactive gates in
[engine-support.md](engine-support.md) close.

Adding an admitted engine changes its package and the explicit catalog
registration. It does not change ordinary session services, tools, REST paths,
or the Desktop workflow.

## Deferred publishing

Export, signing, store metadata, release artifacts, and distribution are a
separate future product boundary. No publishing state machine, service, or
dependency belongs in the current perception or development graph.

## Completion record

Each closed gate records:

- exact plugin and upstream commits;
- exact artifact identities and provenance;
- commands and external environments exercised;
- automated counts and interactive scenarios;
- skipped suites and their blockers;
- catalog records admitted by that evidence.

A passing unit suite, a native candidate, or a documentation update alone is
not a support claim. Ordinary Setup is the executable truth: while production
composition is empty, no engine/version is offered.
