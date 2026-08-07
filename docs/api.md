# API and Tool Contracts

This file defines the engine-neutral public contract. Pydantic models below
`toqraq/contracts/` are the one source for HTTP bodies, Hermes tool arguments,
successful results, events, and their generated schemas.

Hermes mounts the dashboard router below `/api/plugins/toqraq/`. Paths in this
document are relative to that prefix. Request bodies are strict JSON objects;
unknown or invalid fields return the shared error envelope with HTTP 400.

## Ownership

`EngineSession.id` equals the owning Hermes session ID. `POST /sessions`
requires `hermes_session`; starting again with the same value first stops and
releases the game it owns. Every route below `/sessions/{session_id}` uses that
same ID. Once Hermes finalizes an ID, the plugin rejects later starts for it.
The HTTP presenter separates that host owner before calling `SessionService`;
the service receives the same `GameStartRequest` command as the Hermes tool.

Hermes game tools do not expose an ID argument. Their target is the calling
tool context's `task_id`.

## Component endpoints

| Method and path | Body | Result |
| --- | --- | --- |
| `GET /components` | none | selectable release summaries, readiness, and exact live-lease state |
| `POST /component-jobs` | `{release_id, action}` | an immediate component-job snapshot |
| `GET /component-jobs/active` | none | `{jobs}` containing the bounded current active-job snapshots |
| `GET /component-jobs/{operation_id}` | none | the authoritative current job snapshot |
| `POST /component-jobs/{operation_id}/cancel` | none | the authoritative cancelling or terminal snapshot |

`release_id` is the opaque digest-derived identifier returned by the list; a
caller never reconstructs component paths or package identity fields. `action`
is `prepare` or `remove`. Starting a job never holds the request open for a
download, extraction, or removal. Starting `prepare` again after failure is
the retry operation; concurrent preparation requests for the same release
join the same active job.

The active-job read is ordered by job creation and contains only `queued`,
`running`, or `cancelling` snapshots. It exists solely to let a remounted
Desktop surface recover observation of process-owned work; reading it never
starts, joins, cancels, or otherwise changes a job. Desktop matches only a
unique `prepare` jobs whose `release_id` is present in the exact setup result,
one at a time in setup order. It ignores malformed, duplicate, ambiguous,
removal, and unrelated entries.
After selecting an operation, `GET /component-jobs/{operation_id}` is
authoritative even if the job became terminal between the two reads; if the
retained operation is no longer available, a fresh component inventory is the
readiness authority.

A job reports `queued`, `running`, `cancelling`, `ready`, `failed`, or
`cancelled`, plus its current `checking`, `downloading`, `installing`,
`verifying`, `removing`, or `ready` phase and bounded byte progress when the
phase has a byte total. A failure contains the shared `PublicError`.
Cancellation is cooperative before the atomic publication point. If
publication has committed, the job reports the verified component as ready
instead of pretending that rollback occurred.

Runtime provenance, executable paths, stores, lock files, staging paths, and
download mechanics remain private. Release summaries include the source,
exact engine/tool version, platform, architecture, download and installed
size, license/account requirements, readiness, and whether an exact live lease
currently prevents removal. Desktop does not infer that fact from session UI
state.

The production certified component catalog is currently empty, so
`GET /components` returns `{"releases":[]}`. There is no separate runtime-list
route: engine and exact-version choices come from `POST /setup`, while
component facts come only from this inventory.

## Setup endpoint

`POST /setup` accepts `{project_dir?, engine?, version?}` and applies the same
project-runtime selection policy as Start. It performs a local, read-only check
and never downloads a runtime. There is no default engine. The response
reports native-display availability, project and probe state, the selected
exact public runtime when one exists, the exact opaque component release IDs
required by that selection, whether preparation is required, bounded engine
or version choices, and one `action`:

```text
engine_unavailable | runtime_unavailable | select_project | select_engine | select_version
install | start | unsupported_host
```

`engine_unavailable` means this plugin build has no registered project format.
Its `engine` is `null`, its project state is `unchecked`, and no project probe
or component read occurs. `runtime_unavailable` means a registered format
recognized the project but no complete admitted engine contribution exists;
the response includes the detected engine and project facts, has no selected
runtime or component IDs, and performs no component read. Desktop uses
returned component release IDs verbatim; it never constructs a component ID
from an engine ID or version.

The following illustrates the DTO after a future release has been admitted; it
is not the current empty-catalog response:

```json
{
  "host": {"platform": "windows", "native_display": true},
  "engine": {
    "id": "godot",
    "runtime": {"version": "4.7.1"},
    "available_versions": [],
    "required_component_release_ids": [
      "1111111111111111111111111111111111111111111111111111111111111111"
    ],
    "runtime_install_required": true
  },
  "project": {
    "path": "D:\\game",
    "state": "ready",
    "viewport_size": {"width": 1280, "height": 720},
    "probed_engine_ids": ["godot"]
  },
  "engine_choices": [],
  "action": "install"
}
```

## Workspace context endpoint

`PUT /workspace-context/{session_id}` accepts the same
`{project_dir?, engine?, version?}` setup request and returns its `SetupResult`,
or `null` when `project_dir` is absent. The path is the active Hermes task
published by Desktop. This endpoint synchronizes context and setup in one
read-only operation; it never installs, launches, edits, or persists a project.

Starting an update invalidates that task's previous workspace summary before
the project probe begins. Only the newest in-process update may publish its
result. A ready, singly recognized project stores a bounded immutable summary;
every other setup outcome leaves the task unbound. A missing project performs
no probe and is the explicit clear operation. Task finalization and plugin
disposal also clear the binding. `POST /setup` remains the owner-free setup
read and never changes model context.

## Session endpoints

| Method and path | Body | Result |
| --- | --- | --- |
| `POST /sessions` | `{hermes_session, project_dir, engine?, version?}` | running session snapshot |
| `GET /sessions` | none | active session snapshots |
| `GET /sessions/{session_id}` | none | active session snapshot, or `null` when no game is owned |
| `POST /sessions/{session_id}/pause` | `{paused}` | updated session snapshot |
| `POST /sessions/{session_id}/step` | `{frame_count}` | updated session snapshot |
| `DELETE /sessions/{session_id}` | `{run_revision}` | final stopped snapshot |

Starting validates the project and requires the already prepared exact runtime
selected during setup. It never downloads a component. The existing game
remains alive if validation or readiness fails. Launch aspect ratio comes from
the project's declared viewport; callers cannot override it through the public
contract.

No production session can currently be created because the engine catalog is
empty. After an admitted contribution starts successfully, the public session
shape is:

```json
{
  "id": "hermes-session-id",
  "run_revision": 7,
  "runtime": {
    "engine": "godot",
    "version": "4.7.1-stable",
    "build_id": "toqraq.windows.x86_64.release",
    "distribution_id": "toqraq",
    "platform": "windows",
    "architecture": "x86_64"
  },
  "project_dir": "D:/game",
  "root_pid": 1234,
  "process_state": "running",
  "alive": true,
  "exit_code": null,
  "started_at": 1785852000.25,
  "bridge": {
    "id": "toqraq.godot.bridge",
    "protocol": "1.0",
    "capabilities": ["toqraq.observe.hierarchy", "toqraq.play.pause"]
  },
  "capabilities": [
    "toqraq.observe.hierarchy",
    "toqraq.play.pause",
    "toqraq.preview.display"
  ],
  "preview": {
    "state": "ready",
    "error": null,
    "surface": {
      "kind": "native_window",
      "viewport_size": {"width": 1280, "height": 720}
    }
  },
  "perception": {"state": "ready", "error": null},
  "control": {"state": "ready", "error": null}
}
```

`run_revision` distinguishes replacement runs inside the same Hermes session;
it is returned evidence, never a caller-selectable session ID. Readiness values
are independently `unavailable`, `connecting`, `ready`, or `failed`. A failed
value contains the shared `PublicError`. Preview surface data contains only its
kind and real viewport size; native handles, URLs, and credentials never enter
this DTO.

Desktop sends the exact `run_revision` it observed when stopping. The service
checks that owner while holding the session operation gate; a replacement run
causes `session.invalid_state` instead of being stopped by an older request.
Desktop then reads the authoritative owner and accepts a successful terminal
response only when its revision equals the request. The model-facing stop tool
has no revision field because it stops the caller's current run.

## Live perception and input endpoints

| Method and path | Body model | Result model |
| --- | --- | --- |
| `POST /sessions/{session_id}/hierarchy` | `HierarchyReadParams` | `HierarchyReadResult` |
| `POST /sessions/{session_id}/objects` | `ObjectReadParams` | `ObjectReadResult` |
| `POST /sessions/{session_id}/diagnostics` | `DiagnosticsReadParams` | `DiagnosticsReadResult` |
| `GET /sessions/{session_id}/process-output` | none | `ProcessOutputResult` |
| `POST /sessions/{session_id}/metrics` | `MetricsReadParams` | `MetricsReadResult` |
| `POST /sessions/{session_id}/frame` | `FrameCaptureParams` | `FrameCaptureResult` |
| `POST /sessions/{session_id}/input/semantic` | `SemanticInputParams` | `InputAcknowledgementValue` |
| `POST /sessions/{session_id}/input/keyboard` | `KeyboardInputParams` | `InputAcknowledgementValue` |
| `POST /sessions/{session_id}/input/pointer` | `PointerInputParams` | `InputAcknowledgementValue` |
| `POST /sessions/{session_id}/input/text` | `TextInputParams` | `InputAcknowledgementValue` |
| `POST /sessions/{session_id}/input/gamepad` | `GamepadInputParams` | `InputAcknowledgementValue` |

The Bridge parameter and result models above are the same strict Pydantic values used
on the common Bridge boundary when their JSON semantics are identical. Public
routes never accept a JSON-RPC envelope, request ID, method name, binary
announcement, or engine-native session selector. Each operation resolves the
current run owned by the path's Hermes session, holds the shared session
operation gate, requires ready perception or control plus its exact namespaced
Bridge capability, invokes the borrowed port on its owning event loop, and
correlates the result with the original request before returning it. The
process-output read instead holds the same gate while it snapshots the exact
session-owned process tree; it requires no Bridge capability or readiness.

Hierarchy is a flat revision-consistent page, not a nested scene tree. Object
reads use opaque run-scoped references and explicit field groups. Diagnostics
and hierarchy continuations require the revision that issued their cursor.
Metric reads select namespaced groups or exact names. Their bounds and
correlation rules are defined once by the generated schemas and the pure Core
values described in [perception.md](perception.md).

`ProcessOutputResult` is the latest combined stdout/stderr tail, not a log
history. Its chunks retain strict global sequence and stream identity,
`next_sequence` is a snapshot watermark rather than a continuation argument,
`truncated` reports source or public-tail loss, and `failed_streams` is a
canonical subset of `stdout` and `stderr`. The aggregate contains at most
16,384 Unicode characters and offers no cursor or pagination request.

Keyboard input uses W3C `code` and `key` values; it never accepts an engine
keycode. The five input surfaces are semantic actions, W3C keyboard events,
pointer events, Unicode text commits, and standard-layout gamepad events. Each
request is validation-atomic and its acknowledgement count must equal the
complete submitted command count.

The Bridge transports a frame as one authenticated binary PNG following a
strict announcement. `FrameCaptureResult` is the JSON-facing form and contains
`viewport_size`, `captured_at_unix_ms`, `encoded_size`, `frame_revision`, the
fixed `image/png` MIME type, `byte_length`, `sha256`, and canonical
`png_base64`. It contains no transfer ID. The service verifies the request's
dimension and byte ceilings before encoding, and the DTO verifies base64,
length, digest, PNG header, and dimensions.

## Hermes tool mapping

Hermes tools call the same services and serialize the same successful result
models as HTTP. Each declaration owns both its generated request model and its
exact successful result model; returning another Pydantic model is an
unexpected boundary failure, never alternate success JSON. Their argument
schemas are generated directly from request models; no handwritten
tool-schema or parser layer exists. Game tools obtain
the owner ID from the calling Hermes `task_id`, so the ID is deliberately not
part of their argument schema. `toqraq_game_start` consequently uses
`{project_dir, engine?, version?}` while HTTP adds the host-owned
`hermes_session` field to the same start command.

The manifest and runtime registry expose exactly these seventeen tools:

| Tool | Request model | Owner |
| --- | --- | --- |
| `toqraq_project_setup` | `SetupRequest` | no game owner required |
| `toqraq_game_start` | `GameStartRequest` | caller `task_id` |
| `toqraq_game_stop` | empty | caller `task_id` |
| `toqraq_game_pause` | empty | caller `task_id` |
| `toqraq_game_resume` | empty | caller `task_id` |
| `toqraq_game_step` | `StepFramesRequest` | caller `task_id` |
| `toqraq_game_read_hierarchy` | `HierarchyReadParams` | caller `task_id` |
| `toqraq_game_read_objects` | `ObjectReadParams` | caller `task_id` |
| `toqraq_game_read_diagnostics` | `DiagnosticsReadParams` | caller `task_id` |
| `toqraq_game_read_process_output` | empty | caller `task_id` |
| `toqraq_game_read_metrics` | `MetricsReadParams` | caller `task_id` |
| `toqraq_game_capture_frame` | `FrameCaptureParams` | caller `task_id` |
| `toqraq_game_input_semantic` | `SemanticInputParams` | caller `task_id` |
| `toqraq_game_input_keyboard` | `KeyboardInputParams` | caller `task_id` |
| `toqraq_game_input_pointer` | `PointerInputParams` | caller `task_id` |
| `toqraq_game_input_text` | `TextInputParams` | caller `task_id` |
| `toqraq_game_input_gamepad` | `GamepadInputParams` | caller `task_id` |

Every handler returns one compact JSON string containing the same successful
DTO or public error object as HTTP. Tools never receive a different game ID,
native window handle, executable path, Bridge request ID, or transport choice.
Conformance tests pair every tool with its mounted HTTP operation and prove the
same focused service method, validated command contract, result contract, and
safe error envelope; REST-only component, preview, workspace, list, and event
operations remain explicitly outside the tool surface.

## Native preview and event endpoints

Each mounted renderer effect creates an `attachment_id`. Requests from any
other attachment ID cannot move, hide, or detach the current owner.

| Method and path | Body |
| --- | --- |
| `POST /preview/native/attach` | `{session_id, attachment_id, pane_rect}` |
| `POST /preview/native/rect` | `{session_id, attachment_id, pane_rect}` |
| `POST /preview/native/visible` | `{session_id, attachment_id, visible}` |
| `POST /preview/native/detach` | `{session_id, attachment_id}` |
| `WS /sessions/{session_id}/events` | path owner is the active Hermes session |

`pane_rect` uses screen-absolute physical pixels. Width and height are positive
integers at most 32768; coordinates are bounded to +/-1000000. The display
service derives the host point and the aspect-fit destination from the current
session's authoritative preview viewport while holding that session's
operation gate. Callers cannot submit a fitted destination rectangle.

The event socket sends only events owned by its path session, using one strict,
immutable envelope. Sequence starts at one
for a Hermes session and remains monotonic across game stop/restart until that
Hermes session is finalized. `timestamp` is Unix time in seconds.

```json
{
  "session_id": "hermes-session-id",
  "sequence": 4,
  "timestamp": 1785852000.25,
  "type": "session.process_state",
  "payload": {
    "id": "hermes-session-id",
    "run_revision": 7,
    "runtime": {
      "engine": "godot",
      "version": "4.7.1-stable",
      "build_id": "toqraq.windows.x86_64.release",
      "distribution_id": "toqraq",
      "platform": "windows",
      "architecture": "x86_64"
    },
    "project_dir": "D:/game",
    "root_pid": 1234,
    "process_state": "paused",
    "alive": true,
    "exit_code": null,
    "started_at": 1785852000.25,
    "bridge": {
      "id": "toqraq.godot.bridge",
      "protocol": "1.0",
      "capabilities": ["toqraq.play.pause"]
    },
    "capabilities": ["toqraq.play.pause", "toqraq.preview.display"],
    "preview": {
      "state": "ready",
      "error": null,
      "surface": {
        "kind": "native_window",
        "viewport_size": {"width": 1280, "height": 720}
      }
    },
    "perception": {"state": "ready", "error": null},
    "control": {"state": "ready", "error": null}
  }
}
```

Topics are `session.started`, `session.readiness`, `session.process_state`,
`session.stopped`, and `session.failed`. A
`session.failed` payload contains `{session, error}` and reuses the same public
error object returned by HTTP and Hermes tools. Every other payload is the
exact shared session result DTO. Events accelerate updates; after the first
frame, reconnect, malformed frame, or sequence gap, Desktop reads
`GET /sessions/{session_id}` for truth.

## Errors

Expected failures, request validation failures, and unexpected boundary
failures use one Pydantic-owned envelope across HTTP and Hermes tools:

```json
{
  "error": {
    "code": "session.not_found",
    "category": "not_found",
    "parameters": {"session_id": "hermes-session-id"},
    "details": {"reason": "not_owned"},
    "trace_id": "8f489b96-c438-4d13-a54d-9e3f1020f531"
  }
}
```

The envelope never contains a backend message, exception cause, traceback, or
unreviewed exception data. Hermes Desktop derives `errors.<code>`, localizes
the message, and shows the trace ID. Category alone determines HTTP status:

| Category | Status |
| --- | --- |
| `invalid` | 400 |
| `unauthenticated` | 401 |
| `forbidden` | 403 |
| `not_found` | 404 |
| `conflict` | 409 |
| `unavailable` | 424 |
| `timeout` | 504 |
| `upstream` | 502 |
| `internal` | 500 |

Hermes tool handlers serialize the identical `error` object as a JSON string.
Expected and unexpected failures do not cross the tool boundary; cancellation
continues to propagate to its owner.
