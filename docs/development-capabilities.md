# Development Capabilities

This document defines how Toqraq combines Hermes and engine capabilities to
help create a finished-quality game rather than a demonstration. It describes
available instruments and optional skill guidance, not a mandatory studio
process.

## Responsibility split

| Need | Primary owner | Toqraq contribution |
| --- | --- | --- |
| Edit source and assets | Hermes file capabilities | engine-aware validation and visible change plans |
| Run terminal and build commands | Hermes shell capability | exact managed engine entry points and typed operations |
| Version control | Hermes Git capability | runtime evidence linked to the current project revision when available |
| Generate or analyze image/video/voice | enabled Hermes media toolsets | game-domain constraints, provenance, import validation |
| Use specialist reasoning | Hermes model and `delegate_task` | focused skills and bounded evidence |
| Understand and control a game | Toqraq | project/runtime perception, preview, input, diagnostics, metrics |
| Transform media | future admitted Toqraq managed tools | typed deterministic operations and engine target checks |
| Engine import and execution | engine contribution | normalized user intentions and exact runtime ownership |

Toqraq does not wrap a generic Hermes operation merely to rename it. It adds a
tool only when the operation needs game, engine, component, session, license,
or media-transform semantics.

## Current harness boundary

The plugin currently registers seventeen focused game tools, the four skills
defined below, and a `pre_llm_call` capsule capped at 2,048 characters. It
prefers the calling `task_id`'s cached live game identity, process, readiness,
preview, capability, and skill facts. Otherwise it may use the recognized
active-workspace setup summary synchronized by Desktop. The hook itself
performs no project or provider work and injects no tree, logs, or media.

Open-asset adapters, provider orchestration, and deterministic creative media
operations are not implemented. Those sections define admission contracts,
not currently available tools.

Every `delegate_task` child receives an independent task ID. Live Toqraq tools
bind to the caller's task, so the parent task retains game lifecycle, input,
perception, and final verification. A child receives bounded source or live
evidence from the parent and performs only an independent analysis or review
leaf; it does not call Toqraq tools to reach the parent's game.

## Development loop

The smallest useful loop is:

```text
understand intent and current evidence
  -> make a visible project change
  -> validate/import with the selected exact engine
  -> run or reload the game
  -> play or inject a bounded scenario
  -> perceive the result
  -> keep, refine, or revert through ordinary Hermes/Git work
```

Skills teach this loop when it is useful. The plugin does not block a source
edit until a planning artifact exists, force an Agent review, or automatically
rewrite a change that did not pass a heuristic score.

## Game design and narrative

Hermes reasoning, files, and optional delegated tasks can help create or refine:

- core fantasy, audience, pillars, constraints, and session length;
- mechanics, controls, feedback, failure, mastery, and onboarding;
- progression, rewards, content cadence, levels, encounters, and pacing;
- world, characters, dialogue, quests, branching, and environmental narrative;
- UI flow, accessibility, localization, and player settings;
- lightweight design notes, tables, or diagrams when the user benefits from
  them.

These artifacts remain ordinary project or documentation files and are never
required by Toqraq. Runtime observations let the model compare intended
experience with actual play instead of treating prose as proof.

## Gameplay, scenes, and levels

Hermes edits engine-standard source, scenes, prefabs, maps, resources, or data.
Toqraq supplies:

- project/version-aware validation before launch;
- engine import, parse, and compile diagnostics;
- start, restart, pause, resume, and bounded frame step;
- bounded semantic, keyboard, pointer, text, and gamepad input;
- hierarchy and selected-object observation;
- screenshots, temporal captures, metrics, and diagnostic revisions;
- a repeatable scenario result that records inputs and observed evidence.

A scenario is a bounded sequence of declared input and observation steps, not
a general scripting language. It cannot execute arbitrary engine code, shell
text, or object methods.

An input batch is validation-atomic: the bridge validates and maps every event
before dispatching any of it. Its acknowledgement proves only that the complete
batch was accepted for dispatch. Gameplay effect is established separately by
stepping or waiting and then reading authoritative state or capturing a frame;
Toqraq does not invent simulation or frame revisions for an input operation.
Keyboard input uses W3C `KeyboardEvent.code` for physical position and
`KeyboardEvent.key` for layout-dependent meaning. Committed printable or IME
text uses the separate text operation.

Every read or control response is decoded against the exact pending operation
that owns its JSON-RPC ID. A hierarchy, object, diagnostic, metric, or frame
result must satisfy its originating selection and bounds. A pause result must
equal the requested state, and a step result must report the exact requested
frame count. Method-specific results do not repeat generic result-kind tags or
tuple lengths that the enclosing method and payload already establish.

## Asset sources

Open and free asset acquisition uses focused `AssetSource` contributions. A
source implements only:

- search by media kind, query, cursor, and explicit license filter;
- inspect one source record and preview;
- acquire the exact selected asset into a managed staging area;
- return provenance and attribution data.

The normalized record contains source ID, asset ID, source page, author,
license identifier and URL, attribution text, preview metadata, download
identity, and known technical facts. The adapter retains source-native facts
without converting an unclear license into a permissive one.

Admission requires a stable public API or documented download contract,
maintained service, clear terms, rate-limit handling, and a direct source-page
link. Toqraq does not scrape arbitrary search results, remove watermarks,
bypass accounts, infer missing rights, or present "free to download" as
permission to redistribute.

Acquisition flow is:

```text
search -> inspect preview and rights -> user/model selects exact record
       -> download and verify -> inspect technical properties
       -> transform to a new output -> visible project edit -> engine import
```

Source assets remain unchanged in staging. The source adapter's managed record
keeps provenance through transformation. Placement uses an existing project
convention when one exists; Toqraq does not invent a project-side metadata
format or assume a generic Hermes artifact store.

## Generated assets

Hermes owns provider credentials and model selection. Toqraq may compose
`image_generate` when exposed, `video_generate` only when the opt-in
`video_gen` toolset has an active backend, and `text_to_speech` only when the
`tts` toolset exposes its configured provider. The speech result is a spoken
dialogue or narration candidate, not generated music or a sound effect. Toqraq
supplies a game-aware request context only when asked, such as:

- intended in-game role and art direction;
- dimensions, transparency, tiling, frame, palette, or safe-area constraints;
- duration and framing constraints for an enabled video backend;
- selected engine import target and destination;
- reference files chosen by the user.

Generated output is treated as an untrusted candidate asset. Toqraq inspects
its technical properties, records only source identifiers actually returned by
the enabled tool, previews any deterministic transformation, and lets Hermes
make the visible project edit. Generation never writes directly into the
project from a provider callback.

## Image, 2D, 3D, animation, and VFX

Image operations are narrow typed commands backed by one admitted managed
processor selected through the dependency benchmark:

- inspect, crop, pad, resize, rotate, flip, composite, and format conversion;
- alpha and color-space normalization;
- sprite-sheet slicing or assembly from explicit frame geometry;
- thumbnails and bounded previews;
- validation against engine texture/import limits.

Toqraq does not install both libvips and ImageMagick for the same work, does
not implement raster codecs or a general node-based image editor, and never
accepts a raw processor command. Source and output are distinct paths unless
the user explicitly approves a visible replacement.

3D meshes, rigs, animations, materials, shaders, particles, and VFX remain
engine- or specialist-tool domains. Toqraq initially perceives their metadata,
orchestrates existing Hermes/engine tools, validates import, and observes the
result in game. A new deterministic transformer is added only for a concrete
workflow with a maintained component; Toqraq does not build a 3D suite.

## Music, sound effects, and voice

The verified Hermes agent-tool contract exposes conditional `text_to_speech`
for spoken dialogue and narration. It provides neither a music or sound-effect
generator nor an agent-callable transcription operation. Approved asset
sources may retrieve music, sound effects, and voice with explicit rights. A
new audio-generation or transcription surface must enter through its own
public host contract rather than being inferred from voice-mode internals.
After a media component passes admission, Toqraq may add these deterministic
operations:

- inspect streams, sample rate, channels, duration, loudness, peaks, and
  silence;
- trim, concatenate, resample, remix channels, normalize, fade, and convert;
- prepare an explicit loop region and preview the boundary;
- extract or replace bounded tracks in a supported container;
- validate the selected engine's import target.

Semantic music or audio judgments are model inferences tied to a bounded sample
and source file. Deterministic analysis reports measurements separately.

## Video and cinematics

`video_generate` may produce a candidate only when the user enabled the opt-in
`video_gen` toolset and configured an active backend. `video_analyze` may inspect
a clip only when the opt-in `video` toolset and a suitable model are available.
Absence is reported rather than replaced with a claim. A future admitted media
tool may perform bounded inspect, trim, concatenate, scale, crop, frame
extraction, frame-rate change, audio mapping, and transcode operations. Every
admitted transform must declare exact input, output, time range, geometry,
streams, codec policy, size bound, and timeout.

Engine-specific timeline, sequencer, animation-tree, or cutscene changes use
normal project editing plus engine validation. Toqraq verifies the result by
running and capturing the relevant bounded interval; it does not create a
second cinematic editor.

## Balance, economy, and progression

The `toqraq:balance` skill combines model reasoning, ordinary data files,
Hermes terminal computation, optional tables or spreadsheets available to the
user, and live observations.

It can help with:

- damage, health, cooldown, probability, loot, cost, reward, and progression
  curves;
- economy sources/sinks, expected value, variance, and exploit cases;
- enemy, encounter, level, and difficulty pacing;
- Monte Carlo or deterministic simulations outside the game;
- scenario runs in the real game and comparison with the analytical model;
- readable tables and plots when they improve a decision.

Toqraq owns no universal balance schema. The game data remains in its natural
project format. A skill first locates the authoritative values, then selects
the smallest calculation and in-game evidence needed.

## UI, accessibility, localization, and input

The model can use captures, hierarchy, input, and project files to inspect:

- layout across declared viewport sizes and safe areas;
- focus, keyboard/gamepad navigation, pointer behavior, and remapping;
- readable text, contrast, animation, motion, captions, subtitles, and audio
  controls;
- locale expansion, pluralization, font/glyph coverage, and right-to-left
  behavior supported by the project;
- onboarding, error feedback, save/load, pause, and settings flows.

Toqraq reports evidence and engine facts. Accessibility judgment remains a
combination of deterministic checks, model review, and human playtesting.

## Playtest, QA, and performance

The `toqraq:playtest-debug` skill helps:

- record exact reproduction prerequisites and bounded input sequence;
- observe before/after revisions, frames, diagnostics, and metrics;
- distinguish launch, import, bridge, game-code, display, and input failures;
- create focused regression scenarios;
- explore edge states without claiming exhaustive coverage;
- identify frame-time, memory, rendering, physics, loading, or asset issues
  from available engine metrics and captures.

Human play remains important for feel, fun, clarity, accessibility, and
creative quality. Toqraq makes human feedback easy to pair with exact runtime
evidence; it does not replace that feedback with an automatic score.

## Skills and delegated specialists

The base plugin installs four small skills:

| Skill | Loads when |
| --- | --- |
| `toqraq:game-development` | a source, scene, level, system, or engine task needs an inspect/edit/run/verify loop |
| `toqraq:asset-workflow` | media must be found, generated, understood, transformed, licensed, or imported |
| `toqraq:balance` | numeric behavior needs modeling, simulation, or live validation |
| `toqraq:playtest-debug` | behavior must be reproduced, observed, diagnosed, or verified |

They are procedures, not personas. The main Hermes model may delegate a
focused, independent leaf such as visual review, audio direction, balance
analysis, or regression review. The delegated request names its outcome,
bounded evidence, allowed project scope, and expected return. Hermes gives the
child an independent task ID and isolated context. The parent passes the needed
evidence, keeps all Toqraq live-game calls and controls, then checks the child's
summary against the cited source or fresh live evidence. A child never uses its
own Toqraq tool binding as a selector for the parent's game.

Toqraq does not auto-create a producer, designer, artist, programmer, audio
team, and QA team. Persistent specialist state, automatic meetings, and hidden
agent work would add coordination cost and constrain user/model judgment.

## Tool design

Tools expose user intentions, not UI clicks or engine protocol methods. A tool:

- targets the calling Hermes session for live game work;
- uses a typed request generated from the shared contract source;
- has explicit selection, bounds, cancellation, and output-reference behavior;
- returns concise typed facts, cursor/revision, and trace ID;
- reports capability absence rather than approximating it;
- leaves generic source editing, shell, Git, and model operations to Hermes.

Avoid mega-tools such as `make_game`, `create_all_assets`, or
`run_full_pipeline`. The model can compose narrow reliable operations more
intelligently than a fixed opaque pipeline.

## Completion evidence for a game feature

When relevant to the user's intent, a strong result can show:

- authoritative project files changed through Hermes;
- engine import or compile status;
- exact runtime and feature readiness;
- reproduction or play input used;
- before/after capture or runtime observation;
- diagnostic and performance status;
- asset source, license, generation, and transformation provenance;
- tests or scenarios added;
- creative or human judgments that remain unresolved.

This is evidence available to the user and model, not a required manifest or
release gate for every edit.

## Acceptance

A representative vertical-slice exercise should prove that Hermes and Toqraq
can, without leaving the workspace flow:

1. refine a small mechanic and its player feedback;
2. acquire or generate an image and acquire a sound with provenance;
3. inspect and transform both to declared engine targets;
4. make visible standard project changes;
5. import, run, preview, and control the game;
6. observe hierarchy, frames, diagnostics, audio, and performance;
7. simulate and validate at least one balance decision;
8. reproduce and verify one behavior through a bounded scenario;
9. identify which conclusions are engine facts, deterministic measurements,
   model judgments, and human judgments;
10. finalize the session with complete resource cleanup.

Publishing the resulting game remains outside the current scope.
