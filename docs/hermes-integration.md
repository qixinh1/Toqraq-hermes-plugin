# Hermes Integration

This document defines the public Hermes surfaces used by Toqraq. Toqraq is a
Hermes Desktop plugin; it does not reproduce conversation, editing, model,
provider, or delegation systems.

## One plugin identity

One installed package exposes three presenters with the stable ID `toqraq`:

| Presenter | Responsibility |
| --- | --- |
| root Python `register(ctx)` | tools, hooks, skills, services, and disposer |
| API-only Dashboard backend | scoped REST and session event socket |
| `desktop/plugin.js` | Hermes Desktop contributions |

Under Toqraq's required manifest-v2 host contract, Hermes owns all three
through one install, enable, update, disable, and remove lifecycle. Current
evidence is limited to the locally modified paired host worktree. Python
registration never copies or installs a second Desktop entry.

## Current registration

`register(ctx)` currently registers:

- the seventeen tools listed in [api.md](api.md);
- awaited `on_session_finalize`;
- synchronous `pre_llm_call`;
- the four namespaced bundled skills;
- one composed asynchronous container disposer.

Tools, hooks, and Dashboard routes share the process-local container. The
manifest tool and hook declarations must equal the runtime registrations.

### Tools and session ownership

Tool argument schemas come directly from strict Pydantic request models. Every
declaration also names the exact HTTP-shared success DTO; the handler rejects a
different returned model before serialization. It returns a compact JSON
string containing that DTO or the same public error value used by HTTP.

Game tools obtain their owner from Hermes's calling `task_id`; the model cannot
provide a different session selector. Start therefore accepts only
`project_dir`, optional `engine`, and optional `version`. Setup is read-only and
does not require a live game owner.

Tools expose game intentions, not transport calls, native handles, executable
paths, UI clicks, or arbitrary engine methods.

### Finalization and plugin disposal

`on_session_finalize` awaits the same session-service cleanup used by explicit
stop. Its Hermes session ID is the game ID. Cleanup drains the process tree,
Bridge, preview attachment, tasks, temporary resources, and component leases;
a failure remains owned for retry. A missing or malformed host session ID fails
the hook before any context or game owner changes, so the host lifecycle can retry.

The container disposer is the instance-level barrier for disable, update,
remove, force reload, and host shutdown. It rejects new work, closes session
and component owners independently, and reports all failures. Hermes must not
unregister the old instance or load a replacement before that barrier succeeds.

### Conditional context capsule

`pre_llm_call` is a synchronous projection over cached state. It reads the
hook's `task_id` and calls the session service's non-mutating lookup. When
there is no matching live session, it checks only the process-local workspace
summary already bound to that exact task. Lookup failure returns no context.

For a matching live session it returns at most 2,048 characters containing
only:

- owner task ID and internal run revision;
- a JSON-quoted bounded tail of the project path;
- exact engine, version, build, platform, and architecture;
- process and preview/perception/control readiness;
- safe preview kind and dimensions when ready;
- a bounded capability list;
- the four registered skill names.

It contains no hierarchy, objects, diagnostics, logs, media bytes, credentials,
Bridge endpoint, native handle, provider setting, conversation text, or
general development instructions. It performs no filesystem, network, engine,
component, or model work in the LLM path.

Without a live game, `PUT /workspace-context/{task_id}` may cache only a ready,
singly recognized project summary. Its capsule contains owner, a quoted bounded
project-path tail, engine, selected runtime when resolved, setup action,
viewport hint, and the four skill names. A plugin-lifetime Desktop observer
drives this endpoint from public active-task, workspace, and gateway state; it
does not depend on the preview pane being mounted. A newer update clears the
old value before probing, and its process-local identity prevents a late probe
from republishing stale context. Empty, invalid, unrecognized, ambiguous, or
failed probes leave no binding. Finalization and plugin disposal clear it. The
hook has no workspace parameter, so the first turn receives this capsule only
when Desktop synchronization has already completed.

### Skills

The plugin registers these files through `ctx.register_skill`; Hermes owns the
`toqraq:` namespace and loads them explicitly:

| Skill | Purpose |
| --- | --- |
| `toqraq:game-development` | inspect, edit, run, and verify an engine change |
| `toqraq:asset-workflow` | source, generate, transform, license, import, and verify media |
| `toqraq:balance` | model values, simulate outcomes, and validate them in the game |
| `toqraq:playtest-debug` | reproduce, operate, observe, diagnose, and verify behavior |

Skill bodies are not inserted on every turn. The live capsule advertises their
names, and the model loads a relevant skill explicitly. Each skill composes
the seventeen Toqraq tools with Hermes file, shell, Git, and delegation
capabilities. Media tools are named only where their actual enablement contract
is relevant; a skill does not implement a host capability again.

### Delegation

Toqraq registers no permanent agent system. A skill may instruct the active
Hermes agent to call `delegate_task` for a bounded independent leaf or review.
Hermes gives every child an isolated context, terminal session, and independent
task ID. Toqraq live-game tools always bind to their caller's task ID and accept
no parent-session selector, so a child cannot inspect or control the parent's
game by calling those tools.

Before delegation, the parent gathers only the bounded source or live evidence
the leaf needs and passes it in the request context. The child performs analysis
or review without Toqraq live-game calls. When its summary returns, the parent
checks the cited files or evidence, owns any live input or lifecycle operation,
and performs final verification. The summary is evidence to inspect, not a
transfer of session ownership or proof of success.

Toqraq itself does not dispatch delegation from the plugin backend because the
backend has no parent-agent workspace and task context. Delegated work remains
visible and optional in the Hermes task flow.

## Desktop boundary

The Desktop entry is one ESM default export using public Hermes SDK imports.
Its current public surfaces include:

- pane contributions for setup and live preview;
- one status contribution and one Stop palette action;
- `host.state.activeSessionId`, workspace directory, gateway, profile, locale,
  and viewport facts;
- scoped REST/socket clients;
- plugin locale bundles and Hermes UI primitives.

Route/dialog, composer, key-binding, and plugin-storage use remain planned and
are added only when a concrete current flow owns them.

Backend state is authoritative. Events accelerate updates; REST reconciles the
first read, reconnect, malformed event, and sequence gap. Desktop storage never
owns a process, component job, engine selection truth, credential, or backend
error message.

The public SDK does not justify importing private Desktop modules. Hermes owns
ordinary project selection; Toqraq uses the active project and does not add a
private directory picker. A future settings route must use a public
contribution rather than reaching into host internals.

## Workspace-only binding boundary

The Desktop binding connects:

```text
Hermes task ID + active workspace directory
  -> bounded project probe
  -> engine/version choice
  -> cached project snapshot
```

It is invalidated by task finalization, workspace change, project
disappearance, or plugin disposal. It contains no conversation text. The
binding endpoint reuses the setup service and returns its authoritative result;
the hook never performs the probe itself.

## Media and provider composition

Toqraq uses only media tools exposed to the active Hermes task:

- `image_generate` and `vision_analyze` when those toolsets are available;
- `video_generate` only when the opt-in `video_gen` toolset has an active
  backend and its required credential;
- `video_analyze` only when the opt-in `video` toolset and a suitable model are
  available;
- `text_to_speech` only when the `tts` toolset exposes its configured provider,
  and only for spoken dialogue or narration candidates.

`text_to_speech` is not a music or sound-effect generator. The verified public
contract provides no agent-callable transcription operation or generic
artifact-store API. Toqraq does not infer those surfaces from voice-mode or
provider internals. Provider credentials, voices, and model choices stay in
Hermes.

Toqraq registers a media provider only if it supplies a genuinely new backend.
It never copies provider credentials or model choices into plugin settings,
renderer storage, logs, errors, or context.

The intended composition is:

```text
Hermes search or an enabled generation tool
  -> provider-returned URL or visible source file
  -> Toqraq inspect/transform operation
  -> visible project edit
  -> engine import and runtime verification
```

Toqraq-owned asset-source, media-inspection, and media-transform operations are
not implemented.

## Errors and internationalization

Domain failures cross Hermes and HTTP as one stable code, category, safe
parameters/details, and trace ID. Tool JSON is language-neutral. Desktop maps
the code to its locale bundle and owns user-visible recovery text. Raw
exceptions and unbounded engine output remain outside model and renderer state.

## Current boundary table

| Integration | Current state | Open evidence or work |
| --- | --- | --- |
| Tools | seventeen engine-neutral generated-schema tools | prove full standard-install model flow with an admitted engine |
| Finalization | awaited session cleanup | prove real component/process/preview cleanup after production admission |
| Instance disposal | one awaited composed disposer | prove failure retention across host lifecycle operations |
| Skills | four namespaced skills registered and tool names current | representative real workflows |
| Context | live-game or recognized-workspace capsule, 2,048-character ceiling | prove representative standard-install model flows |
| Delegation | independent-task children receive bounded leaves; parent owns live-game work and verification | representative parallel and review flows |
| Media | conditional image, opt-in video, and configured spoken-voice TTS contracts are named | game-specific source/inspect/transform adapters remain absent |
| Desktop package | manifest-v2 companion entry in the plugin root, exercised in the modified paired host tree | clean published Hermes host, published plugin install, and complete interactive lifecycle evidence |
