# Security

This document defines Toqraq's security boundaries for a Hermes Desktop plugin
that acquires game engines, launches untrusted projects, loads media, and gives
an Agent runtime observation and control.

## Security objectives

Toqraq must:

- preserve Hermes session ownership of every live game and bridge;
- keep managed components separate from user and global engine installations;
- authenticate local bridge and preview connections;
- verify every acquired executable before use;
- bound untrusted network, archive, protocol, image, audio, video, and engine
  data before allocation;
- make project mutations explicit and reviewable;
- avoid general command execution through tools or network APIs;
- keep credentials, authorization material, and private project content out of
  logs and model context unless the user requests them.

Security invariants are code-owned policy. A normal settings change cannot
disable path confinement, component digest checks, platform signature checks,
loopback binding, protocol limits, or session ownership.

## Trust boundaries

| Boundary | Treat as untrusted |
| --- | --- |
| Hermes tool and REST input | paths, identifiers, dimensions, filters, input events |
| Bundled release records and network | metadata, redirects, sizes, archives, installers |
| User project | scripts, scenes, plugins, imported assets, engine configuration |
| Engine process | Bridge messages, file paths, logs, screenshots, object graphs |
| Media input | codecs, dimensions, duration, metadata, embedded attachments |
| Native desktop | window handles, process IDs, ownership, coordinates |
| Web preview | URL, navigation, messages, storage, downloaded content |
| LLM and delegated Agent | tool parameters, inferred paths, requested mutations |

Hermes itself supplies the authenticated plugin host, current session ID,
workspace, secret facilities, and user interaction surface. Toqraq validates
the values it receives rather than assuming that an Agent generated them
correctly.

## Session ownership

One play session is owned by exactly one live Hermes session ID. Each run also
has an internal monotonic revision used only for compare-and-swap and stale
callback rejection. Public tools target the caller and accept neither another
Hermes session nor a run revision as a selector.

Every bridge, preview surface, background task, process tree, native
attachment, and temporary capture belongs to the same session. Finalizing the
Hermes session:

1. rejects new session-owned work;
2. cancels pending bridge and preview operations;
3. terminates the owned process tree;
4. closes network listeners;
5. restores native windows;
6. removes session temporary files.

Cleanup is idempotent. Failed cleanup remains recorded and retryable; ownership
is not discarded while a process or native resource may still exist. Under
Toqraq's required manifest-v2 host contract, Hermes must await session
finalization and the plugin instance disposer before unloading, and a failed
disposer must retain the old instance and owners for retry. Current host
evidence is limited to the locally modified paired worktree.

## Component supply chain

The component policy is defined in
[component-management.md](component-management.md). Security requirements are:

1. the standard plugin package contains strict release records identifying an
   exact publisher, build, platform, architecture, URL, and SHA-256 digest;
2. a standard plugin update is the only operation that adds a selectable
   release record;
3. the runtime manager validates the bundled record before trusting package
   metadata;
4. the package digest is verified before extraction or execution;
5. redirects are accepted only when the final origin is allowed by the
   certified release record;
6. installation publishes atomically from a confined staging directory;
7. installed entry points are resolved from a complete component manifest;
8. a runtime session records the exact component and bridge identities it
   launched.

A checksum retrieved from the same unverified package location is not a
publisher identity. Toqraq release builds put the archive digest in the plugin
release record and publish the upstream engine commit, Toqraq module commit,
toolchain description, and externally verifiable CI provenance alongside the
component. Runtime support never expands from release-site metadata alone.
Repository workflows pin third-party actions by full commit. The Godot
candidate job has read-only permissions, accepts an exact tag and commit, and
installs hash-pinned build and post-link verification wheels, and cannot
publish; conformance admission and component publication are separate gates.

Official vendor installers are downloaded only through the vendor's declared
distribution mechanism. Their adapter validates Authenticode or the vendor's
platform signature when one is available and verifies the resulting install
receipt and entry points.

## Catalog and download security

Network clients use HTTPS and explicit host policy. They:

- reject credentials embedded in URLs;
- validate URL scheme, requested host, redirect chain, and final host;
- apply connection, read, response-size, and idle-progress limits;
- stream large responses to a managed temporary file;
- validate declared content length without trusting it as the only limit;
- avoid sending Hermes or vendor secrets to another origin;
- retain only digest-verified package downloads.

Retry does not relax verification. A continued partial download is hashed from
the beginning before it enters staging.

Bundled release-record parsers reject duplicate identities, unknown fields,
unsafe version identifiers, malformed digests, and ambiguous platform or
architecture records. Vendor adapters that must resolve an exact official
installer validate their bounded response independently.

## Archive and file security

Archive extraction occurs below a unique staging root. The extractor rejects:

- absolute and parent-relative paths;
- symlinks, junctions, hard links, devices, and special files;
- drive-qualified and alternate-data-stream paths;
- Win32 reserved or normalization-ambiguous names;
- duplicate and case-colliding paths;
- excessive entry count, entry size, expanded size, and path depth;
- a member that produces more or fewer bytes than declared.

File validation uses resolved paths and verifies that every result stays below
the intended root. Security decisions never rely on string prefix comparison,
unexpanded environment variables, globs, or a current working directory.

Temporary files use private, unpredictable directories. A component manifest
is written only after every required entry point and identity check succeeds.

## Process security

Engine and media processes start with an argument vector and absolute
executable path. Toqraq never concatenates Agent input into a shell command.

The launcher:

- selects only a verified managed entry point;
- sets the working directory explicitly;
- requires a caller-constructed immutable environment and never starts from
  the Hermes process environment;
- passes only reviewed non-secret values needed by that exact engine build;
- accepts at most 4 KiB of representation-redacted one-shot bootstrap bytes;
- captures bounded stdout and stderr and exposes only an explicit 16,384-character
  latest-tail projection outside the process owner;
- applies startup and shutdown deadlines;
- owns the process tree and terminates descendants on cleanup;
- does not elevate privileges;
- does not disable operating-system code-signing or security prompts.

On Windows 10 and Windows Server 2016 or later, every playable process enters a
session kill-on-close Job Object atomically in `CreateProcessW`. A dedicated
process-local helper is the declared parent and already belongs to a separate
process-lifetime kill-on-close job. The main Hermes process never makes one of
its handles inheritable. It duplicates only the launch's reviewed handles into
the helper, restricts inheritance with `HANDLE_LIST`, and closes those remote
leases before launch commits. Failure is terminal; launch does not fall back
to suspended assignment or ownership of one PID. A vendor authorization or
installer that cannot join the job is a separate installation task with
explicit state, never the active game process.

Launching a user project executes that project's code with the user's desktop
permissions. The pane states this fact before first launch. Toqraq is not a
sandbox for game code. In particular, model/provider keys, Hermes auth values,
plugin credentials, and unrelated user environment values are absent from the
child even when they exist in the parent process.

An unexpected helper exit cannot silently downgrade ownership. New launch is
rejected while existing child leases remain, and the existing lifetime and
session jobs stay owned until verified cleanup succeeds. Hermes host exit
relies on tested kill-on-close Job Object semantics, not a best-effort PID
callback. A host configuration that prevents the guarantee is reported as
unsupported.

## Bridge security

Engine bridges bind only to loopback or an operating-system local IPC
primitive. Each bridge listener:

- belongs to one Hermes session and internal run revision;
- uses an unpredictable session nonce;
- accepts the expected number of clients;
- requires an exact engine, bridge, and protocol handshake;
- rejects undecodable and wrong-credential candidates without consuming the
  launch owner, so an unrelated local process cannot deny bridge readiness;
- treats any identity or capability mismatch after constant-time credential
  proof as terminal for that launch and settles its readiness immediately;
- bounds frame length and pending request count before decoding;
- applies request deadlines and backpressure;
- closes all pending operations when the bridge disconnects.

The single-use credential is part of the launch's bounded bootstrap bytes. On
Windows the launcher writes the complete value to a non-inheritable anonymous
pipe before child creation and closes its writer. It duplicates only the read
end into the helper and supplies that remote lease as child standard input;
the main process closes its local read end before user code executes. An
unrelated concurrent child of Hermes cannot inherit or read the channel. The
value is not placed in a URL, command line, environment, project file, Desktop
storage, event, log, error, artifact, or model context. The complete wire
contract is [bridge.md](bridge.md).

Terminal authentication failures retain only bounded public-safe wire facts.
They never retain, log, serialize, or expose the supplied credential or either
side of an identity comparison. Cancelling a readiness waiter does not cancel
the listener-owned publication; a later observation receives the same result.

Runtime messages are parsed into typed engine-boundary models before services
consume them. Unknown or malformed messages cannot trigger an arbitrary method
call, script evaluation, property write, or filesystem read.

## Agent control boundary

Agent tools expose bounded game-development operations. They do not expose:

- arbitrary shell execution;
- arbitrary engine console execution;
- arbitrary GDScript, C#, C++, or JavaScript evaluation;
- arbitrary runtime object method calls;
- unrestricted property mutation;
- unrestricted filesystem paths;
- arbitrary outbound URLs.

Input injection validates event type, coordinates, key and button ranges,
batch size, duration, and session capability. A future deterministic-scenario
feature must additionally bound step count, frame count, wall duration, and
capture size before admission.

Hermes remains the source-editing boundary. When an engine needs a project
bridge package, Toqraq returns a precise, reviewable change plan. Hermes applies
the files through its normal workspace tools. Launch does not silently add or
modify source files.

## Project and path policy

The ordinary Desktop flow uses the normalized active Hermes workspace and
stores no user-selected project path. Explicit Hermes tool or HTTP requests may provide
`project_dir`; services normalize and validate that request-scoped root before
use. Engine adapters validate their project marker before downloading an
engine.

Read operations:

- reject paths outside the selected project unless the operation explicitly
  targets the managed component store;
- do not follow project symlinks into sensitive locations by default;
- bound file count and bytes read;
- treat engine-returned paths as untrusted;
- restrict temporary screenshot and trace paths to the owning process's known
  temporary root and expected filename form.

Toqraq mutable state, downloads, staging, locks, logs, and components stay
below `$HERMES_HOME/toqraq`. Certified release records stay read-only in the
installed plugin package. User project source and managed runtime files never
share a writable root.

Windows child processes receive only a validated `SYSTEMROOT` and an `APPDATA`
directory below that managed root; they do not inherit `PATH` or parent settings.

## Native preview security

The engine-owned game-window discovery selects only visible, non-empty
top-level windows for the exact game-process PID. Before every display
operation, the Windows adapter rechecks that the child and selected host
handles are live; coordinates and dimensions are bounded physical-pixel
values.

Host lookup receives the renderer's pane screen point and the session's game
root PID. It enumerates visible top-level windows in Z-order, excludes windows
owned by that game PID and transparent or non-activating overlays, then selects
the first remaining window whose screen rectangle contains the point. The
current `NativeDisplay` contract carries no Hermes host process identity,
window identity, or application attestation. It therefore does not prove that
the selected host belongs to Hermes Desktop.

Before attachment, the adapter records style, owner, region, rectangle, and
visibility. Detach restores that exact state. One attachment ID owns each pane
mount so a stale renderer effect cannot move or hide the current preview.

Native calls run outside the event-loop thread and convert platform failures to
typed errors without exposing raw handles to the Agent.

## Future web-preview admission

A `WebSurface` is a core value only; no engine contribution or renderer surface
currently implements web preview. Before admission, a web renderer must use a
loopback URL with a per-session credential and:

- permits only the declared loopback origin;
- blocks top-level navigation and new windows by default;
- denies filesystem, clipboard, camera, microphone, and notification access
  unless a game capability explicitly requires and the user grants it;
- isolates cookies and storage by Hermes session;
- validates `postMessage` origin and message schema;
- removes the surface and storage when the session ends.

An admitted web preview must not call Hermes plugin APIs directly. Interaction
must cross a session-authenticated, schema-validated bridge.

## Future media-processing admission

No media inspector or transformer is currently composed. Before admission,
images, audio, video, fonts, models, and archives must be treated as untrusted;
inspectors must read metadata under byte, dimension, duration, frame-count, and
decode-time limits before full decoding.

An admitted media transform must use one managed, verified tool with:

- an argument vector, not a shell string;
- an explicit input and unique output path;
- protocol and network input disabled unless the operation requires it;
- CPU, memory, output-size, and wall-time limits where the platform supports
  them;
- bounded diagnostic output;
- no in-place mutation of the source asset.

Any selected managed image processor must use a repository-owned restrictive
policy and bounded resources rather than inheriting user configuration. If
ImageMagick passes dependency admission, that policy must disable network
access and unneeded delegates or coders and bound disk, memory, map, threads,
time, width, height, and area.

The LLM may eventually choose crop coordinates or time ranges, but admitted
deterministic code must validate those values, perform the transform, and
inspect generated output again before it becomes a project asset.

## Secrets and vendor authorization

API keys, provider credentials, signing material, and vendor tokens use Hermes
secret facilities or the vendor's own credential store. They are not stored in:

- `plugin.yaml`;
- project files;
- Toqraq component manifests;
- Desktop local storage;
- tool results;
- screenshots or traces.

Logs redact known secret fields, URL query credentials, authorization headers,
and environment values. A future diagnostics bundle must list only the
presence of approved settings, never their values.

Toqraq never accepts a vendor license or account agreement on behalf of the
user. Authorization handoff is an explicit `awaiting_user` installation phase.

## API and Desktop boundary

Dashboard routes are mounted by Hermes below the Toqraq plugin API prefix.
Routes validate:

- Hermes session identity and ownership;
- project and component identifiers;
- request-body size and exact schema;
- native rectangles and attachment IDs;
- WebSocket origin and session binding.

Events are advisory. After reconnect, the Desktop reads authoritative session
and task state. Error payloads contain stable codes, safe localization
parameters, and bounded details; Python tracebacks and host
paths are not returned in ordinary UI responses.

The Desktop bundle imports only the Hermes SDK, React, and React JSX runtime.
It does not load remote scripts or execute project-provided JavaScript in the
Hermes plugin context.

## Logging and diagnostics

Structured logs contain correlation fields needed to trace work:

- Hermes session ID;
- operation or installation task ID;
- engine and exact version;
- process ID when safe;
- phase and typed error code.

Logs do not contain bridge nonces, secrets, full model prompts, media contents,
or arbitrary project file contents. Current startup and process output is a
bounded session-owned tail. Any future persisted engine trace or vendor log
must use an explicit bounded diagnostics artifact with its own lifetime owner.

User-facing errors are internationalized. Security decisions use stable error
codes, not localized string matching.

## Security verification

Current automated tests cover:

- session ownership and finalization races;
- stale run-revision and registry compare-and-swap races;
- process-tree teardown and cleanup retry;
- bridge authentication, framing, limits, and disconnect behavior;
- archive traversal, link, collision, and expansion attacks;
- release-record, package-digest, redirect, and duplicate-record failures;
- executable and engine-returned path confinement;
- native window ownership and stale-handle rejection;
- bounded input commands;
- secret-safe error and context projections;
- component cancellation and crash recovery.

Before release, host integration tests must prove awaited disposer failure and
retry before unload. Before their own admission, WebSurface, media transforms,
deterministic scenarios, diagnostics bundles, and persisted artifacts must have
focused security tests for the policies above. Protocol codecs, project
parsers, archive readers, image validation, and media metadata readers require
property-based or fuzz testing appropriate to their untrusted boundary.
Real-engine security tests must include malicious fixture messages and files as
well as valid projects.

## Reporting vulnerabilities

Security reports should follow the repository's `SECURITY.md` once published.
Reports should identify the affected plugin version, engine and exact runtime
version, operating system, reproduction steps, and whether untrusted project or
network input is required. Public issues should not contain secrets, exploit
payloads against active services, or vendor authorization material.
