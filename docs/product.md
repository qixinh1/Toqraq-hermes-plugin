# Product Definition

This document defines what Toqraq is expected to make possible for a user and
the Hermes model. Architecture and implementation decisions are subordinate to
this product boundary.

## Product statement

Toqraq turns Hermes Desktop into a practical game-development workspace. A user
can discuss, inspect, change, run, play, and debug a real engine project with a
model while staying in Hermes. The project remains a normal project for its
engine; Toqraq supplies orchestration and observation rather than a new game
format.

The product is organized as **Perceive -> Develop -> Publish**. This is a user
journey and capability boundary, not a rigid workflow engine.

## Current availability

When loaded by the paired manifest-v2 development host, the plugin exposes its
pane, eighteen tools, four skills, session lifecycle, component machinery,
common Bridge, and Windows/Godot implementation boundaries. The public Hermes
plugin manifest has no Desktop companion or shared instance lifecycle, so the
standard manifest-v2 install path is not released yet. Production includes side-effect-free recognition of
the standard Godot 4 project format, while the launchable-engine and certified
component catalogs remain empty. Setup may therefore identify a Godot project
and its bounded project facts, but reports `runtime_unavailable`; Start cannot
launch it. Project-format recognition is not an engine-support claim. The
repository records an earlier local Godot 4.7.1 observation covering native
and production host-adapter exercises, but it has no admitted published
component record. It is not a supported selectable runtime. Publishing is
deferred.

## Users

Toqraq serves:

- a beginner who has Hermes Desktop but has not installed a game engine;
- a developer who wants the model to inspect and operate a running game;
- a designer who works through conversation, playable results, and ordinary
  project assets rather than engine internals;
- a team member opening an existing Godot, Unity, Unreal, or Cocos project;
- a model agent that needs bounded, structured evidence before changing code.

The first useful result must not require the user to understand engine paths,
Bridge protocols, managed-component identities, or Toqraq's internal
architecture.

## 1. Perceive

Perception answers four questions: what is this project, what is running, what
does it look and sound like, and what is wrong?

### Project perception

The model can request:

- detected engine and declared or recommended version;
- project configuration and entry scene or level;
- scenes, scripts, resources, dependencies, packages, plugins, autoloads, and
  input actions;
- import state, missing references, parser errors, and engine diagnostics;
- image, animation, audio, video, font, shader, and model asset inventories;
- bounded summaries and targeted reads rather than an unconditional project
  dump.

Project files remain the authority. Toqraq may cache derived observations for
the active process, but it does not create a second project database.

The initial detailed project read is an explicit task-owned inventory tool. It
prefers the caller's live game's immutable project binding and otherwise uses
that task's latest recognized Hermes workspace. It returns bounded, pageable
scene, script, resource, setting, dependency, and input metadata without file
contents, configuration values, absolute paths, links, generated trees, or
secret-like files. A project replacement invalidates an in-flight page instead
of combining facts from two workspace or game incarnations.

### Runtime perception

For the game owned by the current Hermes session, the model can request:

- process and feature readiness;
- exact engine and bridge build identity;
- hierarchy and selected runtime objects;
- selected properties, components, resources, and relationships;
- recent engine diagnostics;
- the latest bounded stdout/stderr process-output tail, including loss and
  collector-failure state;
- a screenshot or short capture;
- viewport, timing, memory, rendering, physics, audio, and other available
  performance signals;
- changes since a cursor or revision.

Engine-native detail remains available. The common result envelope does not
rename an Unreal Actor into a Godot Node or discard Unity Component data.

### Media perception

The model can inspect dimensions, channels, duration, frame rate, codecs,
loudness, transparency, color space, and import suitability. When the active
Hermes task exposes image or video understanding, Toqraq may provide a bounded
preview or source-file reference for semantic analysis.

### Context capsule

For a Hermes task that owns a live game, the current bounded context capsule
tells the model:

- project and engine identity;
- exact selected version;
- whether a game is running;
- readiness of preview, perception, and control;
- preview kind and size when ready;
- relevant Toqraq capabilities and skill names.

Everything else is retrieved explicitly. A project tree, logs, media bytes, or
full scene hierarchy never enters every model call.

Without a live game, a plugin-lifetime Desktop observer binds the task's active
workspace independently of preview-pane visibility. It stores only the latest
recognized-project setup result: owner, bounded project path, engine, selected
runtime when one exists, setup action, viewport hint, and skill names. An
empty, invalid, unrecognized, ambiguous, or failed probe clears the binding.
Both capsule forms are capped at 2,048 characters and detailed evidence
remains tool-driven.

The complete evidence model is [perception.md](perception.md).

## 2. Develop

Development combines Hermes-native work with Toqraq's engine-aware work.

### Source and project changes

Hermes file, terminal, and Git capabilities perform ordinary edits.
Toqraq contributes:

- engine and version detection;
- engine-aware project validation;
- import and compile status;
- exact managed runtime selection;
- launch, stop, restart, pause, resume, and frame step;
- deterministic input and repeatable play sequences;
- observation before and after a change;
- focused diagnostics and performance evidence.

No Toqraq-specific project format is required. If an engine needs a project
bridge package, the proposed project change must be visible, explained, and
applied through the same reviewable editing path as other source changes.
Read-only project-format recognition may ship before any runtime for that
engine is admitted. It exposes only facts proven from the project and never
creates an install or Start path by itself.

### Play and preview

The game appears in a Hermes pane as a native-window or web preview surface.
The real viewport aspect ratio is preserved, the complete frame remains
visible, and resizing the pane updates the preview continuously. Human input
goes to the preview. The model can send typed input through the runtime bridge.

### Debug and verify

The model can form a hypothesis, change the project, run or reload it, operate
the game, capture evidence, inspect runtime state, and compare the result. A
skill may recommend this loop, but Toqraq does not force a fixed sequence or
silently declare quality based on a synthetic score.

### Creative assets

Toqraq composes only media tools exposed to the active Hermes task. The
verified host surface includes image generation and analysis; video generation
and analysis are available only when their opt-in toolsets and required
backend or model are enabled. Conditional `text_to_speech` can produce spoken
dialogue or narration with the user's configured Hermes voice provider. It is
not a music or sound-effect generator. Toqraq assumes no agent-callable
transcription tool or generic artifact store. It adds only game-specific
capabilities:

- provider readiness and game-domain output defaults;
- open asset discovery with license and provenance metadata;
- target-engine import constraints;
- image crop, resize, format conversion, atlas preparation, and inspection;
- audio trim, normalize, loop preparation, format conversion, and inspection;
- video trim, scale, frame extraction, transcode, and inspection;
- generated or transformed asset placement as an ordinary visible file
  change.

Toqraq uses maintained libraries and managed media executables. It does not
implement image, audio, or video codecs from first principles.

### Design, narrative, balance, and playtest

Bundled skills help the model reason about:

- game concept and player experience;
- mechanics, controls, onboarding, levels, narrative, UI, and accessibility;
- art direction, animation, VFX, music, sound effects, and voice;
- economy, progression, encounters, probability, difficulty, and pacing;
- instrumentation, reproducible playtests, regressions, and performance.

Hermes delegation creates a specialist only when the main model needs focused
parallel work. Every delegated child has an independent task ID. Because live
Toqraq tools always target their caller's task, the parent task retains its
game controls, gathers bounded live evidence for the child, and performs final
verification. A child receives only a bounded independent leaf such as source
review, license comparison, style critique, or numerical analysis. Delegated
children do not become permanent departments or create mandatory process
artifacts.

The initial bundled skill set stays deliberately small:

| Skill | Purpose |
| --- | --- |
| `toqraq:game-development` | Route an engine task through inspect, edit, run, and verify |
| `toqraq:asset-workflow` | Find, generate, transform, license, and import assets |
| `toqraq:balance` | Model values, run simulations, and validate them in the game |
| `toqraq:playtest-debug` | Reproduce, observe, diagnose, and verify game behavior |

Engine-specific guidance is loaded only for the detected engine and exact
version. A skill teaches tool composition and judgment; it does not copy API
reference material into every prompt.

The complete workflow composition is
[development-capabilities.md](development-capabilities.md).

## 3. Publish

Publishing is deliberately deferred. Its eventual boundary may include export
configuration, reproducible builds, signing, platform validation, store
metadata, release artifacts, and distribution. None of those concerns may
complicate the perception or development interfaces before publishing work is
approved.

The only current requirement is that observations and visible source changes
do not make a standard engine project harder to export later.

## Engine support promise

An engine is shown as supported only when at least one exact version satisfies
the baseline:

- project detection and analysis;
- managed or guided runtime provisioning;
- launch, restart, and owned process-tree cleanup;
- preview inside Hermes;
- pause, resume, bounded frame step, and frame capture;
- hierarchy and object inspection;
- diagnostics and process output;
- model-driven input;
- performance snapshot;
- session finalization cleanup;
- clean-install and real-engine conformance tests.

Godot is the first implementation. The architecture must admit Unity, Unreal,
and Cocos contributions without changing common services, but an external
technical, distribution, or authorization gate blocks catalog registration as
strictly as a missing capability. Vendor login, license acceptance, written
authorization, and distribution constraints are never treated as UI details
that code can bypass. The current evidence and unblock conditions are in
[engine-support.md](engine-support.md).

## First-use experience

The intended ordinary path is:

1. install and enable Toqraq with the standard Hermes command;
2. open a game workspace in Hermes;
3. let Toqraq detect the project, engine, and version;
4. press **Install and start** if a managed component is missing;
5. watch progress in the Toqraq pane;
6. play in the pane and work with the Hermes model.

A game that has not started uses the active Hermes workspace as its only
project candidate. Toqraq does not ask for or retain a competing free-form
project path. An empty workspace asks the user to open a Hermes project and
does not run a setup probe. Once started, the game keeps the exact project root
recorded by its owning session even if the user views another workspace.

A single valid project and version require no prompt. Ambiguity creates one
focused choice. Large downloads disclose size, storage, source, license, and
any login requirement before they begin. Failures include a localized cause
and a concrete recovery action.

Closing and reopening the pane does not restart component work. The pane
recovers every active preparation required by the exact setup plan, observes
them one at a time in plan order, and refreshes readiness after each terminal
result. Removal availability comes from authoritative component leases rather
than an inference from whichever game is currently visible.

## Product acceptance

The product is ready for an offered engine/version only when a new Hermes
Desktop user with an empty Toqraq component store can:

- install the base plugin with the standard command;
- discover the Toqraq pane without a manual file copy or package install;
- open a standard engine project without configuring executable paths;
- provision the required engine through Hermes;
- start and interact with the real game in the pane;
- ask the model to inspect, change, run, control, and verify the project;
- recover from an interrupted download or failed launch in the pane;
- remount the pane without duplicating or losing active component work;
- finalize the session and leave no owned process, window, bridge, or temporary
  resource behind.

Convenience claims must be demonstrated by clean-install tests, not inferred
from developer-machine state.
