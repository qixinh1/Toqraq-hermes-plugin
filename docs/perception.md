# Perception Contract

This document defines how Toqraq gives a Hermes model reliable evidence about
a game project and a running game. Perception is read-only, bounded, typed, and
available on demand. It does not create a second project model or fill every
LLM request with engine state.

## Outcomes

Perception must let the user or model answer:

- What engine project is active, and which exact runtime does it require?
- What source, scenes, assets, dependencies, settings, and inputs define it?
- Is the project importable and runnable now?
- What process is running and which preview, observation, and control features
  are ready?
- What is visible, audible, instantiated, changing, failing, or slow?
- What changed after a source edit or model-driven game action?
- Which detailed evidence should be fetched next?

Answers distinguish direct engine facts, project-file facts, process facts,
media metadata, model inference, and user-provided intent.

## Current availability

Focused live hierarchy, object, diagnostics, metrics, and frame services and
their strict Bridge contracts are implemented. The Godot 4.7.1 candidate has
exercised them through the production listener and adapters, but production
has no admitted engine, so an ordinary install cannot produce a live result.
Broad project inventory, media inspection, and temporal capture are not
implemented. A recognized active workspace contributes only a bounded cached
setup summary; detailed workspace perception remains explicit and tool-driven.

## Sources

| Source | Owner | Examples |
| --- | --- | --- |
| Project files | `ProjectProbe` and focused project readers | manifests, version, scenes, scripts, resources, settings, dependencies |
| Engine import or compile | engine contribution | import status, parser/compiler diagnostics, missing resources |
| Process tree | process adapter | root identity, state, exit, stdout, stderr |
| Runtime bridge | focused feature ports | hierarchy, objects, diagnostics, audio state, metrics, control acknowledgements |
| Preview surface | frame capture and display boundary | viewport identity, current frame, short bounded capture |
| Media tools | media adapters | dimensions, streams, duration, codecs, loudness, transparency |
| Hermes models | host provider or auxiliary task | semantic image, audio, video, UI, or scene interpretation |

An observation records its source and revision or timestamp. Model inference is
never represented as an engine fact.

## Project perception

The default project read is a concise `ProjectSummary` containing:

- confined project root and stable workspace identity;
- detected engine, confidence evidence, and declared version when present;
- selected exact managed runtime when resolved;
- entry scene, level, map, or startup target;
- viewport and platform hints;
- counts and bounded summaries for scenes, source files, assets, packages,
  plugins, inputs, and diagnostics;
- revisions that allow focused follow-up reads.

Detailed operations page through engine-owned concepts:

- project entries by kind and path prefix;
- scene or level structure;
- scripts and declared dependencies;
- resources and reference relationships;
- input/action mappings;
- plugins, packages, autoloads, and build configuration;
- import, parse, compile, and missing-reference diagnostics;
- media inventory and technical suitability.

Toqraq uses engine parsers where they are stable and public. It uses a small
owned parser only for a focused project marker or configuration invariant. It
does not parse an entire engine serialization format merely to avoid invoking
the engine.

## Runtime perception

Runtime state separates process and feature readiness. A running process does
not imply that the bridge, preview, or control is ready.

### Hierarchy

A hierarchy read returns a revision and a bounded page of entries containing:

- opaque object reference;
- display name and engine-native type;
- parent reference and bounded child summary;
- optional component/type summaries;
- engine-native facts in a namespaced typed extension.

The ordinary result is not an unrestricted nested tree. Callers can request a
root, depth, type/name filter, page limit, and revision. A stale cursor returns
a typed revision error and the current revision; it does not silently combine
two runtime states.

The baseline page is flat and contains at most 256 entries. A request selects
depth 0 through 16 and may supply at most 32 exact engine-native types. A
continuation cursor is accepted only with its originating opaque revision.
Each entry reports the full native component-type count, at most 32 unique type
summaries, and whether that summary was truncated.

### Object inspection

Object inspection takes explicit opaque references and a field selection. It
returns bounded properties, components, resource references, and engine-native
extensions. Expensive values, binary resources, long strings, and recursive
objects become summaries or artifact references.

The common contract does not offer arbitrary method invocation or unrestricted
property mutation. Engine-native debug actions require a separately reviewed
typed capability.

The baseline object read accepts at most 64 unique run-scoped references and
selects from properties, components, resources, and extensions. Every selected
group is present even when empty; unselected groups are absent. Each group
reports its total count and truncation independently. Property values are
scalars, opaque references, or explicit summaries. Engine extension facts are
flat, scalar, namespaced, unique, and bounded; they are not a recursive escape
hatch for an engine object graph.

### Diagnostics and process output

Diagnostics retain the source of engine compile/import/runtime records and
bridge failures. Process stdout and stderr remain a separate platform-owned
observation rather than being converted into engine diagnostic records.

Diagnostic reads use a sequence cursor, severity/source filters, and a limit. Records include
timestamp, source, severity, code when supplied, summary, bounded details,
optional location, and exact runtime identity. Original engine text is not
translated or inserted wholesale into notifications.

The bridge page contains at most 200 records in strictly increasing sequence
order. Source selections are namespaced and severity is one of debug, info,
warning, error, or fatal. A cursor is paired with its opaque diagnostic
revision so reconnect and stale reads cannot splice two streams.

The process-output read returns only the current latest tail from the owned
process tree. It preserves global stdout/stderr chunk sequence, reports whether
older characters were discarded, and names either collector stream that
failed. The public tail contains at most 16,384 Unicode characters even when
the platform owner retains a larger internal tail. It has no request cursor,
pagination, history database, or unconditional model-context injection.

### Metrics and audio state

Metrics are named, typed, timestamped, and bounded. The baseline includes a
small performance snapshot; engine-specific counters remain namespaced. A
caller chooses groups or fields and receives collection cost or availability
when useful.

One bridge metrics snapshot contains at most 128 boolean, exact-integer, or
finite-number samples. Names, groups, and optional units are namespaced. The
result reports the total available count, truncation, unavailable selections,
and bounded collection duration; callers narrow a truncated selection instead
of paging across changing samples.

Audio perception reports engine-supported buses, active sources, levels,
muting, and playback state when available. It does not capture system audio or
microphone input without an explicit capability and user action.

## Visual and temporal perception

`FrameCapture` returns the real viewport dimensions, capture timestamp, encoded
dimensions, opaque frame revision, and validated immutable PNG bytes.
The port completes only after the engine-bridge transport has received and
verified the complete binary transfer. Artifact creation is a later
session-owned use case; transport IDs and pending-transfer state never enter
the core result.

The bridge capture encoding is the fixed PNG baseline, not a one-value format
option repeated through query, result, and transfer objects. A request supplies
maximum dimensions, native or contain scaling, and a byte ceiling. The JSON
result contains only a binary announcement with its PNG MIME type, encoded
dimensions, byte length, SHA-256, transfer ID, and opaque frame revision. The
following transport stage validates the announced binary against that response
and the original request before it constructs the core result.

`native` preserves the viewport dimensions exactly and therefore fails when
either viewport dimension exceeds the requested maximum. `contain` never
enlarges a viewport that already fits. Otherwise it selects the limiting axis
using integer cross-products, sets that encoded dimension to its requested
maximum, and computes the other as the source dimension multiplied by the
same maximum then divided by the corresponding source dimension with integer
floor, clamped to at least one pixel. The encoded dimensions must equal this
deterministic result and fit completely inside the requested maximum.

The transport accepts only exact immutable `bytes`. Its length must equal the
announcement and be no greater than the request byte ceiling, its SHA-256 must
match, and it must begin with a PNG signature and an `IHDR` whose dimensions
equal the announced encoded dimensions. A transfer that fails any check never
becomes a `FrameCaptureResult` or session-owned media reference.

A short capture is an owned operation with explicit maximum duration, frames,
dimensions, bytes, and time. It is used only when one frame cannot explain
animation, timing, input, or transition behavior. Toqraq does not continuously
record a user's game session.

Visual analysis follows:

```text
capture evidence
  -> validate and create a bounded session-owned source file
  -> invoke an enabled Hermes image or video analysis tool when asked
  -> return inference with the source revision and returned tool evidence
```

The model may reason about UI layout, visual defects, animation, contrast,
composition, state transitions, or whether an intended change is visible. Its
inference is attached to the source capture and is not cached as live engine
truth after the runtime revision changes.

## Media perception

Media inspection occurs before transformation or engine import. Depending on
kind, it reports:

- container and codec;
- byte size, width, height, channels, sample rate, duration, frame rate, and
  frame count;
- alpha, color-space, orientation, and animation facts;
- loudness, peaks, silence, and loop metadata;
- embedded streams or attachments under strict limits;
- source, author, license, attribution, and acquisition record when known;
- selected engine import constraints and likely issues.

Semantic understanding uses a bounded preview or sample. It never sends an
entire large source automatically. User or project-private content follows the
active Hermes provider and approval policy.

## Revisions, cursors, and events

Every mutable observation family has an opaque revision. Ordered streams also
have a monotonic per-session sequence. A response states whether it is a full
snapshot, page, or change set.

The transport promotes a response only after validating it against the exact
query held by the pending request. A supplied revision must be echoed exactly;
pages cannot exceed their requested limit; diagnostics must match requested
filters; object references and selected groups must match the request; and
request-specific byte ceilings still apply after ordinary protocol bounds.
Operation-specific response types make a generic result `kind` discriminator
and a returned count that merely repeats tuple length unnecessary.

Common Bridge adapters perform this promotion inside the pending request's
method-specific closure and return only `HierarchyPage`, `ObjectSnapshot`,
`DiagnosticsPage`, `MetricsSnapshot`, `FrameCaptureResult`, or the exact
control acknowledgement. Neither a generic Bridge call nor a boundary DTO is
part of a perception or development service contract.

Events notify the Desktop that authoritative state may have changed. They
contain event type, Hermes session ID, sequence, timestamp, revision, operation
or trace ID when relevant, and a bounded payload. They do not contain full
hierarchies, logs, screenshots, or media.

After reconnect or a sequence gap, the consumer reads authoritative state and
resumes from the returned revision. The plugin does not introduce a durable
event broker for process-local game state.

## Model-facing result policy

Results are optimized for useful evidence rather than maximum serialization:

1. return identity, readiness, counts, revision, and the most relevant bounded
   facts first;
2. require a limit and selection for potentially large data;
3. use opaque cursors rather than page numbers over mutable data;
4. return bounded session-owned references for binary or long-form evidence;
5. include a suggested next query only when it follows from a typed truncation
   or failure, not as generic workflow prose;
6. never silently truncate: pageable results return a flag, counts, and a
   continuation cursor; fixed latest-tail results return an explicit loss flag
   and intentionally provide no history cursor.

Bounds are named policy values in the owning contract. They are tested but not
made arbitrary end-user settings.

## Context capsule

The `pre_llm_call` capsule is a projection of already available summary facts.
For a cached live game it contains owner/run identity, a bounded project-path
tail, exact runtime, process state, feature readiness, an optional ready-preview
summary, capability IDs, and the four relevant skill names. Otherwise a ready
workspace binding contains only owner, bounded path, detected engine, selected
runtime when one exists, setup action, viewport hint, and skill names.

Capsule generation performs no project scan, network call, model inference,
component operation, or engine launch. If the projection is not immediately
available, the hook returns no context. Full evidence remains tool-driven.

## Perception and action loop

A skill may recommend this flexible evidence loop:

```text
observe -> form a hypothesis -> make one visible change or input sequence
        -> run or continue -> observe the relevant revision -> compare
```

The loop is not enforced. A user may work manually, ask only for analysis, or
skip runtime verification. Toqraq reports what was and was not observed rather
than inventing confidence.

## Safety and privacy

- Project and engine-returned paths are confined before reads.
- File, tree, property, diagnostic, capture, media, and event sizes are bounded
  independently.
- Secrets, bridge credentials, provider settings, and full environments never
  enter observations.
- Source contents are returned only by an explicit project read or existing
  Hermes file capability.
- A delegated task receives only the evidence required by its request.
- Temporary captures are session-owned and removed by the session cleanup
  policy.

## Acceptance

Every supported engine/version proves that a model can:

1. identify a fixture project and exact runtime without configuration;
2. distinguish process running from preview/perception/control readiness;
3. page hierarchy and inspect selected native objects without an unbounded
   response;
4. obtain current diagnostics by cursor and the current bounded startup-output
   tail with explicit loss state;
5. capture a verified real frame and a bounded performance snapshot;
6. observe an input-driven state change at a later revision;
7. use a bounded session-owned reference for media or visual inference without
   binary context inflation;
8. finalize the Hermes session and leave no perception task or temporary
   capture behind.

The shared conformance and adversarial requirements live in
[testing.md](testing.md).
