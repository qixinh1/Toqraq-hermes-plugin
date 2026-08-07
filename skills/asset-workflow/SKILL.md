---
name: asset-workflow
description: Use for sourcing and importing traceable game media.
---

# Asset Workflow Skill

Source, generate, adapt, import, and verify game media without losing its
rights or origin. This skill does not invent a provider, license, transform
result, or project-side provenance system.

## When to Use

Use for images, sprites, textures, animation, models, fonts, shaders, sound
effects, music, voice, or video intended for a game project.

## Prerequisites

- A player-facing purpose, style direction, and engine import target.
- Explicit user authority before placing or replacing project files.
- Provider authentication remains in Hermes or the provider's own setup flow.

## How to Run

Describe the asset need and destination in Hermes. A review or sourcing request
does not authorize project edits; import and conversion happen only when the
user asks for them.

## Quick Reference

- `search_files` and `read_file`: inspect existing assets and import settings.
- `web_search` and `web_extract`: inspect candidate source pages and terms.
- `image_generate` and `vision_analyze`: use only when exposed to this task.
- `video_generate`: use only when exposed by the enabled `video_gen` toolset
  and an active backend.
- `video_analyze`: use only when exposed by the enabled `video` toolset and a
  suitable model.
- `text_to_speech`: use only when exposed by the enabled `tts` toolset and its
  configured provider; it creates spoken dialogue or narration, not music or
  sound effects.
- `patch` or `write_file`: make visible, user-authorized project changes.
- `terminal`: invoke an existing approved project or media command.
- `toqraq_game_read_diagnostics`, `toqraq_game_read_process_output`: verify
  engine import and inspect bounded process failures.
- `toqraq_game_capture_frame`: verify the asset in visible game context.

## Delegation Boundary

Every `delegate_task` child has an independent `task_id`. A
`toqraq_game_*` call from that child targets the child's task, not the parent's
game. The parent gathers and passes bounded evidence, retains every live-game
operation, and verifies the returned summary. Delegate only an independent
analysis or review leaf; never ask a child to control or verify the parent game.

## Procedure

1. Define the asset's purpose, style constraints, import requirements,
   technical limits, and acceptance evidence.
2. Inspect existing project assets and settings before creating another source
   of truth.
3. Search or generate through capabilities that are actually available. Do not
   manufacture a source, author, license, provider response, or transform.
4. Record source/generation method, creator when known, license and attribution,
   source identifier actually returned, transformations, and intended
   destination. Prefer an existing project convention or visible source file;
   do not invent a new project-side sidecar format. Record identifiers, never
   secrets.
5. Stop and ask when rights are unclear. Preserve an editable source when
   useful and derive only the engine-ready outputs the target requires.
6. When import was requested, place text with `patch` or `write_file` and use
   one explicit `terminal` operation for binary files. Let the selected engine
   import them, then read its diagnostics.
7. Verify in context when the relevant runtime capability exists. Check the
   properties that matter: scale, crop, color, transparency, timing, looping,
   loudness, legibility, or accessibility.
8. Call `delegate_task` only for a bounded leaf such as style exploration,
   source/license comparison, or accessibility review. Pass the exact evidence
   and prohibit Toqraq live-game calls. Continue independent parent work; do
   not poll. When the summary returns, inspect its cited facts before use.

## Pitfalls

- "Free to download" is not redistribution permission.
- Do not remove watermarks, bypass accounts, or infer missing license terms.
- Do not promise crop, transcode, import-check, or media-understanding results
  when the corresponding Hermes or Toqraq capability is absent.
- Do not treat `text_to_speech`, voice mode, a provider setting, or a returned
  file path as music, sound-effect, transcription, or artifact-store
  capability.
- If wait/step is unavailable, use the strongest exposed state/frame evidence
  and mark any gameplay effect unverified; elapsed sleep is not proof.

## Verification

Verify provenance and rights, confirm the engine accepted the exact imported
file, and inspect the asset in its intended context when possible. Report which
checks were unavailable instead of replacing them with inference.
