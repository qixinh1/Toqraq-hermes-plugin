# Engine Bridge Contract

This document defines the implemented process boundary shared by complete
engine contributions. It is a transport and ownership contract, not a
universal engine object model. The Godot candidate module and production
Python listener use this contract directly; no other engine is admitted yet.

## Purpose and boundary

The bridge lets one running engine process expose the focused Perceive and
Develop ports declared in [engine-adapters.md](engine-adapters.md). It carries
only runtime facts and commands that require engine-native access. Project file
editing, shell commands, Git, artifacts, model calls, component installation,
preview placement, and process ownership remain outside this protocol.

One bridge connection belongs to one internal game-run revision within one
Hermes session. It cannot select another session, project, engine, runtime, or
component. Public object references are opaque and valid only for that run.

## Transport

The common transport is JSON-RPC 2.0 over a loopback WebSocket. One
`PendingStart` owns an ephemeral listener in the same process as the Toqraq
service graph; it binds `127.0.0.1` with an operating-system-selected port and
passes that non-secret endpoint only to the process it launches. The engine
bridge is the client. This is a session resource, not a Dashboard route,
separate daemon, shared gateway listener, or discoverable service.
The endpoint is exactly `ws://127.0.0.1:<port>/toqraq/bridge` and can be passed
unchanged to an engine-native WebSocket client.

- bind only to an explicit loopback address;
- permit one authenticated connection for the run;
- reject non-WebSocket requests and browser origins before application
  dispatch; an engine-native client is expected to omit `Origin`;
- accept text frames only for bounded UTF-8 JSON-RPC messages;
- accept binary frames only for a transfer announced by a valid response;
- disable WebSocket compression so compressed input cannot bypass byte limits;
- enforce connection, message, request, response, transfer, and timeout bounds
  independently;
- stop accepting connections after successful authentication;
- close the socket, listener, and every pending waiter when its session owner
  closes.

The Python endpoint uses Hermes' exact `websockets` runtime dependency with
compression and server identification disabled and explicit handshake, queue,
message, write-buffer, ping, and close bounds. Toqraq never installs a Python
package into Hermes at plugin runtime. Failure to import the host-provided
dependency is an actionable plugin-readiness failure before engine launch.
After authentication, one controlled connection owns the sole frame reader,
request registry, merged invalidation state, and socket. No service receives
the raw WebSocket object.

The bridge protocol version is exact. A bridge accepts only that version. A
protocol change ships with the native bridge, Python contracts, certified
runtime record, conformance fixtures, and plugin update that selects it.

## Credential delivery

Each pending start creates a cryptographically random single-use credential.
The credential never appears in a URL, command line, project file, Desktop
storage, event, log, error detail, artifact, or model context.

On Windows it is encoded in the launch's representation-redacted bootstrap
bytes, bounded to 4 KiB. Before process creation the launcher writes the entire
value to a non-inheritable anonymous pipe and closes the writer. It duplicates
only the read end into the dedicated helper and supplies that remote handle as
the child's standard input through the restricted handle list. The main
process closes its local read end before user code executes. The engine reads
to EOF once and closes standard input; an unrelated concurrent Hermes child
cannot inherit the channel. Other platforms use an equivalent one-shot secret
channel owned by their process-tree adapter.

The host only encodes this one-way value. The engine-native parser owns
decoding and rejection; its native contract suite and the real launch exercise
prove parity with the host encoder. Python does not decode its own launch
output as a substitute for that boundary evidence.

Possession of the credential is necessary but insufficient. The handshake must
also match every expected runtime and owner fact.

## Handshake

The engine's first application message is a `toqraq.handshake` JSON-RPC request.
No other method, notification, or binary frame is accepted first.

The request contains:

- the single-use credential;
- Hermes session ID and internal run revision;
- engine ID, public version, build ID, distribution ID, platform, and
  architecture copied from the launched `RuntimeRelease`;
- bridge ID and exact protocol copied from that release;
- the complete native RPC capability ID set implemented by this process;
- bounded engine-native limits required by the common contracts.

The exact request parameters are:

| Field | Contract |
| --- | --- |
| `credential` | 32 random bytes encoded as exactly 64 lowercase hexadecimal characters |
| `session_id` | owning Hermes session ID, 1 to 512 UTF-8 bytes with no control characters |
| `run_revision` | positive run-scoped integer no greater than JavaScript's exact integer maximum |
| `engine_id` | validated engine ID |
| `engine_version` | exact bounded runtime version copied from `RuntimeIdentity` |
| `build_id` | exact bounded build ID copied from `RuntimeIdentity` |
| `distribution_id` | exact validated distribution ID copied from `RuntimeIdentity` |
| `platform` | exact validated platform copied from `RuntimeIdentity` |
| `architecture` | exact validated architecture copied from `RuntimeIdentity` |
| `bridge_id` | validated namespaced bridge implementation ID |
| `protocol` | exact bounded bridge protocol copied from `RuntimeRelease` |
| `capabilities` | zero to 64 unique validated native RPC capability IDs |
| `limits` | the exact bounded limit object below |

The initial limit object contains only limits needed before feature ports are
created:

| Field | Range |
| --- | --- |
| `max_text_message_bytes` | 4,096 through 262,144 bytes |
| `max_binary_transfer_bytes` | 1 through 67,108,864 bytes |
| `max_in_flight_requests` | 1 through 64 requests |

The listener supplies its own values for the same object. Each effective limit
is the lower of the engine and listener values. Operation schemas retain their
own stricter bounds; the handshake does not turn protocol maxima into engine
configuration.

The listener first decodes the complete offer, then compares its credential in
constant time with the immutable expectation. It does not infer identity from
an executable path, process name, package label, or connection address. The
native capability set must equal the bridge set in the certified release; a
missing or undeclared extra capability is a mismatch.
It is distinct from the release's complete contribution capability set, which
also contains host-owned project, preparation, lifecycle, and preview features.
An empty set is valid only as an exact handshake-only candidate fact and creates
no feature port; such a candidate is never exposed as a supported release.

The success result returns only the accepted owner key, protocol, capability set, and effective limits. The owner key is the exact `session_id` plus `run_revision`.
It is an identity, not another credential. The credential is invalidated before success is sent.

An undecodable frame or wrong credential is untrusted: reject only that candidate and remain available. It cannot consume the credential, owner, or readiness publication.
A fully decoded offer with the correct credential has proved this launch's secret. Any later owner, runtime, bridge, protocol, or capability mismatch consumes the
credential, stops acceptance, returns the same safe mismatch response, and immediately settles feature readiness with `bridge.unavailable`; another candidate cannot
legitimately represent that launch. The terminal application error retains only the wire error's stable code, category, field, and trace ID, never compared values or credentials.
Second handshakes, concurrent losers, timeouts, and malformed first messages close their candidate with a policy violation and create no feature port.

Authentication controls feature readiness, not process ownership. Once a live
process tree has been promoted through the session registry, handshake failure
sets bridge-dependent features to `failed`; it does not hide or terminate an
otherwise playable process. Explicit stop, replacement, exit, or finalization
still closes the complete run.

## JSON-RPC envelope

Requests use a bounded opaque string `id`, exact method name, and object
`params`. Notifications omit `id`. Responses contain exactly one of `result`
or `error`. Duplicate object keys, non-finite numbers, invalid Unicode, unknown
top-level members, batch requests, and numeric request IDs are rejected.

The engine-authored handshake ID contains 1 to 128 ASCII letters, digits, `.`,
`_`, `:`, or `-` and begins with a letter or digit. Every post-authentication
request and response ID is host-owned, has exact form `host-<positive decimal>`,
has no leading zero, and is no greater than JavaScript's exact integer maximum.
A text message is at most 262,144 UTF-8 bytes, has at most 4,096 JSON values,
has at most 256 members in one collection, and has a maximum nesting depth of
16. These pre-dispatch limits apply before the more specific Pydantic schema.

The handshake request and success response have these exact JSON-RPC shapes:

```json
{
  "jsonrpc": "2.0",
  "id": "request-1",
  "method": "toqraq.handshake",
  "params": {
    "credential": "<64 lowercase hexadecimal characters>",
    "session_id": "<Hermes session ID>",
    "run_revision": 1,
    "engine_id": "godot",
    "engine_version": "<exact version>",
    "build_id": "<exact build>",
    "distribution_id": "<exact distribution>",
    "platform": "windows",
    "architecture": "x86_64",
    "bridge_id": "toqraq.godot.bridge",
    "protocol": "1.0",
    "capabilities": ["<implemented native RPC capability ID>"],
    "limits": {
      "max_text_message_bytes": 262144,
      "max_binary_transfer_bytes": 33554432,
      "max_in_flight_requests": 16
    }
  }
}
```

```json
{
  "jsonrpc": "2.0",
  "id": "request-1",
  "result": {
    "owner": {"session_id": "<Hermes session ID>", "run_revision": 1},
    "protocol": "1.0",
    "capabilities": ["<accepted native RPC capability ID>"],
    "limits": {
      "max_text_message_bytes": 262144,
      "max_binary_transfer_bytes": 33554432,
      "max_in_flight_requests": 16
    }
  }
}
```

The listener decodes the first message and passes its typed offer directly to
the pure core handshake validator. Those boundaries use stable failures and
never echo the rejected value:

| JSON-RPC code | Stable data code | Meaning |
| --- | --- | --- |
| `-32700` | `bridge.json_invalid` | invalid JSON, duplicate key, non-finite number, or invalid Unicode |
| `-32600` | `bridge.request_invalid` | invalid JSON-RPC envelope, batch, or aggregate JSON bound |
| `-32601` | `bridge.method_not_found` | a valid first request names a method other than `toqraq.handshake` |
| `-32602` | `bridge.params_invalid` | handshake parameters violate their schema |
| `-32001` | `bridge.handshake_mismatch` | a valid offer differs from the expected credential, owner, runtime, bridge, protocol, or capability set |
| `-32002` | `bridge.message_too_large` | the UTF-8 text frame exceeds its pre-parse byte limit |

Post-authentication error responses accept only `-32601`, `-32602`, `-32603`,
or `-32000`. Their bounded `data` is the shared public error value. Another
number, an unknown field, an invalid result shape, or an unknown response ID
is a connection-level protocol failure; native technical `message` text is
validated but never logged or propagated.

The JSON-RPC number and public error classification are one exact pair:

| JSON-RPC code | Required public error classification |
| --- | --- |
| `-32601` | code `bridge.method_not_found`, category `invalid` |
| `-32602` | code `bridge.params_invalid`, category `invalid` |
| `-32603` | code `bridge.remote_internal`, category `internal` |
| `-32800` | code `request.cancelled`, category `conflict`, empty fields |
| `-32000` | a non-`internal` application failure that does not use a reserved code above |

The internal `BridgeRemoteError` retains frozen fields and separate traces, not
technical prose. Allowed `-32000` code/category mappings are
`perception.capability_unavailable`/`unavailable` for all methods,
`perception.stale`/`conflict` for reads, `perception.object_not_found`/`not_found`
for hierarchy/object, `perception.frame_unavailable`/`unavailable` for capture,
`simulation.invalid_state`/`conflict` for pause/step, and
`input.rejected`/`conflict` for input. Other pairs, method/params errors fail the
protocol; remote internal maps to local Bridge unavailable. Bounded fields may
copy, but a remote trace never becomes local.

An error uses a request ID only after envelope validation, else `null`.
`error.data` is the bounded public error value; fixed JSON-RPC `message` text is
technical and never shown as localized Desktop prose.

The bridge implements only these protocol operations:

| Method | Direction | Focused port |
| --- | --- | --- |
| `toqraq.handshake` | engine to host | authenticated connection |
| `toqraq.hierarchy.read` | host to engine | `HierarchyReader` |
| `toqraq.object.read` | host to engine | `ObjectReader` |
| `toqraq.diagnostics.read` | host to engine | `DiagnosticsReader` |
| `toqraq.metrics.read` | host to engine | `MetricsReader` |
| `toqraq.frame.capture` | host to engine | `FrameCapture` |
| `toqraq.simulation.set_paused` | host to engine | `SimulationController` |
| `toqraq.simulation.step` | host to engine | `SimulationController` |
| `toqraq.input.semantic` | host to engine | `InputController` |
| `toqraq.input.keyboard` | host to engine | `InputController` |
| `toqraq.input.pointer` | host to engine | `InputController` |
| `toqraq.input.text` | host to engine | `InputController` |
| `toqraq.input.gamepad` | host to engine | `InputController` |
| `toqraq.request.cancel` | host to engine | owned cancellation |
| `toqraq.state.changed` | engine to host | revision invalidation |

There is no generic `execute`, arbitrary engine method call, unrestricted
property mutation, script evaluation, filesystem operation, shell operation,
or protocol-level restart. Restart is a session use case that replaces the
owned process tree.

Unknown optional engine behavior uses a reviewed namespaced method paired with
a namespaced capability and typed engine-owned schema. It is not added to the
mandatory baseline and cannot change common service behavior.

## Revisions and object references

Hierarchy, object, diagnostics, and metrics results carry their own monotonic
run-scoped revision or sequence. `toqraq.state.changed` announces only the
families whose authoritative revision changed; it does not push a tree, object,
log batch, frame, or arbitrary payload.

The notification has exactly `jsonrpc`, method `toqraq.state.changed`, and
params containing one unique non-empty tuple selected from `hierarchy`,
`objects`, `diagnostics`, `metrics`, `frame`, and `simulation`. The controlled
connection merges notifications into a six-family dirty set. A subscriber
takes and clears one immutable snapshot, so repeated invalidations remain
bounded and cannot overflow a notification FIFO.

An opaque object reference:

- contains no user-visible engine path or pointer promise;
- is bounded and validated before lookup;
- is scoped to the authenticated owner key;
- becomes stale when the engine reports the relevant lifetime boundary;
- cannot be supplied to another run or engine;
- never authorizes an operation not exposed by a focused method.

A stale revision, cursor, or object reference returns a typed application error
and the current revision when safe. The host never combines pages from two
revisions.

## Input and simulation

`SimulationController` owns two immediate commands. `set_paused` sets the
desired Boolean state rather than toggling it, so repetition is safe; its
acknowledgement reports the resulting state, whether this request changed it,
and the current simulation and frame revisions. `step` accepts 1 through 120
frames, succeeds only while paused, leaves the game paused, and reports the
exact advanced count plus the final revisions. Neither result repeats the
method as a `kind` field. Its per-request decoder captures the original command
and rejects a pause-state or frame-count mismatch as an invalid response.

`InputController` exposes five separate methods rather than a generic event
or execute escape hatch. Every collection is an immutable ordered batch of 1
through 128 events. Validation is atomic: the complete batch is accepted or
rejected before dispatch. This does not promise rollback after engine-thread
execution begins. Success contains only `accepted_event_count`, which must equal
the original command's event count; the per-request decoder captures that
command and enforces the correlation.

| Input | Exact common value and hard bound |
| --- | --- |
| semantic | project action up to 256 UTF-8 bytes, explicit press state, normalized strength 0 through 1 |
| keyboard | required physical code from Toqraq's cross-engine subset of W3C 2025 `KeyboardEvent.code`; optional W3C named key or NFC logical-key string; location, unique modifiers, press and repeat state |
| pointer | mouse, pen, or touch ID 0 through 31; pixel or normalized viewport coordinates; typed motion, button, and wheel events |
| text | one non-empty UTF-8 commit up to 4,096 bytes with no null character |
| gamepad | device slot 0 through 15 and typed standard-layout button or axis events with normalized values |

Pixel coordinates and deltas are finite and bounded to magnitude 1,000,000;
the native adapter additionally rejects positions outside the current live
viewport rather than clamping them. Normalized positions are 0 through 1 and
normalized motion deltas are -1 through 1. Wheel deltas are finite, non-zero
as a pair, and bounded to magnitude 10,000. Input encodes immediate ordered
state transitions. A timed hold or play sequence is an owning application use
case that sends explicit transitions; the bridge creates no hidden timer task.

Text is data for the engine's focused text surface and is never executable
source. No input value can name an engine callback, method, script, object, or
another run. Physical code and logical key may coexist; the active keyboard
layout determines their relationship. IME and printable text entry use
`toqraq.input.text`, not synthetic key labels.

An input acknowledgement is dispatch evidence, not gameplay-effect evidence.
The harness verifies effects through `input -> step/wait -> authoritative
read/capture`; it never infers state changes from removed revision fields.

The native bridge validates off the engine thread and dispatches object access,
input, capture, and simulation changes onto the engine-approved thread. Socket
callbacks never mutate game state directly.

## Reads and bounds

Every potentially growing read requires an explicit limit and selection:

- hierarchy: root reference, depth, filters, revision, cursor, entry limit;
- object: references, selected field groups, per-value and total byte limits;
- diagnostics: source, severity, sequence cursor, record limit;
- metrics: selected groups or names and sample limit;
- capture: maximum dimensions, `native` or contain scaling, and maximum bytes.

The native endpoint applies protocol maxima before engine work. The host applies
the same or stricter limits when decoding results. Truncation is explicit and
returns counts plus a continuation cursor where the source is pageable.

Engine-native extension fields live under the engine's namespace and have
their own typed bounds. They do not permit arbitrary recursive engine values,
reflection graphs, object pointers, components, or JavaScript objects.

The exact common DTO shapes and value limits are owned by
[bridge-values.md](bridge-values.md).

## Binary transfers

JSON never contains base64 media. Capture announces a random 128-bit lowercase
hex ID, PNG facts, payload length, SHA-256, and revision. The next WebSocket
binary message is exactly the same ID as 16 raw bytes plus that PNG payload;
the announcement length counts only PNG bytes. The shared transport ceiling is
the larger of the text ceiling and negotiated binary ceiling plus 16; the text
codec still enforces its independent negotiated limit.

The receiver rejects a binary message when no transfer is pending, the ID is
unknown, length exceeds the announcement or negotiated maximum, another text
message interleaves, the digest differs, or the transfer misses its deadline.
Only one transfer is pending per connection. The host converts validated bytes
to a session-owned artifact or bounded capture value and never places them in
an event or model context automatically. `toqraq.frame.capture` completes only
after the JSON announcement and its immediately following, strictly bound
binary frame both pass full validation.

The registered request and announcement share one deadline through JSON, binary,
hash, PNG, and query validation. Cancellation, interleaving, timeout, or
disconnect fails closed; validation clears ownership and transfers success once.

## Cancellation and concurrency

The host owns each request and its deadline. `toqraq.request.cancel` identifies
one outstanding request on the same connection. Cancellation is idempotent and
cannot target a request from another run.

Host request IDs are `host-<positive decimal>`, remain within the cross-language
exact integer range, and are never reused. A single reader correlates responses;
unknown, duplicate, and late IDs fail closed. Native implementations need only
the highest seen sequence plus their bounded active map; they retain no
unbounded completed-ID tombstone set.
The negotiated `max_in_flight_requests` bounds ordinary work. One additional
slot exists only for `toqraq.request.cancel`, so total pending requests never
exceed the negotiated work limit plus one, including when the work limit is
one.

The cancellation request has its own JSON-RPC ID and names a different target
request ID using the exact same bounded syntax. That pending ID already binds
the operation to its target, so the acknowledgement result contains only
`requested`, `already_terminal`, or `not_found`; it does not echo the target or
repeat a result kind. `requested` means only that the owning registry delivered
the signal; the original request still owns its waiter until its own terminal
result or cancellation error. Repeating cancellation never dispatches target
work again.

Every work request has one total deadline. Caller cancellation requests
control immediately but leaves the original registry owner until its terminal
response or total deadline. Work timeout releases that owner at its deadline,
then sends one cancellation request. Control-slot acquisition and cancellation
acknowledgement share a separate short cleanup grace. Missing that grace means
the connection can no longer control its work and fails closed, completing all
waiters once. A cancellation acknowledgement never waits for target work.

The engine checks cancellation before work and at bounded chunks. It returns the
committed result or `-32800` with `request.cancelled`, `conflict`, and empty
parameters/details. After host cancellation this terminal is valid for every
work method and uses no capability ID. The host retains the waiter until terminal, close, or
deadline; late/duplicate IDs fail closed and IDs are never reused.

The connection has bounded in-flight requests and one binary transfer. Native
main-thread work uses a bounded queue with backpressure; it is never an
unbounded callback list.

## Errors

JSON-RPC standard errors cover parse, envelope, method, parameters, and internal
dispatch failure. Expected bridge failures include a stable namespaced code in
bounded `error.data`, safe parameters/details, and the request trace ID. Native
exception text, stack traces, paths, credentials, environment values, pointers,
and large engine output never enter an error response.

The Python boundary validates and translates one bridge failure into the
shared Toqraq error system. Desktop localization happens only after that
translation. Engine-authored diagnostics remain bounded source records and are
not treated as localized application errors.

## Close and ownership

The active session owns the authenticated connection, request registry,
native feature ports, subscribers, binary transfer, and attachment tasks.
Closing is idempotent and follows this order:

1. reject new requests and cancel queued engine work;
2. close subscribers and complete every waiter with one terminal failure;
3. cancel or drain the binary transfer;
4. close the WebSocket and listener registration;
5. release feature-port and native bridge resources;
6. allow process-tree cleanup to finish before runtime leases are released.

Natural exit, explicit stop, replacement, failed start, Hermes finalization,
and plugin disposal call the same owner cleanup. A close failure keeps the
resource attached to its exact owner for retry. An old run revision cannot
close, publish, or satisfy a waiter belonging to its replacement.

## Conformance evidence

The shared fixture suite is executed against every certified engine build. It
proves:

- exact handshake success and rejection of each mismatched field;
- first-message, duplicate-connection, credential reuse, timeout, and frame
  bounds;
- every mandatory method's valid, invalid, cancelled, timed-out, and stale
  request behavior;
- opaque reference and revision isolation between two runs;
- main-thread dispatch and native object lifetime handling;
- bounded output, paging, truncation, and binary integrity;
- disconnect during request and transfer without waiter or artifact leaks;
- process running with failed bridge readiness;
- close, process exit, replacement, finalization, and disposer cleanup.

Schema fixtures are generated from the Python boundary models and consumed by
the native bridge tests. A component record is not certified until the exact
native build passes this suite with the common services and public presenters.
