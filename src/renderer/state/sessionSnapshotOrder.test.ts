import assert from 'node:assert/strict'
import test from 'node:test'
import { canApplySessionSnapshot, canClearSessionRun } from './sessionSnapshotOrder.js'

function snapshot(id: string, revision: number) {
  return { id, run_revision: revision }
}

test('snapshot ordering rejects late updates and terminal clears for a replacement run', () => {
  const current = snapshot('session-1', 2)
  assert.equal(canApplySessionSnapshot(current, snapshot('session-1', 1)), false)
  assert.equal(canApplySessionSnapshot(current, snapshot('session-1', 2)), true)
  assert.equal(canApplySessionSnapshot(current, snapshot('session-1', 3)), true)
  assert.equal(canApplySessionSnapshot(current, snapshot('session-2', 1)), true)
  assert.equal(canClearSessionRun(current, 'session-1', 1), false)
  assert.equal(canClearSessionRun(current, 'session-1', 2), true)
  assert.equal(canClearSessionRun(current, 'session-2', 3), false)
})
