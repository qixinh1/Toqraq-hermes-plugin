---
name: balance
description: Use for modeling and tuning connected game values.
---

# Balance Skill

Treat balance as a testable player-experience hypothesis rather than a list of
isolated numbers. This skill does not require live mutation when the user asks
only for analysis or recommendations.

## When to Use

Use for combat values, economies, progression, probability, rewards,
encounters, difficulty, pacing, or another connected numerical system.

## Prerequisites

- A target player experience, affected phase/cohort, and measurable range.
- Access to the project's authoritative values or formulas when they exist.
- Running-game evidence is optional and must be labeled unavailable when no
  suitable Toqraq capability is exposed.

## How to Run

Describe the tuning question and desired outcome in Hermes. The main Agent owns
assumptions, model choice, any authorized edits, and comparison with live
evidence.

## Quick Reference

- `search_files` and `read_file`: locate authoritative values and formulas.
- `execute_code`: run a bounded calculation or simulation when useful.
- `patch` or `write_file`: apply user-requested tuning to project sources.
- `toqraq_game_start` and the five `toqraq_game_input_*` tools: exercise representative scenarios.
- `toqraq_game_read_objects`, `toqraq_game_read_metrics`: read focused runtime facts.
- `toqraq_game_capture_frame`, `toqraq_game_read_diagnostics`: capture visible and diagnostic evidence.
- `toqraq_game_read_process_output`: inspect the latest bounded process tail
  when startup or native output is relevant.

## Delegation Boundary

Every `delegate_task` child has an independent `task_id`. A
`toqraq_game_*` call from that child targets the child's task, not the parent's
game. The parent gathers and passes bounded evidence, retains every live-game
operation, and verifies the returned summary. Delegate only an independent
analysis or review leaf; never ask a child to control or verify the parent game.

## Procedure

1. State the target experience, affected cohort or game phase, metric,
   acceptable range, and failure condition.
2. Locate authoritative values and formulas. Identify units, caps, rounding,
   randomness, dependencies, and existing telemetry or tests.
3. Capture a source calculation and, when available, a running-game baseline.
   Keep observed measurements separate from assumptions.
4. Build the smallest calculation or simulation that can challenge the
   hypothesis. Declare assumptions and scenarios. Declare sample size and seed
   policy only for stochastic work, and never present simulation as live proof.
5. If the user requested tuning, change authoritative data or code visibly
   with `patch` or `write_file`; do not create an unrequested parallel
   balance database.
6. Exercise representative and edge scenarios when runtime control exists.
   Input acknowledgement is delivery evidence only; follow it with an
   authoritative state read or frame when available.
7. Compare new evidence with the baseline and target range. Check adjacent
   systems and report uncertainty, outliers, and untested cases.
8. Call `delegate_task` only for a bounded leaf such as sensitivity analysis or
   an adversarial economy review. Pass the values and observations it needs,
   prohibit Toqraq live-game calls, and continue parent work without polling.
   Recalculate or inspect its evidence after the summary returns.

## Pitfalls

- Do not hide units, rounding, caps, or assumed player skill.
- Do not treat one happy-path encounter as system-wide evidence.
- If wait/step is unavailable, use the strongest exposed state/frame evidence
  and mark the gameplay effect unverified; elapsed sleep is not proof.

## Verification

Recalculate the exact changed path, exercise at least one representative and
one edge case when possible, and compare both against the declared target
range. Report simulation, live observation, and inference as separate evidence.
