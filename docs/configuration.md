# Configuration and Settings

This document assigns one owner to every configurable value. Configuration is
kept small: automatic detection is the default, and a setting exists only when
different users or workspaces need a durable choice.

## Principles

1. A user is not asked for information that can be detected reliably.
2. The setting lives at the narrowest lifetime that owns it.
3. Secrets stay in Hermes-owned secure configuration.
4. Bundled certified release records and engine descriptors own supported
   build metadata.
5. Protocol and security constants are not user preferences.
6. The Desktop never invents a second backend configuration source.
7. Unknown settings fail validation; they are not silently ignored.

## Ownership and lifetime

| Scope | Examples | Owner |
| --- | --- | --- |
| Hermes user | creative provider credentials and selected models | Hermes provider configuration |
| Toqraq user | component storage root, cache budget, default license filters | Toqraq backend settings |
| Workspace | future engine selection, version policy, and game-domain media defaults | future Toqraq workspace settings |
| Hermes session | pending start, active game, prepared runtime, feature readiness, preview attachment | in-memory session owner |
| Hermes layout | preview pane placement and size | Hermes Desktop layout tree |
| Desktop view | future pane-local display preference | Hermes Desktop plugin storage |
| Engine catalog | exact builds, sources, digests, sizes, licenses, bridge identity | bundled certified release records |
| Engine package | detection rules, launch defaults, setting schema, capability IDs | engine descriptor |
| Protocol module | method names, bounds, handshake version | named source constants |

Session state is never persisted as a workspace preference. Workspace selection
is never keyed only by a chat session. A process-wide component install is not
duplicated for each session.

A pending start and active game are strong resource owners, not settings
records. Failure or cancellation retains their acquired runtime leases,
process tree, bridge, tasks, and preview resources until idempotent cleanup
succeeds. Finalization and plugin shutdown use that same cleanup path.

## Current persistence boundary

The current Desktop persists no Toqraq setting. Hermes owns the active
workspace and preview-pane visibility, placement, and size. A plugin-lifetime
observer projects the public active task ID and workspace through the typed
workspace-context endpoint; it runs whether or not the preview pane is
mounted. The backend retains only the latest ready recognized-project summary
for that task. `pre_llm_call` reads cached live-session facts first and this
already-synchronized summary second; it performs no workspace probe itself.
Because the Hermes hook does not carry a workspace, a first turn may precede
Desktop synchronization and receive no workspace capsule. Production engine
and component catalogs are empty.

The workspace settings below define the owner required before durable choices
are added. They are not a claim that such persistence exists today.

## Project and engine selection

The ordinary project candidate is the active Hermes workspace directory. An
empty workspace produces a local open-project state without a backend probe.
The project probe returns zero, one, or several engine candidates:

- zero candidates shows a localized explanation and lets the user choose a
  workspace or project directory through a public Hermes surface when
  available;
- one unambiguous candidate is selected without asking;
- several candidates show one focused chooser containing engine, project root,
  detected version, and confidence evidence.

The durable workspace choice contains:

```json
{
  "project_root": "...",
  "engine_id": "godot",
  "version_policy": {"kind": "exact", "version": "..."}
}
```

The public user choice is engine and version policy. Archive channel,
executable filename, vendor product code, bridge artifact, and launch probes
remain implementation details.

An exact policy is required for a running session. A convenience policy such as
`recommended` is resolved to an exact version before provisioning and recorded
as that exact version in the session.

One project-runtime selection service applies this policy for Setup, Start,
and Hermes tools. Setup projects the selected release and its component
readiness for the UI; it does not persist a launch ticket. Start reruns the
same deterministic service against the immutable bundled catalog and workspace
choice, then passes the returned `RuntimeRelease` object directly to the
engine's provisioner. The provisioner does not query the catalog or resolve a
selection again.

When the project-format catalog is empty, Setup returns `engine_unavailable`
before project probing or workspace-choice lookup. When a registered format
recognizes the project but the engine contribution catalog is empty, Setup
returns `runtime_unavailable` with the detected project facts and no release
or component identity. Start reports a typed unavailable failure. An existing
workspace choice does not turn an uncertified engine into a selectable one.

Component acquisition and repair are explicit setup jobs. Start only validates
and leases the already installed components named by the selected release. A
missing or invalid component blocks Start with one localized preparation
action; it never causes a hidden download or substitute release.

## Component settings

The ordinary user does not configure component paths. Toqraq selects an
isolated default below `$HERMES_HOME/toqraq/`. Advanced settings may expose:

- store root;
- cache size budget;
- automatic cleanup policy for unreferenced archives;
- download proxy inherited from Hermes or the operating system;

Changing the store root affects new operations only after validation. Active
sessions and install jobs retain their original resolved roots. Moving an
existing store is a separate explicit operation with progress and rollback.

## Creative settings

Hermes owns provider credentials and model selection for media tools exposed
to the active task. Toqraq reads readiness only through public Hermes
interfaces and never copies an API key. Image tools remain conditional;
`video_generate` and `video_analyze` also require their opt-in toolsets and
runtime prerequisites. `text_to_speech` requires the exposed `tts` toolset and
uses the provider and voice configured by the user in Hermes. No setting
assumes music or sound-effect generation, agent-callable transcription, or a
generic artifact-store API.

Toqraq may store workspace game-domain defaults such as:

- preferred sprite dimensions and pixel-density policy;
- texture, audio, and video target formats;
- asset destination directories;
- allowed license classes and attribution requirements;
- loudness, loop, frame-rate, or transparency preferences.

Every default remains overridable in an explicit tool call. A skill can propose
a value but does not rewrite settings silently.

## Renderer settings

Desktop storage contains only non-sensitive presentation preferences. Backend
and session facts come from typed REST reads and events. In particular, the
renderer does not persist:

- engine executable paths;
- component installation records;
- authentication tokens;
- bridge credentials;
- an authoritative running-session snapshot;
- raw error details or process logs.

A future Toqraq settings surface must be a plugin route or dialog built from
public Hermes Desktop contributions. No such route or persisted setting exists
now, and private Hermes Settings modules are never imported.

## Environment variables

Environment variables are reserved for development, test isolation, and host
bootstrap where no public configuration API exists. They are documented in one
place, validated at process startup, and converted to typed settings. Product
behavior must not depend on an undocumented variable.

Tests may override:

- the Hermes home or component store;
- fixture engine executable and exact version;
- bundled release-record fixtures;
- network endpoints and timeouts;
- interactive desktop availability.

Production engine selection never scans arbitrary environment variables or
uses `PATH` as an implicit preference.

## Catalog and descriptor configuration

Release records are versioned, strict data bundled with the standard plugin
package. They contain variable distribution facts, not executable policy.
Engine descriptor code decides how a validated record maps to a provision and
launch operation. There is no production catalog URL, trust-root setting, or
scheduled catalog refresh.

The engine contribution record set may be empty. This represents the exact
fact that the installed plugin build currently offers no certified engine; it
does not weaken validation for any contribution or runtime record that is
present.

For one engine ID, public version, platform, and architecture, a plugin release
contains at most one currently selectable certified runtime release. Exact
build and distribution identities remain internal facts on that record.
Catalog validation rejects duplicate selectable tuples instead of asking an
ordinary user to choose between implementation builds.

A catalog record may contain:

```text
component identity
exact engine and build version
platform and architecture
source and license
compressed and expanded size
SHA-256 package digest and provenance reference
named entry points
bridge identity and protocol
declared capability IDs
```

Removing a release record in a plugin update removes that build from new
selection. It does not silently delete an installed component or stop an
active session.

## No-scattered-literals rule

"No hardcoding" means every variable product or environment fact has one
named owner. The following are forbidden in application logic:

- user-visible prose;
- engine versions and download URLs;
- installation roots and executable guesses shared across modules;
- product policy timeouts and retry counts repeated as literals;
- engine IDs used to branch outside the engine catalog or contribution;
- colors, locale assumptions, provider IDs, and license defaults;
- duplicate request constraints.

Stable facts are expressed directly and locally:

- JSON-RPC method IDs in the bridge protocol module;
- PNG magic in the PNG parser;
- Win32 flags in the Windows adapter;
- error codes in the owning error definition;
- allocation and payload bounds beside the code that enforces them.

These values are named, cite their source in a concise comment when necessary,
and have direct tests. Moving them into a global `constants` file or editable
user configuration would hide responsibility and weaken validation.

## Settings schema replacement

Settings are versioned typed documents with strict validation and atomic
writes. A new schema replaces the old schema in one deliberate change; the
application does not accumulate dormant readers and branches. A destructive
schema change must:

1. update this document and the owning contract;
2. define the single new default or require one focused user choice;
3. remove displaced keys and code paths;
4. test invalid, missing, and concurrent writes;
5. surface a localized recovery action when persisted state fails current
   validation.

There is no generic settings framework inside Toqraq. Each scope has one small
typed repository only when persistence is actually required.
