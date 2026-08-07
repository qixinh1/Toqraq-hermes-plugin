# Component Management

This document defines how Toqraq discovers, acquires, verifies, installs, and
removes large external components while remaining a standard Hermes Desktop
plugin.

## Scope

Managed components may include after exact release admission:

- certified engine runtimes;
- engine bridge binaries that are not project source;
- engine-owned command-line tools required by an adapter;
- one focused media tool selected through dependency and security review;
- small model or codec runtimes explicitly selected by the user.

Python and renderer source that form the Hermes plugin are not managed
components. User projects and their assets are never stored in the component
store.

## Installation objective

The plugin installation path is one standard Hermes command:

```text
hermes plugins install <owner>/<repository> --enable
```

The installed plugin contains its backend, prebuilt Desktop entry, bundled
skills, schemas, translations, and any component release records admitted for
that exact plugin revision. It does not contain a Godot, Unity, Unreal, Cocos,
or media-tool distribution.

Large components are prepared from the Toqraq pane when a project needs them.
The user does not leave Hermes for a Toqraq setup flow or modify a global
engine installation.

The plugin package must use only dependencies supplied by its package or by a
documented Hermes plugin contract. It must not run `pip install` into the
Hermes interpreter. Windows APIs used by the plugin are called through the
Python standard library and `ctypes` unless Hermes provides a native boundary.

## Component identity

A component is selected by a complete immutable identity:

```text
component_id
version
build_id
platform
architecture
package_digest
```

The component ID describes purpose, such as `engine.godot`,
`bridge.unity.editor`, or `tool.ffmpeg`. Version syntax is owned by the
component provider and remains an opaque validated string in shared code.

Two packages with different digests are different builds even when their
display version matches.

## Certified release records

The process-local composition root constructs a strict
`CertifiedComponentCatalog` from immutable `ComponentRelease` values defined
by admitted contribution code in that exact plugin version. The current
production catalog is empty; no JSON record loader, separate catalog directory,
or runtime-discovered source exists. An admitted release contains:

- immutable component identity;
- human-readable label;
- source and publisher;
- package URL and exact digest;
- exact package and installed byte lengths;
- archive or official-installer strategy;
- named entry points;
- component dependencies;
- license and authorization requirements;
- expected installed manifest;
- complete contribution capabilities enabled by the component;
- exact bridge identity, protocol, and separately declared native RPC
  capabilities when the component hosts a runtime bridge.

For a published component tree, `expected_tree_sha256` is the SHA-256 of its
canonical content manifest. The digest begins with the fixed format marker
`toqraq-component-tree-v1` followed by a zero byte. For every regular file in
UTF-8 bytewise relative-path order, it then hashes: a four-byte unsigned
big-endian path length, the NFC UTF-8 path, an eight-byte unsigned big-endian
file length, and the raw 32-byte file SHA-256. Directories, links, metadata
timestamps, and the generated root `component.json` are excluded. The
installer computes this value from staging before publication. Repair rehashes
the files and compares the same value with the immutable bundled release
record, so changing both an installed file and its writable local manifest
cannot make an altered build appear certified.

`installed_bytes` is the sum of those same regular-file lengths. It excludes
archive framing, directories, and the generated `component.json`. A candidate
build may calculate package, file, installed-size, and tree facts with the
production algorithms, but those facts are not a certified release record.
Immutable package/provenance URLs and an explicit admission decision must still
exist before runtime composition can consume them.

The engine `RuntimeCatalog` lists only its certified runtime releases. If a
focused media tool is admitted later, its composition must register exact
certified releases explicitly. The shared component installer accepts one
already-resolved release and therefore neither chooses an engine version nor
scrapes a vendor release page.

An engine runtime catalog consumes only the opaque component release IDs that
its engine package explicitly registers. It validates the component kind,
identity, bridge facts, named entry points, complete baseline capabilities, and
the bridge-native capability subset before
exposing a `RuntimeRelease`; it does not discover a runtime by scanning the
component catalog or interpreting a component name.

A new selectable build requires a standard Toqraq plugin update after its
adapter, bridge, native build, notices, and complete conformance suite pass.
Runtime discovery cannot silently turn an upstream release into a supported
build. Installed components remain usable offline after a plugin update
removes their release record, but they are not selected for a new session.

## Store layout

Managed state lives below the Hermes home and never below a user project:

```text
$HERMES_HOME/toqraq/
|-- components/<identity-key>/
|-- downloads/
|-- staging/
|-- locks/
`-- logs/
```

Each published component directory contains `component.json`. The manifest
records the immutable identity, source, package digest, installed files or
official installer receipt, named entry points, and expected capabilities.

`identity-key` is a lowercase SHA-256. Its input begins with
`toqraq-component-identity-v1` and a zero byte. Each UTF-8 identity field is
then framed by a four-byte unsigned big-endian length in this order: component
ID, version, build ID, platform, architecture, and package SHA-256. Domain
values therefore never become path segments, and two different package
digests cannot share a destination. The manifest remains the human-readable
source for listing and diagnostics; the opaque directory name is never shown
as a version label.

An installation directory without a valid manifest is not installed. An entry
point is resolved relative to the component root and must remain inside it.

## Component ports

The common application boundary has three small ports:

- `ComponentInventory` lists certified releases and resolves one opaque
  release ID;
- `ComponentPreparation` prepares or repairs one exact release with
  cancellation and progress;
- `ComponentRemoval` removes one exact unleased release with cancellation and
  progress.

`ComponentJobService` owns asynchronous work, idempotent active-job joining,
retention, cancellation, and public snapshots over those ports. The component
adapter owns release lookup and translates downloader, installer, store, and
lock failures once. Archive readers, HTTP clients, vendor hubs, filesystem
stores, capacity probes, and process launchers remain concrete infrastructure
behind it.

Release selection stays in the engine runtime catalog or focused media
composition. The component boundary receives an already-selected opaque
release ID and never chooses a different engine version.

## Exact preparation chain

Component preparation follows one explicit chain:

```text
ComponentReleaseResult
  -> explicit user action when required
  -> ComponentJob
  -> VerifiedStaging
  -> ComponentInstallation
  -> ComponentLease
```

The read-only release result is the installation plan shown before network or
disk mutation. It reports:

- exact components and versions;
- package and installed size estimates;
- target store;
- license or login requirements;
- expected capabilities;
- operations that invoke an official vendor installer.

The user confirms an engine download, license handoff, or vendor operation
from the Hermes pane by starting the job. The read-only release result remains
visible with its exact version, source, sizes, license, authorization, target,
and readiness. There is no second persisted plan object or mandatory workflow
state.

The engine `RuntimeProvisioner` composes verified component installations and
leases for the exact `RuntimeRelease` supplied by the shared project-runtime
selection use case into one `PreparedRuntime`. It never accepts a looser
selection, queries the runtime catalog, or substitutes an equivalent release.
That exact value passes through runtime preparation and launch planning;
neither operation queries the catalog or chooses another installed version.

Runtime preparation acquires the exact component mutation token, rehashes the
published tree, resolves every certified entry point, and performs a final
cancellation check before it acquires the live lease. The same cancellation
token is checked during directory enumeration and at every file-read chunk.
Lease acquisition is the ownership commit: a cancellation that races after
the commit belongs to normal session cleanup, and the provisioner performs no
later filesystem lookup or alternate selection. Before releasing the mutation
token, the provisioner places both it and the committed lease under one
prepared-component resource. A failed native mutation release is retained by
that resource instead of triggering a rollback that can lose both owners; its
idempotent cleanup retries the mutation first and releases the lease only after
the mutation release succeeds.

## Installation task

Long operations are owned tasks rather than long HTTP requests. Job state is
`queued`, `running`, `cancelling`, `ready`, `failed`, or `cancelled`. Work phase
is independently `checking`, `downloading`, `installing`, `verifying`,
`removing`, or `ready`. A prepare job cannot enter `removing`; a removal job
cannot enter download, install, or verification phases. Phase and exact byte
progress are monotonic and every snapshot carries a monotonic revision.

Desktop derives localized progress text from state and phase. A repeated start
for the same release and action joins the active job; an opposite mutation is
a conflict. The immediate start response and subsequent task reads are bounded.
Events may accelerate display updates, but the task read API remains
authoritative after reconnect.

The service also returns a bounded creation-ordered snapshot containing only
its current active jobs. This read is recovery metadata, not another owner or
history store: it exposes no task handle, cancellation primitive, worker
state, filesystem path, or terminal history and performs no mutation. A
remounted Desktop pane may continue polling the unique prepare operation whose
opaque release ID appears in its exact setup plan. Unknown, repeated,
ambiguous, removal, and unrelated operations are not adopted. The subsequent
retained operation read resolves a list-to-terminal race; once no operation is
available, the component inventory determines current readiness. If several
plan components are already being prepared, the pane observes them one at a
time in exact setup order and recovers the next operation after terminal
reconciliation.

Cancellation stops network and extraction work at a safe boundary, removes
partial staging, and preserves any previously published installation. It does
not wait for an entire package to finish before acknowledging cancellation.

Downloads support retry and continuation when the source permits byte ranges.
A task resumed after Hermes restart revalidates every retained byte before
publication.

## Atomic publication

Archive packages use this publication sequence:

1. acquire the component's cross-process mutation lock;
2. recheck whether the exact identity is already installed;
3. verify disk capacity against the plan;
4. download into the managed downloads directory;
5. validate the bundled release record and verify the package SHA-256 digest;
6. extract into a unique staging directory under bounded policy;
7. validate installed entry points and component identity;
8. write `component.json` last inside staging;
9. rename staging to the exact destination;
10. release the lock and publish `ready`.

A previously published installation remains available until the new
installation has been verified. Temporary paths are never treated as runtime
installations.

Official vendor installers implement the same semantic result. Their adapter
must validate the installer source, use an explicit managed destination, read
the vendor's completion receipt, verify required entry points, and then write
Toqraq's component manifest.

## User environment isolation

Managed engines are launched by absolute path. Toqraq does not:

- add an engine to `PATH`;
- change file associations;
- register a global default engine;
- replace or update an existing user engine;
- scan the whole machine and silently choose an installation;
- write engine files into the Hermes plugin source directory.

Existing user engine installations are ignored. This keeps runtime identity,
bridge capability, cleanup, and diagnostics deterministic whether or not the
machine already contains an engine.

Some vendor license services and GPU drivers are host facilities. The pane
states this requirement instead of claiming that those facilities are part of
the managed store.

## Licenses and authorization

License and account requirements are certified release facts, not generic
error text.
Before an official installer runs, the pane displays:

- publisher and component;
- license URL;
- whether account authentication is required;
- download and installed size;
- the action that will open.

Toqraq never accepts terms, creates an account, extracts a vendor token, or
stores a vendor password on the user's behalf. Credentials use Hermes secret
facilities or the vendor's own authenticated application.

When authentication completes outside the pane, the existing task detects the
official install state and resumes. The user does not restart setup or enter a
shell command.

## Download and extraction policy

Every download:

- begins from an allowed HTTPS origin declared by the certified release record;
- validates the final origin after redirects;
- has connect, read, total-size, and idle-progress limits;
- streams to disk without buffering the package in memory;
- verifies the exact digest before execution or extraction;
- removes unverified data when the task is abandoned.

Every repository-owned archive extractor:

- rejects absolute paths, traversal, links, devices, and ambiguous names;
- rejects duplicate and case-colliding entries;
- bounds entry count, entry size, total expansion, and path depth;
- writes only below the unique staging root;
- preserves executable permission only where the manifest requires it.

Limits are declared once by the component policy and tested at their boundary.
They are not scattered literals in download, archive, and adapter modules.

## Version selection UX

The project pane shows:

- detected engine;
- selected exact version;
- installation state;
- required download size;
- preparation progress;
- the next useful action.

The default selection comes from the project declaration when the bundled
certified records contain that exact release. Otherwise the pane asks for a
version among the builds certified by the current plugin. When typed
workspace-choice persistence is implemented, that choice may be stored for the
workspace. The current Desktop stores no version choice, and the production
catalog offers none.

Internal distribution IDs, checksum algorithms, and archive names stay in an
advanced diagnostics view. A missing selected engine blocks Start and exposes
one explicit preparation action. Once preparation refreshes setup to ready,
Start validates the project and launches that exact engine.

## Removal and leases

A live play session holds a `ComponentLease` through its `PreparedRuntime`. A
leased component cannot be
removed or repaired in place. Removal is explicit and reports the sessions or
tasks that currently use the component.

The component inventory reports live-lease state for each exact release;
Desktop never substitutes a visible-session guess for that fact. Lease cleanup
first releases its native lock and only then removes its receipt. If either
step fails, the lease object retains the unfinished ownership and a later
idempotent close retries it; a cleanup failure never discards the only strong
owner. The prepared-component resource applies the same rule to a mutation
token whose release was deferred after lease commit.

Toqraq does not automatically remove an engine because a Hermes conversation
ends. Sessions release leases; installed engines remain available to other
projects until the user removes them.

## Failure model

Component failures use typed codes and structured details. User-facing text is
resolved through Hermes internationalization. Important codes distinguish:

- requested release unsupported;
- authorization required;
- license action required;
- insufficient space;
- download interrupted;
- download origin rejected;
- certified release record invalid;
- checksum mismatch;
- unsafe archive;
- official installer failed;
- installed entry point missing;
- component in use.

Errors include the exact component identity, failed phase, safe retry action,
and diagnostics artifact when available. Secrets and signed authorization
material are never included.

## Verification

Unit and contract tests cover:

- opaque engine version identifiers;
- exact release-to-launch propagation;
- certified release-record and installed-manifest validation;
- redirect-origin policy;
- package size and digest failures;
- archive traversal and expansion limits;
- disk-space failure before download;
- cancellation in each mutable phase;
- cross-process installation locking;
- crash recovery from downloads and staging;
- leases and removal;
- independence from existing user engine installations;
- English and Simplified Chinese message-key parity.

End-to-end tests start with an empty Hermes home, install the standard plugin,
prepare a real engine through the pane, launch a fixture project, and confirm
that the session reports the exact installed identity.
