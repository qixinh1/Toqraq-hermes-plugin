# Changelog

## Unreleased

### Added

- One standard Hermes manifest-v2 package containing the Python entry,
  API-only Dashboard backend, generated Desktop companion entry, locale
  bundles, and four explicitly registered namespaced skills.
- Seventeen generated-schema Hermes tools for setup, lifecycle, simulation,
  hierarchy, objects, diagnostics, bounded process output, metrics, frame
  capture, and semantic, keyboard, pointer, text, and gamepad input.
- A synchronous `pre_llm_call` hook that injects at most 2,048 characters of
  safe cached facts for the calling task's live game or recognized active
  workspace. Workspace replacement, finalization, and plugin disposal clear
  the binding, and late probes cannot restore stale facts.
- Plugin-lifetime workspace synchronization follows public Hermes task,
  workspace, and gateway state even when the preview pane is unmounted, while
  sharing its setup query with the pane and releasing every probe identity.
- Plugin-lifetime session synchronization owns Hermes readiness, the selected
  REST snapshot, and its event stream. Pane, status, and Stop palette consume
  one projection without polling the complete session list, and pane unmount
  no longer suspends session truth or natural-exit notifications.
- Strict shared HTTP, tool, event, and Desktop contracts with one localized
  public error envelope and generated OpenAPI, TypeScript declarations, and
  structural runtime rules.
- Exact managed-component identities, bounded downloads and extraction,
  atomic publication, repair, removal, leases, and asynchronous job recovery.
- Immutable engine contributions, shared project/runtime selection, an honest
  empty production catalog, and focused setup state when no engine is admitted.
- Independent read-only project-format registration, allowing standard Godot
  projects to be recognized without claiming an admitted runtime or support.
- Bounded `project.godot` inspection preserves balanced multiline Variant
  values used by standard input and resource settings.
- Session-scoped pending-start and active-run ownership for prepared runtimes,
  process trees, bridge connections, preview attachments, tasks, temporary
  resources, and retryable cleanup.
- Atomic Windows process-tree ownership, bounded output collection, and typed
  native-display attachment/restoration.
- An authenticated loopback JSON-RPC bridge with exact handshake identity,
  strict bounds, request correlation, cancellation, binary frame transfer,
  invalidation merging, and fail-closed teardown.
- Focused hierarchy, object, diagnostic, process-output, metric, frame,
  simulation, and input services. Process output reads the current owned tree
  under the session gate and projects only its latest 16,384-character tail.
- A Godot custom module built beside untouched upstream source. The repository
  records an earlier local 4.7.1 native and production host-adapter exercise;
  it is not a published or selectable certified component.
- A deterministic Godot candidate ZIP packager and independent strict
  verifier reuse production archive and fingerprint policies. The manual
  workflow runs the Bridge exercise only against the final package's exact
  extracted executable and creates no release record or placeholder URL.

### Changed

- Successful plugin disposal now compare-and-clears its exact process-local
  container so disable and re-enable construct a fresh service graph. Failed
  or cancelled cleanup retains the sealed instance for the same disposer to retry.
- Python verification now installs one generated, universal, exact-version,
  hash-pinned wheel closure. It includes every directly imported host boundary
  and test package, while CI uses read-only repository permissions and never
  retains checkout credentials or resolves an unconstrained Python graph.
- Node 22 is the explicit renderer verification runtime, and the sole npm
  dependency is exact in both the manifest and integrity-checked lockfile.
- The base package now carries an explicit third-party notice stating that
  host and development dependencies are not bundled; managed components own
  their separate license and provenance notices.
- Weekly dependency-update discovery now covers Python, npm, and immutable
  GitHub Actions inputs; generated closures and admission evidence remain
  required before an update is accepted.
- Independent PyPI advisory review displaced vulnerable pytest, Starlette, and
  setuptools pins before the new locks were accepted. The Godot conformance
  closure now has a small checked-in direct-requirement source and generated
  Windows wheel lock instead of an ownerless requirements file.
- Every Hermes tool now declares and enforces the exact success DTO used by
  its matching REST operation; a wrong service result becomes the shared safe
  internal error. HTTP Start removes its host-owned session field before
  passing the common `GameStartRequest` to the lifecycle service.
- Desktop lifecycle presentation now follows only the active Hermes session,
  distinguishes paused, stopping, crash, backend-preview failure, and
  retrying native attachment states, and retains localized crash exit codes
  and preview trace details. Setup/component retries expose disabled busy
  states, component-plan mismatch has an actual refresh action, and dynamic
  setup, preview, phase, and status changes use restrained live regions.
- Desktop status dots now use the current public Hermes `tone` contract, and
  renderer interpolation calls use Hermes' positional argument protocol;
  focused tests prevent both silent presentation regressions.
- Bridge authentication now rejects malformed and wrong-credential candidates
  without consuming the launch, while a credential-proven identity mismatch
  immediately terminal-fails feature readiness with bounded wire facts. The
  host WebSocket version gate reads typed installed-distribution metadata.
- Finalization now rejects a missing or malformed Hermes session identity before
  clearing cached context or touching a game owner.
- Windows managed-engine launches now use a closed `SYSTEMROOT` and private
  managed-`APPDATA` environment instead of inheriting Hermes process settings.
- Desktop decoders now consume generated object fields, closed values,
  patterns, and bounds directly from the Pydantic/OpenAPI graph. Handwritten
  decoding retains only hostile-container reads and cross-field invariants.
- The complete handwritten renderer and test graph now use strict TypeScript.
  One paired-Hermes Program checks production, tests, and the
  generated declaration with the full strict option set; the esbuild-backed
  test runner compiles into and removes one invocation-owned temporary tree.
- Bundled skills keep all Toqraq live-game operations and final verification
  in the parent task because delegated children have independent task IDs.
  Asset guidance names only exposed image tools, opt-in video tools, and the
  configured Hermes `text_to_speech` tool for dialogue or narration. It does
  not present TTS as music, sound effects, transcription, or artifact storage.
- Removed the detached Godot fork-release workflow; the exact-tag,
  exact-commit, untouched-upstream candidate pipeline is the sole engine build
  path.
- Candidate builds accept one exact reviewed SCons vector, install a closed
  hash-pinned conformance set only after linking, preserve canonical provenance
  and notices, and upload only the three-file uncertified evidence directory.
- Game identity is exactly the owning Hermes `task_id`; tool schemas expose no
  alternate session selector.
- Under the required manifest-v2 host contract, Hermes session finalization
  and plugin disposal await the same idempotent cleanup owners used by explicit
  stop; current host evidence is the locally modified paired worktree.
- Setup and Start use one deterministic exact-release selection policy. Start
  performs no download, repair, alternate lookup, or runtime substitution.
- Public runtime state reports exact build identity, process state, independent
  preview/perception/control readiness, and redacted preview geometry.
- Native preview placement accepts only the physical pane rectangle; the
  session-gated service applies the live viewport's centered contain geometry
  without stretching or cropping it.
- Windows cleanup drains stdout and stderr to EOF after the complete process
  tree ends, preserving buffered tail output; rollback aborts collection only
  while a writer may still be alive.
- Events are session-scoped, sequenced accelerators; REST remains the
  authoritative reconciliation path.
- Desktop stop is conditional on the observed run revision, rejects mismatched
  terminal responses, refreshes replacements after revision conflicts, and
  clears only the exact absent or stopped run.
- Desktop success responses pass through one strict decoding and localization
  boundary. Pane, status, and lifecycle controls use Hermes i18n and expose no
  empty accessible labels or raw decoder failures.
- The pane now selects, subscribes to, and controls a Hermes game only after
  host session readiness succeeds. Native attachment and placeholder state use
  one run-bound projection, including deterministic stopping behavior.
- Preview-pane relocation now belongs solely to Hermes' native layout editor;
  the redundant selector that only changed local state has been removed.
- The active Hermes workspace is now the Desktop's sole pre-launch project
  source. Session-keyed path overrides, duplicate pane visibility controls,
  and inactive setup toolbar actions have been removed; Start is the setup
  surface's single ready-state action and runtime controls appear only while a
  game exists.
- Standard Git installation preserves the generated Desktop entry's exact LF
  bytes on Windows, with lifecycle coverage for source-to-install identity.
- Windows runtime selection uses the interpreter's stable platform tag, so a
  GUI launch cannot be misclassified when optional processor environment
  variables are absent.

### Availability

- The public Hermes plugin manifest has no Desktop companion or shared
  instance lifecycle. The required behavior used by local verification exists only in a
  modified paired host worktree; upstream integration and a published Hermes
  build remain release gates.
- A standard-command paired-host run loaded the pane and recognized the Godot
  fixture with `runtime_unavailable`. Computer Use then minimized the pane but
  could not establish an actionable Restore target. Source declares rail and
  tab restore handlers, so pointer, keyboard, accessibility, and persisted-layout
  recovery remain unproven rather than a confirmed host defect.
- Production `EngineCatalog` and certified component catalog are empty, while
  standard Godot project recognition is registered independently. Setup reports
  `runtime_unavailable` for a recognized Godot project, and ordinary Start
  cannot launch an engine until a complete digest-pinned contribution passes
  every admission gate and is explicitly registered.
- Unity, Unreal, and Cocos remain outside the selectable catalog. Game
  publishing remains deferred.
