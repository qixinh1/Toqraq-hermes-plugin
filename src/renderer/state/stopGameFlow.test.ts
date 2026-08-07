import assert from 'node:assert/strict'
import test from 'node:test'
import { decodeSession } from '../bridge/sessionDecoders.js'
import { ToqraqApiError } from '../bridge/errorBoundary.js'
import type {
  ErrorCategory,
  JsonValue,
  PublicError,
  SessionResult,
} from '../contracts/generated.js'
import { executeStopGame } from './stopGameFlow.js'
import type { StopGamePorts } from './stopGameFlow.js'

const SESSION_ID = 'session-1'
const TEST_CONTEXT: Readonly<Record<string, never>> = Object.freeze({})
type TestContext = typeof TEST_CONTEXT
type StatePorts = Pick<
  StopGamePorts<TestContext>,
  | 'beginSessionOperation'
  | 'finishSessionOperation'
  | 'currentSession'
  | 'applySessionSnapshot'
  | 'clearSessionRun'
>

test('a GET to DELETE replacement conflict refreshes the new run without clearing it', async () => {
  const oldRun = session(7)
  const replacement = session(8)
  const harness = stateHarness(oldRun)
  let reads = 0
  const ports: StopGamePorts<TestContext> = {
    ...harness.ports,
    getSession: async () => (++reads === 1 ? oldRun : replacement),
    stopSession: async (_ctx, sessionId, runRevision) => {
      assert.equal(sessionId, SESSION_ID)
      assert.equal(runRevision, 7)
      throw apiError('session.invalid_state', 'conflict', { reason: 'run_replaced' })
    },
  }

  const stopped = await executeStopGame(TEST_CONTEXT, SESSION_ID, ports)

  assert.equal(stopped, false)
  assert.equal(reads, 2)
  assert.equal(harness.current(), replacement)
  assert.deepEqual(harness.clearCalls, [])
  assert.equal(harness.finished(), 1)
})

test('retained cleanup can retry the same stopped run revision', async () => {
  const retained = session(7, false)
  const harness = stateHarness(session(7))
  let attempts = 0
  const ports: StopGamePorts<TestContext> = {
    ...harness.ports,
    getSession: async () => retained,
    stopSession: async () => {
      attempts += 1
      if (attempts === 1) {
        throw apiError('session.cleanup_failed', 'internal', { retryable: true })
      }
      return retained
    },
  }

  await assert.rejects(
    executeStopGame(TEST_CONTEXT, SESSION_ID, ports),
    (error: unknown) =>
      error instanceof ToqraqApiError && error.code === 'session.cleanup_failed',
  )
  assert.equal(harness.current(), retained)
  assert.deepEqual(harness.clearCalls, [])

  assert.equal(await executeStopGame(TEST_CONTEXT, SESSION_ID, ports), true)
  assert.equal(attempts, 2)
  assert.equal(harness.current(), null)
  assert.deepEqual(harness.clearCalls, [[SESSION_ID, 7]])
  assert.equal(harness.finished(), 2)
})

test('a mismatched terminal result fails closed and cannot clear either run', async () => {
  const oldRun = session(7)
  const harness = stateHarness(oldRun)
  const ports: StopGamePorts<TestContext> = {
    ...harness.ports,
    getSession: async () => oldRun,
    stopSession: async () => session(8, false),
  }

  await assert.rejects(
    executeStopGame(TEST_CONTEXT, SESSION_ID, ports),
    /invalid Toqraq stopped run identity/,
  )

  assert.equal(harness.current(), oldRun)
  assert.deepEqual(harness.clearCalls, [])
  assert.equal(harness.finished(), 1)
})

function session(runRevision: number, alive = true): SessionResult {
  return decodeSession({
    id: SESSION_ID,
    run_revision: runRevision,
    runtime: {
      engine: 'godot',
      version: '4.7.1',
      build_id: 'godot-4.7.1+toqraq.1',
      distribution_id: 'toqraq.windows',
      platform: 'windows',
      architecture: 'x86_64',
    },
    project_dir: 'D:/game',
    root_pid: 42,
    process_state: alive ? 'running' : 'ended',
    alive,
    exit_code: alive ? null : 0,
    started_at: 10,
    bridge: { id: 'toqraq.bridge', protocol: '1.0', capabilities: [] },
    capabilities: ['toqraq.preview.display'],
    preview: { state: 'connecting', error: null, surface: null },
    perception: { state: 'connecting', error: null },
    control: { state: 'connecting', error: null },
  })
}

function stateHarness(initial: SessionResult) {
  let current: SessionResult | null = initial
  let busy = false
  let finishCount = 0
  let operationSequence = 0
  const clearCalls: Array<[string, number]> = []
  const ports: StatePorts = {
    beginSessionOperation: (sessionId) => {
      if (busy) return null
      busy = true
      operationSequence += 1
      return Object.freeze({ owner: sessionId, sequence: operationSequence })
    },
    finishSessionOperation: () => {
      busy = false
      finishCount += 1
      return true
    },
    currentSession: () => current,
    applySessionSnapshot: (incoming) => {
      if (
        current !== null &&
        current.id === incoming.id &&
        current.run_revision > incoming.run_revision
      ) {
        return false
      }
      current = incoming
      return true
    },
    clearSessionRun: (sessionId, runRevision) => {
      if (
        current === null ||
        current.id !== sessionId ||
        current.run_revision > runRevision
      ) {
        return false
      }
      clearCalls.push([sessionId, runRevision])
      current = null
      return true
    },
  }
  return {
    clearCalls,
    current: () => current,
    finished: () => finishCount,
    ports,
  }
}

function apiError(
  code: string,
  category: ErrorCategory,
  details: Readonly<Record<string, JsonValue>>,
): ToqraqApiError {
  const failure: PublicError = Object.freeze({
    code,
    category,
    parameters: Object.freeze({}),
    details: Object.freeze(details),
    trace_id: '11111111-1111-4111-8111-111111111111',
  })
  return new ToqraqApiError(failure, code)
}
