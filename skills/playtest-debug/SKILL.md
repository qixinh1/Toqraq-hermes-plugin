---
name: playtest-debug
description: Use for bounded playtesting and running-game diagnosis.
---

# Playtest and Debug Skill

Produce repeatable running-game observations, then diagnose only when the
request and evidence require it. A playtest may end with findings and no source
change; diagnosis does not authorize a repair.

## When to Use

Use for structured playtesting, bugs, regressions, crashes, incorrect
interaction, flaky gameplay, runtime errors, or performance problems.

## Prerequisites

- An expected behavior or playtest question and a bounded starting state.
- Relevant engine/runtime identity, project revision, save state, seed,
  viewport, and input assumptions when they affect reproduction.
- Only the runtime capabilities exposed to the current Hermes session.

## How to Run

Describe either a playtest scenario and observation rubric or a concrete
failure and success criterion. The main Agent owns reproduction, evidence, and
any separately authorized project change.

## Quick Reference

- `search_files` and `read_file`: inspect source after runtime evidence narrows the target.
- `toqraq_game_start`, `toqraq_game_stop`: own a bounded test run.
- The five `toqraq_game_input_*` tools: execute deliberate player actions.
- `toqraq_game_read_hierarchy`, `toqraq_game_read_objects`: read focused state.
- `toqraq_game_capture_frame`: capture visible evidence.
- `toqraq_game_read_diagnostics`, `toqraq_game_read_process_output`: inspect
  engine diagnostics and the latest bounded process tail.
- `toqraq_game_read_metrics`: inspect focused performance facts.
- `patch` or `write_file`: apply a repair only when the user requested one.

## Delegation Boundary

Every `delegate_task` child has an independent `task_id`. A
`toqraq_game_*` call from that child targets the child's task, not the parent's
game. The parent gathers and passes bounded evidence, retains every live-game
operation, and verifies the returned summary. Delegate only an independent
analysis or review leaf; never ask a child to control or verify the parent game.

## Procedure

1. Choose the branch:
   - For a structured playtest, define the scenario, duration/action bound,
     observation rubric, and questions. Findings need not imply a defect.
   - For diagnosis, define expected behavior, observed failure, exact starting
     state, reproduction steps, and success criterion.
2. Reproduce or play before editing when safe. Capture only evidence that can
   answer the rubric or distinguish hypotheses.
3. Execute a deterministic action sequence. Input acknowledgement proves
   delivery only; follow critical actions with available authoritative state
   or frame evidence.
4. For a playtest, organize observed friction, comprehension, feedback,
   pacing, accessibility, and uncertainty without inventing a root cause.
5. For diagnosis, separate facts, inferences, and unknowns, then form the
   narrowest hypothesis that explains all evidence and inspect relevant source.
6. If the user requested a repair, make the smallest visible change with
   `patch` or `write_file`, repeat the same reproduction, and check one
   adjacent regression path. Otherwise stop with findings or diagnosis.
7. Report the scenario, evidence, cause only when established, any change,
   before/after result, remaining risk, and uncontrolled conditions.
8. Call `delegate_task` only for a bounded leaf such as reviewing one crash
   trace or challenging one hypothesis. Pass the bounded evidence, prohibit
   Toqraq live-game calls, and continue parent work without polling. Verify the
   returned conclusion against fresh evidence from the owning parent task.

## Pitfalls

- Do not force every usability finding into a bug or causal hypothesis.
- Do not edit merely because a diagnosis suggests a likely repair.
- Never treat input acceptance or elapsed sleep alone as game-state proof. If
  wait/step is unavailable, mark the strongest available observation and the
  remaining effect as unverified.

## Verification

For playtesting, verify that every finding maps to an observed point in the
declared scenario and rubric. For a repair, repeat the same reproduction and
compare authoritative before/after evidence plus one adjacent path.
