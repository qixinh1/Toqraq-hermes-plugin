# Dependency Policy

This document records how Toqraq chooses third-party code and which major
components the target architecture intends to use. `CONTRIBUTING.md` owns the
review workflow; this file owns dependency roles and selection rationale.

## Selection order

For each capability, prefer:

1. a public Hermes host capability;
2. an engine- or platform-owned API;
3. a focused, maintained open-source component;
4. a small repository-owned implementation when its protocol or invariant is
   specific to Toqraq.

Code reuse is not measured by package count. A package is justified only when
it removes more lifecycle, security, protocol, or domain complexity than it
adds.

## Admission checklist

A runtime dependency is admitted only after recording:

- its single responsibility in Toqraq;
- why Hermes, the engine, the standard library, and current dependencies do
  not already provide that responsibility;
- project activity, release cadence, ownership, and bus factor;
- license and redistribution terms;
- supported platforms and architectures;
- binary size and startup or memory impact when relevant;
- security history and update mechanism;
- whether it runs in the Hermes interpreter, bundles into Desktop ESM, or is
  an isolated managed component;
- removal or replacement cost;
- direct tests at the boundary Toqraq uses.

An unmaintained transitive tree, unclear license, abandoned binary, or package
that needs global installation is rejected.

## Chosen foundations

| Component | Role | Packaging decision |
| --- | --- | --- |
| Hermes plugin APIs | tools, hooks, lifecycle, skills, model providers, delegation | host-provided |
| Hermes Desktop SDK | pane, palette, status, query/state primitives, notifications, and i18n | host-provided external import |
| Python 3.11+ | plugin orchestration and application services | Hermes runtime |
| `asyncio` | owned concurrency, cancellation, and timeouts | Python standard library |
| FastAPI | namespaced Desktop REST and event presenters | Hermes-provided runtime dependency |
| Pydantic | boundary contracts and schema generation | Hermes-provided runtime dependency |
| `websockets` 15.0.1 | session-owned loopback engine-bridge listener and connection state machine | exact Hermes-provided runtime dependency |
| React | Desktop composition | host-provided external import |
| TypeScript | strict Desktop source and generated boundary types | development/build dependency |
| esbuild | one-file Desktop ESM build | development/build dependency |
| SCons 4.10.1 | compose the external Toqraq module into an exact Godot checkout | digest-pinned candidate-build dependency only |
| Win32 `ctypes` | native-window and Job Object platform adapter | Python standard library |
| JSON-RPC 2.0 | common request/response semantics for engine bridges | protocol, no framework runtime |
| WebSocket | loopback bridge protocol and Desktop events | protocol; `websockets`, FastAPI, and engine-native APIs own their respective transports |

FastAPI and Pydantic are used because the Hermes gateway already runs them.
FastAPI owns only the namespaced Desktop REST and event presenter. An engine
run needs a listener even when Start originates from a Hermes tool without an
HTTP request, so its `PendingStart` creates one ephemeral loopback listener
with Hermes' exact `websockets` 15.0.1 dependency. This is an in-process
session resource rather than a second web application or daemon. The plugin
does not install, upgrade, or vendor the package; absence is reported before
launch.

`websockets` was admitted for one responsibility: its maintained asyncio
implementation owns RFC 6455 framing, close handshakes, flow control, and
protocol state that repository code should not recreate. Version 15.0.1 is the
exact core Hermes pin, is pure Python, supports every Toqraq Python platform,
and is BSD-3-Clause licensed. Toqraq disables compression and the server
header, binds only IPv4 loopback, rejects browser origins, bounds all queues
and frames, and tests authentication, duplicate connections, disconnects,
timeouts, and cleanup directly. Updating or replacing it follows the Hermes
pin and reruns the complete bridge and clean-install matrices; removal deletes
only the focused listener adapter because contracts and feature ports do not
depend on the library.

SCons is Godot's official build system. The candidate workflow installs its
universal wheel from `engine/godot/build-requirements.txt` with
`--require-hashes`; it never enters the plugin package or an end-user Hermes
interpreter. Version and digest updates require a real candidate build and the
Godot conformance matrix. The compiler and SDK remain the reviewed GitHub
Windows runner toolchain. Candidate provenance currently records the runner
image/version, Python patch, and SCons version; exact compiler and Windows SDK
identity remains a component-admission evidence gate.

After linking, that workflow installs only the exact Windows/Python 3.12 wheels
generated from `engine/godot/candidate-test-requirements.in`, all with SHA-256 hashes.
Pydantic 2.13.4 and `websockets` 15.0.1 match the paired Hermes runtime;
pytest 9.1.1 and the closed transitive set run the packager, strict evidence
verifier, and real Bridge exercise. They cannot affect the already-linked
engine, are absent from the plugin package, and are reviewed again whenever a
Hermes pin, Python ABI, candidate test, or dependency digest changes.

## Contributor and CI environment

The repository's Python checks run directly from the source tree. They install
only `requirements-dev.txt`; they do not build the plugin package or install it
into either the contributor's or Hermes' interpreter. The generated file is a
universal Python 3.11+ wheel closure with an exact version and SHA-256 hashes
for every distribution. `pip` installs it with `--only-binary=:all:` and
`--require-hashes`, so CI never resolves a new package graph while executing
repository code.

| Direct requirement | Verification responsibility | License |
| --- | --- | --- |
| FastAPI 0.138.1 | build and exercise namespaced HTTP/OpenAPI presenters | MIT |
| Pydantic 2.13.4 | execute the contract source and schema generation | MIT |
| Starlette 1.3.1 | exercise directly imported request, response, and WebSocket types | BSD-3-Clause |
| `websockets` 15.0.1 | exercise the exact Hermes bridge transport | BSD-3-Clause |
| httpx 0.28.1 | drive in-process API boundary tests | BSD-3-Clause |
| PyYAML 6.0.3 | decode plugin manifests in contract tests | MIT |
| pytest 9.1.1 | collect and execute Python evidence | MIT |
| Mypy 2.3.0 | enforce the strict Python type boundary | MIT |
| Ruff 0.15.22 | enforce Python style, imports, complexity, and formatting | MIT |

The first four versions track the paired Hermes runtime because they execute
host-owned boundary types. httpx and PyYAML exist only for focused tests;
pytest, Mypy, and Ruff exist only for verification. All are active projects
with published wheels for the tested platforms. None enters the plugin or a
managed component. Removing a test-only package requires deleting its direct
use; removing a framework package requires moving that presenter or contract
responsibility back to a public Hermes boundary and regenerating all schemas.

`setuptools` 83.0.0 is the exact PEP 517 metadata backend for an intentional
package build; ordinary checks do not invoke it. `uv` 0.11.31 is used only to
regenerate the checked-in wheel closure. Regeneration is explicit:

```powershell
uv pip compile pyproject.toml --extra dev --universal --python-version 3.11 --only-binary=:all: --generate-hashes --default-index https://pypi.org/simple --output-file requirements-dev.txt
```

An update reviews the complete generated diff, installs it in clean Windows
and Linux Python 3.11 environments, and reruns the full Python matrix. A
transitive update is reviewed with the same evidence as a direct update.

Node 22 or later is the renderer verification runtime. esbuild 0.25.12 is the
sole repository Node package and temporarily compiles strict TypeScript tests and
the one-file Desktop ESM entry; it is MIT licensed, actively maintained, and
does not enter the bundle. `package-lock.json` owns its exact platform closure,
integrity digests, and official-registry URLs. `npm ci` is the only install
command. Removing esbuild requires another deterministic TypeScript-to-ESM
build owner and identical bundle/test evidence.

Win32 uses a focused standard-library `ctypes` binding without modifying the
Hermes interpreter. Platform code remains behind a small display/process
boundary so another operating system can supply a native implementation.

JSON-RPC and WebSocket are specifications, not permission to build a generic
RPC framework. The bridge implementation includes only handshake, request,
result, error, notification, cancellation, and bounded binary artifact needs.
Godot, Unity, Unreal, and Cocos use their native JSON and WebSocket facilities.

FFmpeg/ffprobe and an image processor are unadmitted creative-tool candidates,
not current dependencies or component releases. If admitted, they are installed
and verified like engine components, never selected from `PATH`, and expose
source, version, size, license, and readiness in Hermes. Only arguments
constructed by typed commands may be accepted; Toqraq will not expose a raw
command-string wrapper.

FFmpeg publishes source rather than official Windows executables, and its
applicable LGPL/GPL obligations depend on build options. Admission therefore
requires a minimal exact build from upstream source in a provenance-producing
component workflow, including configuration, notices, digest, and corresponding
source. Runtime selection of an arbitrary third-party binary is prohibited.

The image-transform boundary is defined before selecting an implementation.
libvips and ImageMagick are current candidates; Toqraq benchmarks the actual
inspect, crop, resize, alpha, composite, and sprite workflows and reviews their
untrusted-input surface. Exactly one becomes the default component. If
ImageMagick is selected, its managed policy disables network, unneeded
delegates and coders, and enforces resource limits; libvips is not configured
as a secondary processor. A second processor requires a distinct proven
operation rather than broader format coverage in the abstract.

## Desktop state and data fetching

The current renderer uses Hermes SDK `atom`/`useValue` for the small selected
session projection and SDK `useQuery`/`queryClient` for authoritative setup,
component, and Hermes-session reads. Typed request functions and sequenced
events reconcile into those focused owners. Toqraq has no second cache layer,
Redux store, renderer service container, or generic event framework.

## API contract generation

Pydantic models generate OpenAPI and Hermes tool JSON schemas. Focused
repository-owned build modules read only the JSON Schema forms emitted by the
current FastAPI/Pydantic contract graph and generate deeply readonly
TypeScript DTO declarations plus importable structural runtime rules.
Unsupported schema forms fail generation instead of silently becoming `any`.
The rules contain exact object fields, closed values, patterns, and numeric,
string, and collection bounds; they are direct constants rather than a schema
interpreter. Handwritten Desktop decoders own hostile-container reads and
cross-field semantic invariants without restating those structural facts.

Generation uses the existing Python standard library and host-provided
FastAPI/Pydantic packages, adds no runtime or Desktop dependency, and never
runs on an end-user machine. OpenAPI, declarations, runtime rules, and the
Desktop bundle are checked for drift.

## Engine-owned dependencies

The Godot candidate uses its custom C++ module and engine-supplied JSON and
WebSocket facilities; it is not admitted. Unity C# packages, Unreal C++
plugins, and Cocos Creator TypeScript extensions remain candidate engine-local
boundaries, not chosen dependencies or support claims. Their current
authorization and technical gates are in
[engine-support.md](engine-support.md).

Each engine package may add a focused dependency only inside that engine
boundary. It cannot leak engine types or libraries into core or services.

Vendor installers, launchers, account systems, and license dialogs remain the
official vendor components. Toqraq orchestrates and observes them where public
interfaces permit; it does not reimplement or bypass them.

## Repository-owned code

Repository-owned implementations are appropriate when the behavior is a small
Toqraq invariant, for example:

- engine project probes;
- exact launch argument construction;
- component manifest validation and archive confinement;
- preview geometry;
- error and event envelopes;
- engine-to-common result mapping;
- session ownership and cleanup;
- context-capsule selection.

They are not appropriate for image codecs, audio/video codecs, general HTTP
clients, compression formats, spreadsheets, model providers, or a cross-engine
entity-component system.

## Disallowed dependency patterns

- runtime `pip install` into the shared Hermes interpreter;
- reliance on a globally installed executable or mutable `PATH` lookup;
- vendoring an upstream repository without an automated provenance and update
  path;
- two libraries with the same responsibility in the same layer;
- a framework introduced solely to provide names for simple direct functions;
- a general message broker, database, or distributed job system for local
  process state;
- a binary downloaded without license, digest, size, and source metadata;
- a dependency imported across an engine or platform boundary to avoid a
  proper typed port.

## Updates and removal

Every dependency update runs its direct unit, integration, supply-chain, and
clean-install tests. Generated lockfiles are reviewed for unexpected package or
license changes. Managed components are selected by exact version and digest.
Dependabot opens focused weekly Python, npm, and GitHub Actions updates. Its
proposal is discovery, not evidence: maintainers regenerate each owned closure,
retain immutable action commits, review advisories and licenses, and run the
same admission matrix before merging.

Removing a dependency includes:

1. deleting its adapter and unused configuration;
2. deleting transitive packages and generated glue;
3. replacing or deleting tests that protected only that implementation;
4. updating this document, notices, lockfiles, catalogs, and component UI;
5. proving clean installation without developer-machine remnants.

No dormant wrapper remains for a removed dependency.

## Official references

- [JSON-RPC 2.0 specification](https://www.jsonrpc.org/specification)
- [Godot custom C++ modules](https://docs.godotengine.org/en/stable/contributing/development/core_and_modules/custom_modules_in_cpp.html)
- [SCons release files](https://pypi.org/project/SCons/)
- [FFmpeg source downloads](https://ffmpeg.org/download.html) and
  [license considerations](https://ffmpeg.org/legal.html)
- [ImageMagick downloads](https://imagemagick.org/download/) and
  [license](https://imagemagick.org/license/)
- [libvips repository and releases](https://github.com/libvips/libvips)
