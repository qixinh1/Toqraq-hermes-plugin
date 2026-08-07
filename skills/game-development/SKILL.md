---
name: game-development
description: Use for game changes that need live engine verification.
---

# Game Development Skill

Develop a standard engine project while keeping the project authoritative.
This workflow coordinates broad feature work; use a focused sibling skill when
the request is mainly asset production, numerical balance, or defect diagnosis.

## When to Use

Use for gameplay, scenes, scripts, controls, UI, levels, narrative,
accessibility, engine configuration, or another player-visible feature that
needs running-game evidence.

## Prerequisites

- A project or workspace the user intends to change.
- Only the Toqraq capabilities currently exposed to this Hermes session.
- No provider key or engine credential is collected by this skill.

## How to Run

Describe the intended player-visible outcome in Hermes. The main Agent owns the
decision, visible edits, integration, and verification; this skill is guidance,
not a separate command or permanent agent.

## Quick Reference

- `search_files` and `read_file`: find and inspect relevant project sources.
- `patch` or `write_file`: make user-authorized, visible project changes.
- `terminal`: run an existing project validation command when one is known.
- `toqraq_game_start`, `toqraq_game_stop`: own the running-game lifecycle.
- `toqraq_game_read_hierarchy`, `toqraq_game_read_objects`: read focused live state.
- The five `toqraq_game_input_*` tools and `toqraq_game_capture_frame`: act and capture visible evidence.
- `toqraq_game_read_diagnostics`, `toqraq_game_read_process_output`: read
  engine diagnostics and the latest bounded process tail.
- `toqraq_game_read_metrics`: read focused performance facts.
- `skill_view`: load `toqraq:asset-workflow`, `toqraq:balance`, or
  `toqraq:playtest-debug` when that narrower workflow dominates.

## Delegation Boundary

Every `delegate_task` child has an independent `task_id`. A
`toqraq_game_*` call from that child targets the child's task, not the parent's
game. The parent gathers and passes bounded evidence, retains every live-game
operation, and verifies the returned summary. Delegate only an independent
analysis or review leaf; never ask a child to control or verify the parent game.

## Procedure

1. State the intended player outcome, constraints, and evidence that would
   establish success.
2. Inspect only the source and live facts needed for this feature. Do not fetch
   a full tree, log, object set, and frame merely because each is available.
3. Capture a focused baseline when running behavior will change.
4. If the user requested implementation, make the smallest cohesive edit with
   `patch` or `write_file`. Explain instrumentation or project-package
   changes before applying them.
5. Run an available validation/import command, then start or restart the owned
   game only when runtime evidence is relevant.
6. Reproduce the affected path. Input acknowledgement proves delivery only.
   Use an available authoritative state read or frame capture after the effect.
7. Compare diagnostics and observed evidence with the baseline and acceptance
   criteria. Separate facts from inference and name every unverified claim.
8. Call `delegate_task` only for a bounded independent analysis or review.
   Pass the exact objective and evidence, prohibit Toqraq live-game calls, and
   continue independent parent work without polling. When its summary returns,
   inspect the cited facts before integration and perform final verification.

## Pitfalls

- Do not silently instrument or rewrite a project during observation.
- Do not use elapsed sleep as gameplay proof. If condition waiting or bounded
  frame stepping is unavailable, collect the strongest exposed state/frame
  evidence and explicitly mark the effect unverified.
- Do not infer live state from source or a successful input response.

## Verification

Verification is the smallest authoritative observation that proves the stated
acceptance criterion, plus a bounded diagnostic read. Report the exact tools
and evidence used; never claim runtime proof when the required capability was
unavailable.
