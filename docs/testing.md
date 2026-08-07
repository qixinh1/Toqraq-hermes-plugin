# Testing and Verification

This document defines the verification matrix for the architecture in
[architecture.md](architecture.md). A change is not complete when it merely
runs locally; it is complete when the smallest relevant layers below prove its
success, failure, cancellation, cleanup, and user-visible behavior.

## Principles

- Test public behavior and invariants, not private implementation arrangement.
- Keep pure logic deterministic and independent of Hermes, engines, networks,
  desktops, and wall-clock timing.
- Cross every real boundary in at least one integration suite.
- Every supported engine/version/platform passes the same baseline
  conformance suite.
- A bug fix starts with a failing regression test at the lowest layer that can
  reproduce the bug.
- Deleting behavior deletes tests that protect only that behavior.
- Tests do not preserve aliases, alternate contracts, or unused designs.
- No test passes by relying on a developer's installed engine, provider,
  credential, cache, locale, or global Hermes state.

## Test layers

### Architecture gates

Static tests run on every change and enforce:

- allowed dependency direction between core, contracts, services, presenters,
  engines, components, and platforms;
- no engine package importing another engine package;
- concrete adapters imported only by the composition root and their owning
  packages;
- explicit in-memory engine/component catalog registration with no runtime record loader;
- no handwritten source or test file over 500 physical lines;
- no imports outside the allowed Hermes Desktop ESM closure;
- mounted REST/tool service, request, result, error, and generated contract parity;
- plugin, Desktop entry, catalog, and package identity parity;
- i18n key and interpolation parity;
- documentation links and declared command paths resolve;
- generated and built artifacts match their source inputs.

Architecture tests parse source or structured manifests. They do not depend on
fragile text formatting when an AST or parser is available.

### Pure unit tests

Pure tests cover values and policies without I/O:

- engine and capability identifiers;
- runtime selection and exact identity;
- session state transitions, feature readiness, and 64-slot lifecycle capacity;
- project-marker and version parsing;
- geometry and aspect-fit policy;
- input normalization and bounds;
- hierarchy, object, diagnostic, and event pagination;
- command-line argument construction;
- checksum and component-manifest validation;
- archive path and size policy;
- image and media metadata bounds;
- protocol encoding, decoding, framing, and schema conversion;
- error classification and public-envelope conversion;
- context-capsule selection and size limits.

Use table-driven tests for vocabularies and boundary values. Use
property-based or fuzz tests where hostile combinations are broader than a
small example table, especially codecs, archives, paths, and bridge frames.

### Contract tests

Pydantic contracts are the single boundary source. Contract tests prove:

- valid requests convert to exact core commands;
- unknown, missing, null, wrong-type, oversized, and cross-field-invalid input
  is rejected;
- generated Hermes tool schemas match the runtime parser;
- FastAPI uses the same request and result models;
- HTTP and Tool errors have the same error object;
- unexpected failures log a trace ID, exception type, and bounded frame
  locations without logging exception arguments, arbitrary messages, locals,
  secrets, or paths;
- events have session ID, sequence, timestamp, type, and bounded payload;
- opaque references remain opaque through every presenter;
- large results require limit/cursor/revision and never default to unbounded
  output;
- binary media never enters retained state JSON; a one-shot frame result may
  use canonical bounded base64 with correlated length, digest, PNG header,
  dimensions, and original request ceilings.

Engine bridge schemas are separately tested because the engine process is an
untrusted boundary.

### Service tests

Services use fake ports with real core values. Cover at least:

- project detection with zero, one, and ambiguous matches;
- workspace context replacement clearing before a probe, late-result and
  failed-probe settlement, unrecognized-project clearing, finalization, and disposal;
- Desktop workspace projection rejecting empty and relative transient host
  values while accepting absolute Windows, UNC, and POSIX roots;
- plugin-lifetime workspace synchronization without rendering the preview pane,
  including task, workspace, gateway, stale response, and disposal changes;
- a registered project format with an empty engine catalog preserving detected
  project facts, returning runtime-unavailable, and producing a stable Start
  failure without reading components or registering a placeholder contribution;
- an empty format catalog producing engine-unavailable without a probe;
- exact runtime selection flowing unchanged through prepare and launch;
- first-run component preparation;
- transactional replacement of a session's existing game;
- natural process exit and crash classification;
- pause, resume, step, restart, and every focused input and perception
  capability/readiness gate;
- session operation-gate ownership and global active/pending capacity reservation
  under concurrent starts, retry, finalization, and release;
- hierarchy, object, diagnostic, metric, frame, and input acknowledgements
  correlated with their exact originating query or command;
- bridge connecting, ready, failed, and teardown states;
- bounded public process-output tails, diagnostics, hierarchy, object, and metric reads;
- preview attach, follow, visibility, replacement, and detach ownership;
- stale attachment and socket events not mutating the current owner;
- Hermes finalization using the normal cleanup path;
- cleanup failure retaining ownership for retry;
- cancellation settling launch, publication, native mutation, and cleanup;
- plugin shutdown releasing all sessions, tasks, locks, and temporary files.

Fakes implement the same focused ports as production. Avoid mocks that merely
assert an internal call sequence unless that sequence is the ownership
contract being tested.

### Component provisioning tests

Component tests run against isolated temporary stores and controlled HTTP
fixtures. They cover:

- empty-store installation;
- exact manifest and platform/architecture selection;
- bounded and resumable download behavior;
- disk-space preflight;
- digest mismatch;
- truncated or oversized response;
- untrusted redirect or origin;
- archive traversal, absolute paths, links, device files, collisions, excess
  entries, and excess expanded size;
- cross-process install locking;
- cancellation during download and publication;
- staging cleanup;
- atomic replacement and rollback failure;
- lease-commit transfer retaining both the mutation token and lease when native
  mutation release fails;
- repair of incomplete or corrupt components;
- removal without affecting user-installed engines or another component;
- progress and error events carrying trace and operation IDs.

Unit and pull-request suites never access a live vendor release service.
Catalog and download-network smoke tests run in a scheduled, rate-limited job.

### Engine contribution conformance

Every engine contribution is tested through one shared conformance suite. Each
exact engine build offered to users must prove:

1. its project probe recognizes a minimal valid project and rejects another
   engine's project;
2. it reports a project-declared engine version when the format provides one
   and otherwise preserves its absence without inventing a value;
3. its runtime catalog lists deterministic exact releases and rejects a second
   selectable release for the same engine, public version, platform, and
   architecture;
4. setup and Start select the same catalog `RuntimeRelease` object, and
   provisioning receives that object without another lookup or substitution;
5. provisioning yields a verified `PreparedRuntime` with matching identity;
6. launch uses only that prepared runtime and starts an owned process tree;
7. cancellation or failure after each acquisition leaves the prepared runtime,
   bridge listener, process tree, output collectors, attachment tasks, and
   preview under a retryable pending-start owner;
8. registry promotion is compare-and-swap and concurrent replacement or
   finalize cannot overwrite or orphan another owner;
9. the bridge authenticates the owning Hermes session and rejects a bad token,
   engine ID, version, build identity, protocol, or capability declaration;
10. a live process is promoted independently of bridge readiness, and an
    authentication failure exposes failed features without creating ports or
    hiding the playable process;
11. feature readiness reaches a terminal ready or failed state;
12. the preview surface is located and released;
13. frame capture returns a bounded valid frame;
14. hierarchy reads are bounded and return opaque references;
15. selected objects and properties can be inspected;
16. diagnostics and process output are sequenced and bounded;
17. semantic, keyboard, pointer, text, and gamepad input follow the common
    contract; keyboard identities use the W3C baseline, one unmappable event
    rejects the whole batch before dispatch, and the accepted count equals the
    originating command before later state or frame evidence is observed;
18. pause, resume, restart, and step follow the common contract; decoded pause
    state and step count equal their exact originating command;
19. metrics are bounded and typed;
20. stop, natural exit, replacement, plugin shutdown, and Hermes finalization
    release bridge, process tree, preview, temporary data, subscriptions, and
    tasks; a Desktop stop names its observed run revision and cannot release a
    replacement owner, cannot clear a mismatched terminal response, refreshes
    the replacement after a revision conflict, and can retry retained cleanup.

An engine/version missing a mandatory baseline capability is not published in
the supported catalog. There is no reduced conformance label presented as full
support.

### Engine-native tests

Each bridge also runs tests in its native toolchain:

- Godot module unit and integration tests against a clean exact upstream tag;
- Unity EditMode and PlayMode tests for the C# package;
- Unreal automation tests for the C++ editor plugin;
- Cocos extension and preview tests in its supported TypeScript runtime.

Native tests validate main-thread dispatch, object lifetime, protocol bounds,
handshake failure, input conversion, capture, and teardown. Schema fixtures
are shared with Python so both sides prove the exact same messages.

The Godot candidate job requires an exact stable tag and full commit, composes
`engine/godot/modules` only through `custom_modules`, runs the compiled upstream
test binary and production Bridge exercise, and fails if tracked upstream files
change. Its build-only packager must produce byte-identical ZIP and provenance
for identical inputs, round-trip through the production fingerprint/extractor,
and preserve exact license bytes. Its extracted executable passes the production
Bridge exercise. Download, interruption, resume, repair, lease, and removal wait
for immutable HTTPS. The artifact remains uncertified until that source, common
real-engine, and interactive Desktop gates pass; see [godot-candidate-build.md](godot-candidate-build.md).

The focused native and production host-adapter commands are in the
[module README](../engine/godot/modules/toqraq/README.md).

### Required Hermes host integration contract

Use an isolated Hermes home to prove the public host contract:

- `hermes plugins install <owner>/<repository> --enable` installs both entries;
- enable, disable, update, and remove keep both entries consistent;
- bounded atomic journal/config replacement retries transient Windows sharing/access failures and retains persistent failures for recovery;
- the lifecycle test and its command wrapper never retry a failed package operation;
- plugin registration exposes exactly 17 tools, 2 hooks, 4 skills, and one instance disposer, matching the manifest;
- `on_session_finalize` rejects a missing or malformed host identity before ending only its matching game;
- Hermes awaits finalization cleanup rather than accepting an unowned fire-and-forget task;
- disable, update, remove, force reload, and host shutdown await the instance-scoped disposer before unregistering it;
- an injected disposer failure aborts the lifecycle transaction and leaves the old instance and its owners registered for a successful retry;
- namespaced skills resolve without copying into the global skill tree;
- every installed skill leaves parent-game control and verification with the parent because delegated children have independent task IDs;
- the asset skill claims only conditional image, opt-in video, and configured spoken-voice TTS tools;
- `pre_llm_call` selects only the exact calling task's cached live game or recognized-workspace summary and never exceeds 2,048 characters;
- tools target the calling Hermes session and cannot select another session;
- Desktop REST and socket calls remain in the plugin namespace;
- no setup path requires a repository clone, Node.js, separate Python, or preinstalled engine.

If Hermes lacks a required public installation surface, keep the test skipped
with a link to the host-contract issue. Do not add a hidden side-loading path
as the assertion's substitute.

The isolated lifecycle test uses a temporary committed local Git source. One
observed execution completed every transition; two independent executions hit
transient host transactions, at remove rollback and final install journal
publication. The built-in management path loaded no Toqraq instance or
disposer. A controlled no-delete-sharing handle reproduced host journal
replacement as Windows error 5. Stable repeated execution after a bounded host
atomic-replace retry is mandatory; rerunning the test is not a pass condition.
Electron execution, active cross-process disposal, force reload, and host
shutdown remain separate focused and interactive evidence.

### Desktop tests

`npm run typecheck` creates one no-emit Program containing every handwritten
production `.ts` and `.test.ts` file plus generated declarations and structural rules. It enables
`strict`, unchecked-index, exact-optional, isolated-module, verbatim-module,
and unused-symbol checks without `allowJs` or `checkJs`. Architecture tests
reject renderer `.js`, `.tsx`, explicit `any`, `@ts-check`, and JSDoc type
scaffolding. Relative runtime imports retain `.js`; type-only edges use `import type`.

`npm test` uses the existing esbuild dependency to compile tests and their source graph into one invocation-owned temporary directory, runs the result
through `node --test`, and removes the directory. Cases cover strict API/event decoding and localization, setup/selection/component state, plugin-lifetime
session and workspace synchronization, geometry, stale attachments, and command enablement. Session-sync cases prove readiness retry, owner switching,
sequence-gap reconciliation, late-result rejection, pane-independent state, and idempotent disposal without a second session-list poller.

### Runtime bridge transport tests

Controlled Bridge RPC tests use real loopback WebSockets and prove:

- handshake-only candidates authenticate with an empty native capability set;
- malformed and wrong-credential candidates cannot consume the launch; correct-credential identity mismatches, cancelled waiters, concurrent candidates, and repeated claims observe one terminal result without secret retention;
- one reader correlates out-of-order success and safe error responses by exact
  monotonic host IDs;
- every method-specific decoder validates the response against the exact query
  or command retained by that ID, including selections, limits, budgets, pause
  state, step count, and input-event count;
- malformed, binary-without-transfer, unknown, duplicate, and late frames fail
  closed without retaining frame or technical-message text;
- ordinary work never exceeds the negotiated limit and one independent cancel
  request remains possible when that limit is one;
- caller cancellation, total deadlines, cancel grace, natural disconnect, and
  concurrent close settle each owned waiter exactly once;
- repeated state invalidations merge into one six-family dirty snapshot;
- each pending entry runs its operation-owned response correlation decoder.

### Future media admission tests

Before any media inspector or transformer enters composition, its tests use
small licensed repository fixtures and prove:

- type, size, duration, stream, frame, and pixel bounds;
- crop, resize, convert, trim, normalize, and transcode parameters;
- deterministic output for deterministic operations;
- source files remain unchanged unless an explicit visible replacement was
  requested;
- temporary and failed outputs are removed;
- FFmpeg/ffprobe and image-library failures become typed errors;
- provenance and license metadata survive transformation;
- previews and metadata are available before a destructive replacement;
- malformed and decompression-bomb inputs are rejected.

Provider generation itself is tested by Hermes/provider contract fakes. Toqraq
does not test a third-party model's creative quality as deterministic code.

### Security and resilience tests

Maintain adversarial coverage for:

- bridge authentication and replay attempts;
- loopback-only listeners and one-session ownership;
- oversized, nested, malformed, partial, and unexpected protocol frames;
- path traversal, symlink, junction, reserved-name, and case-collision input;
- malicious engine-returned paths and URLs;
- process-tree escape and cleanup;
- stale native handles;
- secret and authorization redaction;
- event floods, slow subscribers, queue overflow, and reconnect;
- request cancellation at every ownership transition;
- simultaneous install, start, replace, stop, and finalize races;
- plugin or engine crash followed by repair and restart.

Windows process tests run on Windows 10 or Windows Server 2016 or later. They
create a real root and grandchild and prove both belong to the exact session
Job Object before user code can report readiness. Separate process tests kill
the helper and the Hermes-like host and prove that no descendant escapes the
process-lifetime and session jobs. They also prove every handle retained by the
main process is non-inheritable, only the remote `HANDLE_LIST` values reach the
child, and the exact `SYSTEMROOT`/managed-`APPDATA` allowlist excludes a parent
environment sentinel. A concurrent unrelated child cannot read the bootstrap pipe, while the intended child reads
the exact 4 KiB boundary through standard input and observes EOF.

Fault seams cover helper creation, lifetime-job creation, local pipe creation,
remote duplication, parent/handle/job attribute construction, process
creation, remote-lease closure, output ownership transfer, and every native
release. Every failure rolls back all ownership acquired so far. A persistent
rollback-release fault stays owned by the launcher and is released by a later
close retry before another launch is accepted. Output tests prove global
sequence order, both streams, bounded storage, explicit truncation, and that a
reader failure closes the unread pipe instead of allowing a child to block.
They also prove that cleanup drains both pipes to EOF after every writer has
ended, including output buffered behind a long polling interval, while cleanup
aborts boundedly when a writer may still be alive. A drain deadline retains the
output owner for an idempotent retry and never reports an unread tail as a
successful close.
Window-close tests prove enumeration callbacks only collect bounded candidates
and each post is preceded by current `IsProcessInJob` membership and a PID
recheck. Repeated close is a no-op after success and a retry after a retained
native cleanup failure. Process helpers wait for valid PID-file contents rather
than treating file creation as publication.

Security bounds are tested at the limit, immediately below it, and immediately
above it.

## Determinism and time

- Unit tests do not use the real clock, random generator, network, home
  directory, or process environment without an injected boundary.
- Randomized tests record the seed on failure.
- Async tests coordinate with events and controllable futures, not fixed
  sleeps.
- Polling code accepts an injected interval and deadline source in tests.
- Temporary paths are provided by the test framework and remain inside the
  test root.
- Tests restore environment, registries, locale, and module-level host state.
- A test may not depend on execution order.

## Fixtures

Keep fixtures minimal and purpose-specific:

- one minimal valid project per engine;
- one cross-engine ambiguous workspace fixture;
- one instrumented gameplay fixture exercising the baseline capabilities;
- bounded valid and malicious bridge frames;
- small image, audio, and video fixtures with documented licenses;
- component manifests and archives generated during tests where practical.

Do not commit full engine binaries, generated caches, credentials, or large
media merely to simplify a test.

## CI matrix

### Pull requests

Every pull request runs:

- formatting, linting, and strict type checks;
- architecture and 500-line gates;
- pure unit, contract, service, component, security, and Desktop unit tests;
- generated contract, i18n, and bundle drift checks;
- native bridge compile/unit tests for changed engine packages;
- one baseline real-engine smoke test for every changed engine contribution
  when the required runner is available.

### Scheduled verification

Scheduled jobs run:

- every supported engine/version conformance suite;
- certified component URL, provenance-reference, and download smoke tests;
- repeated install/repair/remove cycles;
- session and preview soak tests;
- fuzz corpora and race-heavy suites;
- all required Desktop locales and preview layouts.

### Release gate

A distributable plugin release proves:

- installation into an empty Hermes home through the standard command;
- no engine or media component preinstalled;
- Desktop and Python plugin surfaces load together;
- on-demand component installation, cancellation, repair, and reuse;
- one complete Perceive and Develop flow for every offered engine/version;
- real preview resize and session finalization cleanup;
- notices, component manifests, licenses, and digests are present;
- no skipped mandatory conformance test.

Publishing-game workflows are outside the current product scope and are not a
release gate yet.

## Interactive verification

The complete human-operated matrix, evidence record, and pass decision live in
[interactive-testing.md](interactive-testing.md). Interactive evidence neither
replaces automated gates nor turns a local candidate into a support claim.

## Test organization

- Test directories mirror production responsibilities.
- Test names state the invariant or outcome, not the implementation method.
- One test proves one behavioral reason for failure.
- Shared helpers remain narrow; there is no general test utilities bucket.
- A fake lives beside the tests that own its contract unless several test
  packages genuinely share the same port semantics.
- Every handwritten test file is subject to the 500-line gate.
- Integration markers state the exact external requirements.

## Required commands

Install the hash-pinned Python closure and paired Hermes Desktop dependencies
first. Set `TOQRAQ_HERMES_SOURCE` to that checkout; renderer type checking
reuses its TypeScript compiler, React declarations, and public SDK mapping.

```powershell
python -m pip install --disable-pip-version-check --only-binary=:all: --require-hashes --requirement requirements-dev.txt
$env:TOQRAQ_HERMES_SOURCE = "C:\path\to\hermes-agent"
python -m ruff check toqraq dashboard tests scripts __init__.py
python -m ruff format --check toqraq dashboard tests scripts __init__.py
python -m mypy
python -m pytest
python -m scripts.generate_contracts --check
npm run typecheck
npm test
npm run build
```

Real-engine and Desktop suites are additional explicit jobs; passing only the unit baseline is not sufficient for a release.

Run the isolated standard-plugin lifecycle against the same source tree:

```powershell
python -m pytest -m hermes_integration
```

The suite creates a committed local source and temporary `HERMES_HOME`. Current
paired-host evidence is one complete pass and two transient host transaction
failures. Do not add command, test, or CI reruns. The gate requires the bounded
host atomic-replace fix, stable repeated passes, and then a clean published
host and repository in an empty profile.

## Completion rule

A task may be called complete only when:

- the relevant automated layers pass;
- no mandatory check is skipped without a recorded host or runner blocker;
- new failure, cancellation, and cleanup paths are tested;
- user-visible behavior is verified in Hermes Desktop when it changed;
- generated artifacts are current;
- unused code and tests are removed;
- the final report names the tests run and any intentionally unrun external
  suite.
