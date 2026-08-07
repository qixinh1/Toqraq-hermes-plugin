# Preview Surfaces

This document owns the preview structure, state, and admission boundary.
[product.md](product.md) owns the user outcome,
[engine-adapters.md](engine-adapters.md) owns engine contribution conformance,
[plugin-packaging.md](plugin-packaging.md) owns the public Hermes host gate, and
[security.md](security.md) owns native-window and loopback trust policy.

## Current status

The repository implements one native-window presentation path. The renderer,
typed native preview API, session-owned display service, pure contain geometry,
and Windows display adapter exist and have focused tests. The Godot candidate
has a `PreviewLocator` that can produce this surface, but no engine or runtime
is currently admitted to the production catalog. Native preview code therefore
does not make Godot selectable or publicly supported.

`WebSurface` currently exists only as a validated Core value, safe public
snapshot kind, generated contract, and strict Desktop decoder. No engine in
composition returns one, and there is no Web presenter, authorization handoff,
or Web display service. Web preview is a future admission, not a current
feature.

The public Hermes host still lacks the released manifest-v2 companion
lifecycle required to load this pane from the standard plugin package. Local
paired-host evidence is recorded below and is not a public release claim.

## Stable boundary

An engine-owned `PreviewLocator` identifies a playable surface after launch.
It does not position, render, resize, or persist that surface. The session owns
the located surface and every presentation mutation until cleanup succeeds.

```text
Engine PreviewLocator
  -> PreviewSurface owned by one EngineSession
     -> NativeWindowSurface -> NativeDisplayService -> platform display
     `-> WebSurface          -> future admitted Web presenter
  -> safe PreviewSurfaceSnapshot -> Desktop session state
  -> one stable Hermes preview pane
```

The Core tagged union contains:

- `NativeWindowSurface`: one process-local native window reference and its
  authoritative viewport size;
- `WebSurface`: one explicit loopback URL, protected access credential, and
  authoritative viewport size.

`PreviewSurfaceSnapshot` exposes only the closed surface kind and viewport
size. Native handles, URLs, and credentials do not enter ordinary REST session
state, renderer storage, logs, events, or model context.

The common preview capability is engine-neutral. Engine-specific window or
server discovery remains in its contribution; Win32 behavior remains in the
Windows platform adapter. Common services do not branch on engine IDs.

## Pane and Hermes ownership

The Desktop companion registers one plugin-local `pane` contribution for its
entire lifetime. `collapsible`, bottom placement, docking, height, and minimum
height are initial Hermes layout hints. They are not a Toqraq layout model.

Hermes pane chrome and its layout tree exclusively own:

- visibility, minimize, rail presentation, and restore;
- tab stacking, relocation, resizing, and persisted layout;
- the user's Close and native layout-editor interactions.

Toqraq does not keep `paneOpen`, dock, or visibility shadow state. It does not
unregister and re-register the pane to simulate layout changes, and it does
not add its own collapse button, key binding, or status-bar visibility toggle.
Unmounting or restoring the pane may detach or recreate the renderer-owned
native attachment, but it does not restart the game or cancel backend-owned
component work.

Before launch, the pane reads only the public `host.state.cwd` workspace value
and does not copy it into plugin storage. Plugin-lifetime observers synchronize
task/workspace context and the active task's game readiness, authoritative REST
snapshot, and event stream even while the pane is unmounted. An absent or
unresolved workspace disables the pane's setup query and sends only an explicit
context clear, never a project probe. Once a game is running, the pane shows the
exact live-session snapshot and never rebinds that run to a later workspace value.

Renderer state has one selected Hermes-session owner and one combined readiness,
REST-read, and session projection. A snapshot for another owner or an older run
revision is rejected. Pane and status subscribe to that projection; the palette
reads it directly. Lifecycle actions use one opaque operation token per session,
and only the exact token can release the busy state. No presenter lists or polls
all game sessions.

## Current native-window implementation

### Attachment ownership

The native renderer path activates only when the selected live session:

- is running or paused;
- advertises `toqraq.preview.display`;
- reports preview readiness as `ready`; and
- exposes a `native_window` surface.

One pure renderer projection applies those facts to both attachment and pane presentation. A
stopping run is unavailable rather than connecting, and controller status is visible only for
the exact matching session and run revision.

Each mounted renderer effect creates one unique attachment ID bound to the
Hermes session ID and run revision. Attach, follow, visibility, and detach use
that identity. The service holds the session operation gate while resolving
the current owner and applying a native mutation, so stop, replacement, and
finalization cannot withdraw the surface during an operation.

Attaching a new owner restores the previous native mutation before locating
and attaching the replacement. A stale attachment ID cannot move, hide, or
detach the current owner. A response for a replaced run is detached and never
published as current. Late follow, visibility, and detach effects become
idempotent successes after their session disappears.

Partial attach and restore failures remain session-owned for cleanup retry.
Renderer unmount waits for an already-started effect and then detaches its
exact attachment. Session stop, natural exit, replacement, finalization, and
plugin disposal use the same resource cleanup graph.

### Geometry and resize

The renderer reports the complete pane rectangle in physical screen pixels.
It does not send client-fitted geometry or a host window selector. While
holding the session gate, `NativeDisplayService` reads the current surface's
authoritative viewport size and computes the largest centered whole-pixel
aspect fit inside that pane. The result never stretches or crops the game.

The host lookup point is derived from the complete pane, not from the
letterboxed game rectangle. The platform adapter receives only the resulting
destination and the host reference it located from that point.

`ResizeObserver`, animation-frame coalescing, and a bounded position probe
report movement and size changes. During an unsettled drag, the controller
hides the native child, serially follows every newer pane revision, and shows
it again only after the latest geometry settles. A visibility or layout
restore forces a fresh settled measurement rather than leaving a placeholder.

### Windows platform boundary

`WindowsNativeDisplay` is the current concrete display adapter. It:

- enables physical-pixel DPI awareness;
- uses the pane screen point to select the first visible interactive top-level
  window at that point, excluding the game process and transparent or
  non-activating overlays;
- receives no Hermes host process or window identity, so this selection does
  not prove that the selected window belongs to Hermes Desktop;
- snapshots the original game-window styles and ownership;
- applies reversible border, owner, taskbar, z-order, position, and clipping
  mutations;
- changes visibility without transferring focus; and
- restores the exact original state on detach or cleanup.

The adapter knows native handles and Win32 rules, not project, engine, session,
or aspect-fit policy. A stale handle produces a typed platform failure. Failed
native restoration remains owned; it is not reported as successful cleanup.

### Controller failure policy

One serialized controller owns attach, follow, visibility, retry, and detach
for a renderer mount. It hides duplicate errors, retries transient display
failure through an owned bounded-delay scheduler, cancels scheduled retry on
close, and never starts a second concurrent drive. Closing is idempotent and
awaits the active drive before detaching.

The pane renders localized setup or display failure state around this owner.
Technical platform details remain bounded diagnostics rather than UI strings.

## WebSurface admission

The existing Core value accepts only explicit `http` or `https` URLs on
`127.0.0.1` with a port, path, no URL credentials, and no fragment. Its access
credential is a validated 64-character lowercase hexadecimal value and is
excluded from representations and public snapshots. These validations define
a safe value boundary; they do not implement a Web preview.

A Web path enters process composition only when one real engine/version needs
it and all of the following exist together:

1. an engine-owned locator and session-owned loopback server with bounded,
   idempotent cleanup;
2. a focused authorization handoff that never stores or logs the credential;
3. a presenter built only on a public Hermes Desktop contribution surface;
4. restrictive origin, navigation, download, popup, permission, and external
   protocol policy;
5. the same session, run-revision, resize, contain, minimize, restore, focus,
   input-release, error, and accessibility guarantees as the native path;
6. contract, security, engine conformance, clean-install, and interactive
   Desktop evidence for the exact admitted release.

Until those gates close, no UI offers Web preview, no common service guesses a
URL, and documentation must not call the `web` snapshot kind supported.

## Paired Hermes host evidence

The locally modified paired Hermes development worktree contains focused
pane-shell tests for an agent-owned companion pane whose contribution declares
`collapsible: true`. Those tests and the paired Desktop type check pass, while
the current interactive evidence remains incomplete.

After a standard-command install from a committed local package source,
Minimize placed the Toqraq pane in Hermes' persisted narrow rail. Computer Use
exposed Restore without actionable geometry and did not establish a working
coordinate target; restarting Desktop retained the minimized layout. The
paired host source declares restore handlers on the rail and its tab, and the
plugin has no parallel layout state or Restore control.

This is an interactive evidence gap, not proof of a host or Toqraq defect. It
remains open until independent pointer, keyboard, and accessibility checks
complete the Restore path after layout persistence and restart. Public
availability also requires the lifecycle in
[plugin-packaging.md](plugin-packaging.md) and the clean gates in
[implementation-status.md](implementation-status.md) to close.

## Verification obligations

Current repository tests cover:

- surface validation and safe snapshot projection;
- whole-pixel contain geometry and host-point derivation;
- attach, replacement, follow, visibility, detach, rollback, and stale-owner
  behavior under the session operation gate;
- renderer resize serialization, stale-run rejection, retry, and close;
- Win32 discovery, reversible mutation, clipping, and cleanup contracts.

Admission still requires a real catalog engine, native or Web surface
conformance, clean standard installation, pane resize and relocation,
minimize and restore, rapid session switching, focus and input release,
failure recovery, and finalization cleanup in Hermes Desktop. The complete
evidence matrix is [testing.md](testing.md).
