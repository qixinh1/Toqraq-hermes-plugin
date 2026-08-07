# Toqraq Godot Bridge Module

This custom Godot module is the engine-native half of the authenticated
Toqraq bridge. It is composed with an exact unmodified upstream Godot checkout
through `custom_modules`. It uses Godot's public `WebSocketPeer` directly. It
does not expose a script class, install an autoload, or write to the game
project.

The common wire contract is [docs/bridge.md](../../../../docs/bridge.md). This
directory owns only Godot API mapping and the process-local bridge lifecycle.

## Activation and ownership

An ordinary Godot process never starts the bridge. The managed launcher must
provide both:

- `TOQRAQ_BRIDGE_URL`, exactly
  `ws://127.0.0.1:<port>/toqraq/bridge`; and
- one UTF-8 JSON bootstrap object on the child's private standard-input pipe.

The bootstrap object has exactly `credential`, `session_id`, and
`run_revision`. It is non-empty, at most 4 KiB, read once, parsed with bounded
field validation, and then cleared before the first handshake response. It is
never copied into an argument, environment variable, project file, diagnostic,
or error message.

Successful activation registers one process-lifetime idle callback. The
callback points only at static module state, so repeated Godot test setup cannot
leave an object callback behind or register duplicates. Activation creates one
bridge owner, while its first idle callback waits for a live `SceneTree` before
connecting. The owner polls and authenticates on the main thread and closes on
disconnect or module shutdown. Deinitialization first disables the callback and
then destroys the bridge.

The callback remains registered in Godot's fixed process-lifetime callback
table because that API has no removal operation. It never retains the bridge;
after deinitialization it observes the disabled static state and returns.

## Intrinsic build identity

The peer does not echo an identity supplied by the launcher. Its handshake is
constructed from facts embedded in or derived from the running binary:

- engine ID `godot` and Godot's compiled version number and status;
- required `toqraq_build_id` supplied by the candidate build;
- required `toqraq_distribution_id` supplied by the candidate build;
- compile-target platform and architecture;
- bridge ID `toqraq.godot.bridge`, protocol `1.0`, the exact implemented
  capability set, and native limits owned by this module.

`config.py` rejects missing or malformed build identity. The candidate workflow
derives one unique build ID before compilation and records the same value in
provenance. A certified component manifest binds that intrinsic identity to the
final archive digest.

## Current native boundary

- `toqraq_launch` owns exact activation, the one-shot Windows pipe read, strict
  launch data, and secret-reference clearing;
- `toqraq_identity` derives version, platform, and architecture from compiled
  facts and exposes the two validated embedded build identities;
- `toqraq_protocol` owns the exact first JSON-RPC request and bounded,
  duplicate-free handshake response validation;
- `toqraq_transport` owns `WebSocketPeer`, packet and byte bounds, deadlines,
  authentication state, ordered application delivery, and idempotent close;
- `toqraq_dispatcher` owns monotonic request IDs, work admission, cancellation,
  terminal response ordering, and coalesced state invalidation;
- the focused hierarchy, object, diagnostic, metric, frame, simulation, and
  input units map the common typed contract to public Godot APIs;
- `toqraq_observation_state` owns the six run-local revision families;
- `toqraq_diagnostic_log` owns one bounded process logger while the bridge is
  active; and
- `toqraq_module` owns the single static idle callback and bridge lifetime.

There is no script class, arbitrary object method call, generic reflection
endpoint, command executor, or project instrumentation path.

## Implemented common capabilities

The intrinsic handshake declares exactly these capabilities and methods:

| Capability | Methods |
| --- | --- |
| `toqraq.observe.hierarchy` | `toqraq.hierarchy.read` |
| `toqraq.observe.properties` | `toqraq.object.read` |
| `toqraq.observe.diagnostics` | `toqraq.diagnostics.read` |
| `toqraq.observe.performance` | `toqraq.metrics.read` |
| `toqraq.observe.frame` | `toqraq.frame.capture` |
| `toqraq.play.pause` | `toqraq.simulation.set_paused` |
| `toqraq.play.step` | `toqraq.simulation.step` |
| `toqraq.control.input` | `toqraq.input.semantic`, `toqraq.input.keyboard`, `toqraq.input.pointer`, `toqraq.input.text`, and `toqraq.input.gamepad` |

`toqraq.request.cancel` is the transport control method and is not advertised
as a gameplay capability. Input batches are decoded and mapped completely
before the first Godot event is dispatched. Hierarchy and object reads expose
run-local opaque references rather than Godot instance IDs. Frame capture
encodes the live root viewport as PNG and applies `native` or aspect-preserving
`contain` sizing. Diagnostics retain at most 512 bounded Godot log records for
the active bridge process.

Runtime mutations, tree changes, new diagnostics, and frame captures advance
only their owned observation families. Dirty families are sent through one
bounded `toqraq.state.changed` notification after terminal responses have been
queued.

## Transport limits

The native offer is part of the compiled module, not launcher configuration:

- text message: 262,144 UTF-8 bytes;
- PNG payload: 33,554,432 bytes, excluding its 16-byte transfer-ID prefix;
- ordinary requests: 16 in flight, plus one independent cancellation request;
- decoded JSON: depth 16, 4,096 nodes, and 256 items per collection; and
- cross-language integers: inclusive range
  `-9,007,199,254,740,991` through `9,007,199,254,740,991`.

JSON-RPC requests have exact keys, strictly increasing `host-N` IDs, one known
method, and method-specific exact parameter shapes. Authentication accepts the
first response packet and leaves any already queued ordered application packet
for authenticated processing. Invalid framing, bounds, identity, ordering, or
application admission closes the connection. A frame success announcement is
followed immediately by one binary packet containing the raw 16-byte transfer
ID and PNG bytes; the JSON byte length excludes the prefix.

This implementation remains a candidate contribution. It enters the offered
component catalog only after the shared real-engine, clean-install, lifecycle,
and interactive Desktop gates in
[docs/testing.md](../../../../docs/testing.md) pass. Native module tests and a
single local real-process exercise are evidence for this boundary, not that
catalog decision.

## Build

Supply the parent `modules` directory with Godot's official custom-module
option and provide the exact identity values:

```text
custom_modules=<absolute path>/engine/godot/modules
toqraq_build_id=<validated opaque build ID>
toqraq_distribution_id=toqraq.godot.windows.x86_64
```

The authoritative candidate invocation and evidence boundary are in
[docs/godot-candidate-build.md](../../../../docs/godot-candidate-build.md).

For a Windows candidate built with `tests=yes`, run the focused native suite
and the production host-adapter real-process exercise with:

```powershell
$engine = "C:\path\to\godot.windows.editor.x86_64.exe"
& $engine --test --test-case='*[Toqraq]*' --no-colors --duration
$env:TOQRAQ_GODOT_CANDIDATE_DIR = "C:\path\to\candidate"
python -m pytest tests/python/test_integration_godot_native_bridge.py -m integration -vv
```

The integration test strictly verifies the three-file candidate directory,
extracts it with the production component policy, and opens the production
listener against that exact executable. It exercises the private bootstrap,
all eight native capabilities, all five input forms, aspect-preserving PNG
capture, binary correlation, and cleanup. It skips when the candidate directory
is absent and never creates a component release or catalog registration.
