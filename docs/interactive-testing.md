# Interactive Testing

This document owns human-operated Hermes Desktop, real-preview, and release
journey verification. [testing.md](testing.md) owns automated layers, CI, and
the overall release gate. Interactive evidence supplements those checks; it
never substitutes for a missing automated invariant.

## Current availability

The production engine and certified component catalogs are empty. An ordinary
plugin composition can recognize a standard Godot 4 project and report
`runtime_unavailable`, but it cannot install or start an engine. The Godot
4.7.1 Windows executable is a candidate without a published, digest-pinned
component record and is not a selectable runtime.

The public Hermes plugin manifest has no Desktop companion or shared instance
lifecycle. The required behavior has been exercised only in a locally modified paired
host worktree. That worktree can provide development evidence when its exact
commit and dirty state are recorded; it cannot prove the public installation
journey.

Interactive results therefore use one of these exact evidence levels:

| Level | What may be exercised | What it proves |
| --- | --- | --- |
| Current composition | empty workspace, project recognition, `runtime_unavailable`, pane and setup states | present plugin behavior only |
| Engine candidate | exact candidate process, Bridge, controls, capture, and native preview | focused admission evidence only |
| Release journey | clean published host, published plugin source, and the exact component bytes proposed for admission through the catalog-backed path | end-user installation and interaction evidence |

A result names its level. Candidate or dirty-host evidence is never reported as
release evidence.

## Responsibility boundary

Interactive verification covers behavior that requires human perception or a
real Desktop environment:

- whether installation, setup, progress, and recovery are understandable;
- whether the pane is discoverable and follows Hermes layout behavior;
- whether a real game remains complete, aspect-correct, responsive, and
  controllable while the pane changes;
- whether keyboard, focus, localization, contrast, and announcements are
  usable rather than merely present in markup;
- whether Agent work, runtime evidence, and visible project changes form a
  coherent user journey;
- whether process, preview, and session ownership remain correct during real
  Desktop lifecycle transitions.

Automated tests continue to own exact schemas, bounds, state transitions,
security invariants, and deterministic failure cases. A human observation does
not waive a failed or skipped automated requirement.

## Environment record

Record the environment before starting:

- Toqraq revision, build identity, and dirty state;
- Hermes release or commit, build identity, and dirty state;
- evidence level and whether the host is public or locally modified;
- operating-system version, Desktop build, monitor arrangement, display scale,
  and input devices used;
- isolated Hermes profile and empty component-store confirmation;
- locale, theme, contrast mode, and reduced-motion setting;
- fixture project revision and expected engine declaration;
- exact component release ID, engine version, build ID, package digest, and
  source when an engine candidate is involved;
- tester and start time.

Do not record credentials, Bridge secrets, full environment mappings, raw
native handles, or unrelated absolute paths.

## Entry conditions

Before an interactive run:

1. run the relevant automated checks from [testing.md](testing.md);
2. regenerate contracts and `desktop/plugin.js`, then prove no drift;
3. use a fresh isolated Hermes profile with no engine or media component
   preinstalled and no reliance on `PATH`;
4. use a minimal versioned fixture whose expected visible behavior is known;
5. record every external suite or host requirement that is unavailable;
6. use only catalog-backed component facts for a full setup and Start journey.

If the host cannot load the required manifest-v2 package, mark the standard
installation journey blocked. Do not replace it with a manual Desktop file copy
or a second deployment path.

The current Desktop contributions are the preview/setup pane, status chip, and
Stop palette action. A settings route, composer attachment action, and Toqraq
key binding do not exist and are not part of current interactive evidence.

## Current empty-catalog journey

The following journey can verify the current composition without claiming a
playable engine:

1. Load the exact plugin package in the recorded paired host.
2. With no workspace, confirm the pane asks the user to open a Hermes project
   and sends no setup request.
3. Open a standard Godot 4 fixture and confirm the pane reports the recognized
   project facts and `runtime_unavailable`.
4. Confirm no engine version, component install action, or Start action is
   invented while both production catalogs are empty.
5. Open an unrecognized directory and confirm the UI distinguishes it from a
   recognized project whose runtime is unavailable.
6. Change the active workspace and Hermes session and confirm stale setup or
   session results do not replace the selected state.
7. Mount, unmount, relocate, resize, minimize, restore, and remount the pane;
   confirm Hermes remains the owner of its layout state.
8. Exercise the status chip and Stop action with no live game and confirm they
   remain safe, localized, and free of repeated failure notifications.

This journey proves only the empty-catalog Desktop behavior of the recorded
working pair.

### Observed current-composition run — 2026-08-07

The rebuilt package was installed through the standard Hermes plugin command
from a committed local package source, then the paired gateway and Desktop
were restarted. The host was the locally modified paired worktree, so these
results are current-composition evidence rather than release-journey evidence.

Recorded environment for that observation:

- Toqraq `0.1.0` came from an uncommitted local source snapshot with Desktop
  bundle SHA-256 `021355fa4c7290c01b952efe0f519a21d027b274fbccf5346e83bfe99d0c30df`;
- Hermes commit `7de554277de632364c74fcf8641daa58a9a977d9` had local manifest-v2 changes;
- the host ran on 64-bit Windows 11 build 26200 with one 2880×1800 display and
  system DPI 192, using the English (`en-US`) light Desktop presentation;
- this was an existing developer profile, not an isolated release profile;
  component absence followed the empty catalogs rather than a clean-store proof;
- the uncommitted standard Godot 4 fixture was the expected project, no engine
  component or runtime participated, and Computer Use supplied the input;
- contrast, reduced motion, physical keyboard/pointer behavior, and exact start
  time were not recorded and therefore are not evidence from this observation.

- **Pass — project recognition:** Hermes created and opened a project backed
  by `tests/fixtures/godot_project`. Toqraq recognized the standard Godot
  project and displayed `runtime_unavailable`; it exposed no certified runtime,
  install action, or Start action while the production catalogs were empty.
- **Pass — minimize transition:** Hermes moved the pane into its persisted
  narrow minimized rail.
- **Not proven — restore interaction:** Computer Use exposed a Restore node
  without actionable geometry and did not establish a working coordinate
  target. Desktop restart retained the minimized state. The paired host source
  declares restore handlers on the narrow rail and its tab, so this observation
  does not establish that a user cannot restore the pane or that the host
  separator blocks it.

Step 7 remains open because the automated interaction did not complete it.
Focused host state tests do not replace independent pointer, keyboard,
accessibility, geometry, persistence, and restart evidence on the real Desktop.

## Complete engine journey

Run this matrix for every exact engine/version proposed for the selectable
catalog. It becomes release evidence only with a clean published host, a
published plugin source, and the same catalog-backed component bytes under
review.

1. Install and enable Toqraq with the standard Hermes plugin command in a clean
   profile.
2. Open the fixture without a user-installed engine and confirm automatic
   project and exact-version detection.
3. Review component source, size, license, identity, and storage information;
   cancel one safe installation phase, then retry to verified readiness.
4. Unmount and remount the pane during component work and confirm the same
   backend-owned operation is recovered without duplication.
5. Start the game and confirm the reported engine, build, process, Bridge, and
   preview identities match the proposed exact release records.
6. Play through real input, then use the focused model tools for hierarchy,
   objects, diagnostics, process output, metrics, frame capture, simulation,
   and each supported input family.
7. Ask the Agent to make one visible project change through ordinary Hermes
   editing, rerun the exact project, and verify the intended result with
   runtime evidence.
8. Exercise component failure, launch failure, Bridge loss, socket recovery,
   preview reattachment, process crash, and bounded user-facing diagnostics.
9. Switch sessions while the game is running and confirm the process remains
   owned by its original Hermes session.
10. Finalize the owning session and verify complete cleanup before disabling or
    removing the plugin.

No step may use a globally installed engine, executable-path preference,
unrecorded package, or hidden project mutation.

## Desktop interaction matrix

### Contributions and reconciliation

- Register and dispose the plugin contributions without duplicates.
- Exercise the host-supported reload flow and verify stale effects do not
  survive the owning plugin instance.
- Mount and unmount the pane while requests and subscriptions are active;
  status and palette must continue to follow the same session projection.
- Disconnect and reconnect the event socket; authoritative REST state must
  repair any sequence gap or malformed event.
- Confirm no raw translation key, backend English application error, decoder
  failure, or repeated polling notification becomes visible.

Wait for an observable state, event, or bounded deadline. Do not use an
arbitrary sleep as evidence that an asynchronous transition completed.

### Preview and layout

- Verify both wide and tall pane shapes. The complete game frame remains
  visible, centered, and aspect-correct without stretching or cropping.
- Resize continuously and confirm the real preview follows instead of being
  replaced by a persistent placeholder.
- Drag, redock, minimize, restore, hide, show, and remount through Hermes pane
  controls; Toqraq must not create a second layout state.
- Exercise native preview presentation for every admitted native contribution.
  Exercise web preview only when an actual engine contribution supplies one.
- Move between monitors or display scales when supported and confirm physical
  pane geometry remains correct.
- Stop, replacement Start, crash, and finalize the game while the pane is
  mounted and unmounted; stale attachment work must not move, hide, or detach
  a newer run.

### Input, accessibility, and localization

- Reach and operate every Toqraq control using only the keyboard.
- Confirm visible focus, localized accessible names, useful tooltips, and
  status text that does not depend on color alone.
- Focus the game, exercise available input, release capture, change focus, and
  verify input does not remain stuck after stop or session switch.
- Test every required locale, including expanded labels, counts, durations,
  byte sizes, errors, progress, and recovery actions.
- Exercise light, dark, high-contrast, and reduced-motion behavior supported by
  Hermes without unreadable game chrome or clipped setup text.

## Ownership and cleanup inspection

For every terminal path, confirm that the owning session releases or retains
exactly the resources reported by its typed state:

- root process and complete descendant tree;
- stdout and stderr collectors after bounded final draining;
- Bridge listener, authenticated connection, and pending requests;
- preview attachment, native-window restoration, and subscriptions;
- component leases, temporary payloads, captures, and owned tasks.

Exercise explicit Stop, natural exit, crash, replacement Start, session
finalization, plugin disable, and plugin removal. A failed cleanup remains
visible and retryable; it is not accepted as success merely because the pane
disappeared.

## Evidence record

For each scenario record:

- stable scenario ID and evidence level;
- exact environment and fixture identities;
- preconditions, actions, and expected observable state;
- actual result with pass, fail, blocked, or not-applicable status;
- relevant trace ID, operation ID, Hermes session ID, and exact runtime
  identity;
- bounded screenshots, captures, diagnostics, or logs needed to reproduce a
  failure;
- final cleanup result and any resource still owned.

Redact secrets and unrelated user data. Preserve source-native diagnostic text
only within its normal bound. A screenshot or video is supporting evidence,
not a substitute for recording exact identities and cleanup status.

## Pass decision

An engine/version may close its interactive admission gate only when:

- every applicable complete-engine and Desktop scenario passes on the exact
  release bytes;
- all required locales and supported preview modes pass;
- no process, window, socket, task, temporary resource, or lease is orphaned;
- every failed or blocked scenario is resolved and rerun;
- the environment record proves a clean public host and standard plugin path.

A dirty paired host, direct candidate executable, skipped cleanup inspection,
or blocked standard installation remains development evidence and cannot close
the release gate.
