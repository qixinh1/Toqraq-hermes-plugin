import assert from 'node:assert/strict'
import test from 'node:test'
import type { ComponentJobResult } from '../contracts/generated.js'
import { decodeComponentJob } from '../bridge/componentDecoders.js'
import {
  createComponentJobState,
  reconcileComponentJob,
  selectComponentJob,
} from './componentJobs.js'

const FIRST_OPERATION = '8f489b96-c438-4d13-a54d-9e3f1020f531'
const SECOND_OPERATION = 'a836c2a8-6dbd-4b48-a4e7-157b891f763f'

function job(
  revision: number,
  overrides: Readonly<Record<string, unknown>> = {},
): ComponentJobResult {
  return decodeComponentJob({
    operation_id: FIRST_OPERATION,
    release_id: 'a'.repeat(64),
    component_id: 'engine.godot',
    action: 'prepare',
    state: 'running',
    phase: 'downloading',
    completed_bytes: 10,
    total_bytes: 100,
    revision,
    error: null,
    ...overrides,
  })
}

test('component job state keeps operations separate and is deeply immutable', () => {
  const first = job(1)
  const second = job(1, { operation_id: SECOND_OPERATION, component_id: 'tool.ffmpeg' })
  let state = createComponentJobState()
  state = reconcileComponentJob(state, first)
  state = reconcileComponentJob(state, second)

  assert.equal(selectComponentJob(state, FIRST_OPERATION), first)
  assert.equal(selectComponentJob(state, SECOND_OPERATION), second)
  assert.equal(selectComponentJob(state, 'missing'), null)
  assert.ok(Object.isFrozen(state))
  assert.ok(Object.isFrozen(state.byOperationId))
  assert.throws(() => {
    Object.defineProperty(state.byOperationId, 'extra', { value: first })
  }, TypeError)
})

test('newer server snapshot replaces the complete operation value', () => {
  const earlier = job(2)
  const authoritative = job(3, {
    state: 'failed',
    phase: 'verifying',
    completed_bytes: 80,
    error: {
      code: 'component.install_failed',
      category: 'upstream',
      parameters: {},
      details: { retryable: true },
      trace_id: 'ae01a6c4-87ca-4c97-9713-6d467329ed50',
    },
  })
  const firstState = reconcileComponentJob(createComponentJobState(), earlier)
  const reconciled = reconcileComponentJob(firstState, authoritative)

  assert.equal(selectComponentJob(reconciled, FIRST_OPERATION), authoritative)
  assert.equal(selectComponentJob(reconciled, FIRST_OPERATION)?.completed_bytes, 80)
  assert.equal(selectComponentJob(reconciled, FIRST_OPERATION)?.state, 'failed')
})

test('same and older operation revisions are ignored', () => {
  const current = job(4)
  const currentState = reconcileComponentJob(createComponentJobState(), current)
  const sameRevision = job(4, { completed_bytes: 50 })
  const older = job(3, { completed_bytes: 5 })

  assert.equal(reconcileComponentJob(currentState, sameRevision), currentState)
  assert.equal(reconcileComponentJob(currentState, older), currentState)
  assert.equal(selectComponentJob(currentState, FIRST_OPERATION), current)
})
