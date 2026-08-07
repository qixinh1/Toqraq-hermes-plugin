# Desktop Experience

This document defines the Hermes Desktop experience for Toqraq. It describes
the user-visible contract, not a specific component hierarchy. The primary
goal is that a user can open a game project, ask the Hermes Agent to work on
it, run it, observe it, and interact with it without leaving Hermes.

## Experience principles

1. Follow the active Hermes session and workspace. Do not ask the user to
   reproduce information Hermes already exposes.
2. Detect before asking. Ask only when evidence is missing or genuinely
   ambiguous.
3. Keep the simple path to one action. Advanced choices remain available but
   never block a detected project from starting.
4. Explain every wait. Downloads, extraction, engine launch, bridge
   negotiation, and preview attachment expose progress, cancellation, and a
   recovery action.
5. Keep work visible. Agent-driven edits use normal Hermes project and
   artifact surfaces; Toqraq does not maintain a hidden copy of the project.
6. Preserve user agency. The plugin suggests skills and delegated tasks but
   does not impose a production pipeline or start background agents merely
   because a project is open.
7. Keep engine details behind project intentions until a detail is needed for
   diagnosis or an explicit engine choice.

## Hermes surfaces

The current Desktop contributions are the preview/setup pane, status chip, and
Stop palette action. Planned surfaces are listed separately so they are not
mistaken for current registration:

| Surface | Purpose |
| --- | --- |
| Preview pane | Live game display, input, process controls, and focused diagnostics |
| Status bar | Compact readiness and active-session process state |
| Command palette | Contextual lifecycle commands that remain useful outside the pane |
| Planned route or dialog | Project, runtime, components, creative defaults, storage, and diagnostics |
| Planned composer action | Create a bounded game-state snapshot and insert its reference |

A permanent sidebar item is justified only when user testing shows that the
route is otherwise hard to discover. Toqraq does not duplicate Hermes
project browsing, chat, artifacts, model selection, or generic provider
settings.

Pane relocation and layout persistence use the Hermes layout editor and native
pane interactions. Toqraq keeps one always-registered pane identity and does
not add a second set of visibility or dock controls.

Hermes currently has no public plugin-specific Settings contribution point.
A future Toqraq settings experience may use a plugin-owned route or dialog
built from the public Hermes UI kit. It must first earn a concrete setting
owner and discoverable public contribution point; it must not import private
Desktop modules.

## First-run path

The normal first run is:

```text
Install and enable Toqraq
  -> open a project in Hermes
  -> Toqraq probes the active workspace
  -> engine and any project-declared version are detected
  -> required managed components are checked
  -> missing components are installed inside Hermes with consent
  -> Start launches and attaches the preview
  -> Hermes Agent can perceive, control, edit, and verify the game
```

The pane shows one primary action at each step. It does not expose a blank
preview or an inactive toolbar while setup is incomplete.

The public `host.state.cwd` value is the only ordinary pre-launch project
source. Toqraq does not persist a session-keyed path override or reproduce the
Hermes folder picker. While Hermes has not published an absolute workspace,
including its transient `.` value, the pane asks the user to open a Hermes
project and makes no setup request. Backend services still normalize and
confine every accepted path. A running game continues to show the immutable
project root in its session snapshot when the visible workspace changes.

### Project detection

Project detection uses `host.state.cwd` and the active Hermes session. It
looks for adapter-owned evidence such as project manifests and engine version
metadata. The outcomes are:

- no registered project format: show the explicit engine-unavailable state
  without pretending the project was inspected;
- recognized project with no admitted runtime contribution: show the detected
  engine and project facts with an explicit runtime-unavailable state;
- one project format recognizes the active root: bind it without another
  prompt;
- several project formats recognize the same active root: present those engine
  candidates and their evidence;
- recognized project with an unresolved version: request only the version;
- no supported project: explain what was inspected and link to supported
  project requirements;
- inaccessible or invalid project: show the typed error and recovery action.

The public Desktop SDK does not expose the Hermes directory picker. Toqraq
does not reach into private APIs to add one. Normal folder selection belongs
to Hermes Projects. Discovery and selection of nested project roots is not
implemented and requires a separate bounded product decision.

### Engine and version choice

The detected engine and any project-declared version are the defaults. The user
may override the runtime for the workspace when the adapter declares that the
choice is valid. The selector displays:

- engine and exact version;
- source and distribution owner;
- download and installed size;
- platform and architecture;
- license or account requirement;
- installed, available, unsupported, or unavailable state.

Managed, isolated runtimes are the only launch source. Existing system engine
installations are ignored so setup, bridge identity, and behavior remain the
same on every machine. Engines whose official distribution requires an
account, license, or vendor manager expose that requirement in Hermes and
continue after the user completes it into the Toqraq-managed destination.

### Component installation

Component installation never hides inside a long Start request. The setup
surface resolves only the opaque component release IDs returned by setup and
shows their source, size, license, account requirements, and purpose. It never
derives a component ID, package name, or version from an engine label. The
user's install action is the explicit consent point;
after it creates the background job, the surface reports these phases:

```text
checking -> downloading -> installing -> verifying -> ready
```

The job state separately reports queued, running, cancelling, ready, failed,
or cancelled. The user can cancel safe phases, retry a failed operation, open
bounded details, and remove an unused managed component. A failed installation
does not leave the project in a false ready state. Temporary payloads are
cleaned up, while verified shared components remain available to other
sessions.

Unmounting or redocking the pane does not cancel backend-owned component work.
On remount, the surface reads the bounded active-job snapshot and resumes only
the unique prepare job whose opaque release ID occurs in the exact setup plan.
It never reconstructs an identity or starts a replacement job as part of
recovery. The selected operation is then reconciled through its authoritative
single-job read; if it already ended, refreshed component readiness decides the
next action.

## Preview pane

The preview pane is the game surface, not a simulated screenshot viewer. It
uses only the regions required by the current state:

1. setup guidance with at most one primary action before launch;
2. a compact runtime bar with immutable project and engine identity plus only
   currently meaningful lifecycle controls;
3. the display surface;
4. focused diagnostics or secondary display/input choices only when needed.

Hermes pane chrome is the sole minimize and restore control. Toqraq does not
add another collapse button, visibility key binding, status-bar visibility
toggle, or private pane-open state.

The display preserves the game's real aspect ratio. It scales with the pane
using `contain`: no stretching, clipping, or implicit change to the game's
logical resolution. Letterbox space uses a Hermes theme surface rather than
pretending to be game pixels. A pane resize recomputes the destination
rectangle and reattaches or resizes the native surface without replacing it
with a permanent placeholder.

The Desktop reports the physical pane rectangle, not a pre-fitted game
rectangle. The plugin process applies the authoritative viewport size from the
live session under the session operation gate, so a stale or modified renderer
cannot choose a different aspect policy.

Native-window attachment and streamed/web display are adapter capabilities.
The same pane contract applies to both. The UI says which display mode is
active only when that fact helps diagnosis or input behavior.

Native attachment failure remains visible while the owned controller retries
with bounded backoff. The placeholder says that retry is automatic; it does
not leave a failure-looking surface with an unexplained hidden recovery path.
A backend preview-readiness failure is distinct: the pane directs the user to
Stop and then Start the game, because no renderer attachment retry can repair
an engine-side preview failure.

### Input

Game input capture is explicit and reversible:

- click or a keyboard command focuses the game;
- a visible hint explains how to release focus;
- the release command works even when the game consumes ordinary input;
- focus loss releases captured pointer and keyboard state;
- destructive or privileged control actions require normal Hermes approval;
- input availability is reported separately from display availability.

Runtime actions have visible text or accessible names. An unavailable action
is omitted unless its disabled presence explains a transient state. Icon
shape, position, or color is never the only explanation of an action.

### Runtime state

Process and feature states are independent. A process can be running while
preview attachment, perception, or control has failed. The pane presents:

| Dimension | States |
| --- | --- |
| Project | probing, ready, ambiguous, invalid |
| Components | checking, action required, installing, ready, failed |
| Process | stopped, starting, running, stopping, crashed |
| Preview | unavailable, connecting, ready, failed |
| Perception | unavailable, connecting, ready, failed |
| Control | unavailable, connecting, ready, failed |

These are backend facts with revisions, not optimistic UI guesses. Socket
events update them quickly; REST reconciliation remains authoritative.
The runtime bar renders the current process state as text. During `stopping`,
Pause is absent and the remaining Stop action can finish or retry owned cleanup
when no lifecycle request is already in flight. A terminal notification
distinguishes an ordinary exit from a crash and includes the crash exit code;
the setup surface then owns the single Start recovery path.

## Session and workspace changes

A running game belongs to exactly one Hermes session. Switching the active
session changes the pane to that session's state without transferring process
ownership. Finalizing a session ends its process tree and releases its bridge,
display attachment, subscriptions, temporary files, and tasks.

An in-flight Desktop lifecycle action remains keyed to its originating Hermes
session. A second Start, Stop, or Pause for that session cannot overlap it.
Late snapshots from a previously selected session are ignored, and completion
of that old action cannot clear the busy state of the newly selected session.
Pane and palette Stop use the same authoritative renderer action; neither
depends on a pane-mounted snapshot to choose the Hermes session.

Changing `host.state.cwd` invalidates the prior task-bound context immediately
and triggers a new project probe. A singly recognized result becomes the
task's bounded non-live context; other outcomes leave it unbound. When
workspace preferences are implemented, selected engine version and asset
defaults must follow the workspace.
Processes, preview attachment, transient diagnostics, and snapshots follow
the session. The UI makes this distinction visible when a switch would hide a
running game.

## Planned settings contract

No Toqraq settings route or persisted setting exists now. If a concrete need
earns persistence, its UI is grouped by user intent:

### Project and engine

- detected project root and evidence;
- selected engine and exact runtime version;
- adapter capability summary;
- managed runtime and component readiness;
- validation and reprobe actions.

### Components and storage

- installed runtimes, bridges, tools, and optional models;
- source, version, size, integrity, license, and last-use information;
- install, retry, validate, and remove actions;
- cache location and storage use.

### Creative defaults

- target asset directories by purpose;
- image, audio, video, and voice format or dimension defaults;
- license and attribution filters for retrieved media;
- import and deterministic transformation presets;
- readiness links to exposed image tools and the opt-in video generation or
  analysis toolsets.

Provider credentials and model selection stay in Hermes. Toqraq does not copy
or reveal them.

### Preview and input

- preferred display mode when more than one adapter mode is available;
- scaling background and non-game chrome preferences;
- input capture and release shortcut;
- diagnostic verbosity and bounded log retention.

A future UI-only preference may use `ctx.storage` only after its typed owner and
lifetime are defined. Project behavior and component state belong to the
backend so tools, hooks, and Desktop contributions observe one truth. Secrets
never enter plugin storage.

## Agent and skill experience

The capsule is intentionally quiet. A cached live game supplies bounded owner,
project, runtime, process, readiness, preview, capability, and Toqraq skill
facts. Without one, a recognized active workspace supplies only its bounded
setup summary and skill names. It does not inject full skill bodies, logs,
scene trees, diagnostics, or a mandatory game-development workflow on every
model turn.

The user can ask in ordinary language. Skills guide the Agent to combine
Hermes editing, shell, Git, enabled generation, and delegation with Toqraq
perception, control, engine, import, and validation tools. A delegated child
has an independent task ID, so the parent retains live-game operations and
final verification. Optional focused delegation remains visible in Hermes.
Toqraq does not invent a separate agent dashboard.

A planned composer action may insert an inspectable opaque reference to one
bounded backend snapshot. It is not registered now. Binary frames and large
logs must never enter the composer.

## Asset workflow

Asset work follows one visible loop regardless of source:

```text
find or generate
  -> inspect content, metadata, rights, and technical properties
  -> preview a deterministic transformation
  -> write a new project asset through normal Hermes editing
  -> let the selected engine import it
  -> validate it in the running game
```

Original external media is preserved unless the user explicitly requests
replacement. Transformations expose dimensions, duration, channels, frame
rate, encoding, crop, loop, and output path before application. License and
attribution data stay attached to retrieved assets.

## Errors and recovery

Every user-visible failure has:

- a stable error code from the backend;
- localized title and explanation;
- safe structured details;
- one primary recovery action;
- a trace ID and access to bounded technical details when needed.

Raw exceptions, command lines containing sensitive values, and unbounded
engine logs never become notification text. Toasts announce a transition;
the setup route or pane owns durable recovery. Repeated polling failures do
not produce repeated notifications.

Examples of primary recovery actions include Reprobe project, Install
component, Retry verification, Restart engine, Reattach preview, Enable Python
plugin, and Open Hermes provider settings.

The setup-check Retry action is disabled while its replacement request is in
flight. If the setup response names a component release missing from the
current catalog snapshot, the durable component error offers the existing
catalog refresh action rather than instructing the user to retry without a
control.

## Internationalization

Every visible string, accessible name, notification, empty state, progress
stage, error mapping, and recovery action comes from Desktop locale bundles.
The backend returns codes and parameters, not English UI sentences. Engine,
vendor, and file-format names retain their official spelling.

Text layout must tolerate expansion and right-to-left locales. Do not build
sentences by concatenating translated fragments. Dates, counts, byte sizes,
durations, and percentages use locale-aware formatting.

## Accessibility

All Toqraq contributions meet the keyboard, focus, contrast, and semantic
behavior of the Hermes UI kit:

- every control is reachable and operable by keyboard;
- icon-only controls have localized accessible names and tooltips;
- focus is visible and restored after dialogs or failed actions;
- status is conveyed with text and semantics, not color alone;
- progress and connection changes use restrained live announcements;
- theme variables provide light, dark, and high-contrast rendering;
- animation respects reduced-motion preferences;
- the preview surface has an accessible label and does not trap focus;
- game input capture and release are announced clearly.

Blank labels on display, input, or process controls are defects, not a visual
style choice.

The status-bar process summary, setup transition, component phase, component
catalog load, and preview connection placeholder are the live regions. Byte
progress remains available through the native progress element but is not a
separate announcement on every polling update.

## Current implementation gaps

| Area | Current state | Open work or evidence |
| --- | --- | --- |
| Preview | typed native attach/follow/visible/detach client, contain controller, and stale-run checks exist | prove resize, minimize, restore, Hermes-native redock, detach, and cleanup with an admitted engine; add `WebSurface` only with a real contribution |
| Host pane lifecycle | paired local host maps Close for an agent-owned collapsible companion to native minimize and Restore | land and release that host behavior, then prove it in the clean interactive package journey |
| Setup | strict empty-catalog state has no Godot default or false install action; engine/version choice projections are localized but intentionally have no selector while no candidate is selectable | add the public selector before admitting an ambiguous project format or multiple certified versions, then exercise project, install, and Start states |
| Components | exact release facts, authoritative active-job recovery, cancellation, retry, and removal flows exist | exercise them with a published release and add the complete storage inventory route |
| Session state | selected-session snapshots use run ordering, exact event decoding, REST reconciliation, process text, crash notification, and preview failure details; perception/control readiness is available to tools and context but has no focused pane diagnostic | add the focused perception/control failure presentation before engine admission, then prove rapid session switching and stale effects interactively |
| Settings | no complete Toqraq route exists | add grouped project, component, creative, preview, and diagnostic settings |
| Composer | no game-state attachment action exists | add bounded snapshot-reference insertion |
| Skills | four skills are registered and named by live context | add optional Desktop discovery only if user testing needs it |
| Context | live-session and typed recognized-workspace capsules exist | prove representative standard-install model flows |
| Accessibility | localized setup and control labels exist | complete keyboard, focus, high-contrast, and game-input-release tests |

## Acceptance journey

A release candidate passes the following journey on a clean Hermes Desktop
profile with no supported engine on `PATH`:

1. Install and enable Toqraq with the standard Hermes plugin command.
2. Open a supported project in Hermes.
3. See the correct engine and project version without manual configuration.
4. Install required components from the Toqraq surface with understandable
   size, source, license, progress, cancellation, and recovery.
5. Start the game and receive an aspect-correct preview in the pane.
6. Resize and redock the pane with Hermes native layout controls without losing
   the attached display.
7. Focus, control, release, observe, capture, and attach game state using only
   keyboard-accessible Hermes UI.
8. Ask the Agent to change the project and verify the result through Toqraq.
9. Switch sessions and observe correct process ownership.
10. Finalize the owning session and confirm complete runtime cleanup.
