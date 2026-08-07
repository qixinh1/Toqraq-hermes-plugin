import assert from 'node:assert/strict'
import test from 'node:test'
import {
  cancelComponentJob,
  getComponentJob,
  listActiveComponentJobs,
  listComponents,
  startComponentJob,
} from './componentClient.js'
import { ToqraqApiError } from './errorBoundary.js'
import type { RestBridgeContext, RestRequestOptions } from './transport.js'

const OPERATION_ID = '8f489b96-c438-4d13-a54d-9e3f1020f531'
const RELEASE_ID = 'a'.repeat(64)
const TEST_I18N = Object.freeze({ t: () => 'Localized test message.' })

interface RestCall {
  readonly path: string
  readonly options: RestRequestOptions
}

function job() {
  return {
    operation_id: OPERATION_ID,
    release_id: RELEASE_ID,
    component_id: 'engine.godot',
    action: 'prepare',
    state: 'queued',
    phase: 'checking',
    completed_bytes: 0,
    total_bytes: 0,
    revision: 1,
    error: null,
  }
}

test('component client uses bounded authoritative list and job reads', async () => {
  const calls: RestCall[] = []
  const ctx: RestBridgeContext = {
    i18n: TEST_I18N,
    async rest(path, options) {
      calls.push({ path, options: options ?? {} })
      return path === '/components' ? { releases: [] } : job()
    },
  }

  const components = await listComponents(ctx)
  const snapshot = await getComponentJob(ctx, OPERATION_ID)

  assert.ok(Object.isFrozen(components))
  assert.ok(Object.isFrozen(snapshot))
  const [listCall, getCall] = calls
  assert.ok(listCall)
  assert.ok(getCall)
  assert.equal(listCall.path, '/components')
  assert.ok((listCall.options.timeoutMs ?? 0) >= 30_000)
  assert.equal(getCall.path, `/component-jobs/${OPERATION_ID}`)
  assert.ok((getCall.options.timeoutMs ?? 0) >= 30_000)
})

test('component client reads active jobs without starting or joining work', async () => {
  const calls: RestCall[] = []
  const ctx: RestBridgeContext = {
    i18n: TEST_I18N,
    async rest(path, options) {
      calls.push({ path, options: options ?? {} })
      return { jobs: [job()] }
    },
  }

  const active = await listActiveComponentJobs(ctx)

  assert.equal(active.jobs[0]?.operation_id, OPERATION_ID)
  assert.deepEqual(calls, [
    {
      path: '/component-jobs/active',
      options: { timeoutMs: 30_000 },
    },
  ])
})

test('component client starts and cancels jobs with exact request bodies', async () => {
  const calls: RestCall[] = []
  const ctx: RestBridgeContext = {
    i18n: TEST_I18N,
    async rest(path, options) {
      calls.push({ path, options: options ?? {} })
      return job()
    },
  }

  await startComponentJob(ctx, RELEASE_ID, 'prepare')
  await cancelComponentJob(ctx, OPERATION_ID)

  const [startCall, cancelCall] = calls
  assert.ok(startCall)
  assert.ok(cancelCall)
  assert.deepEqual(startCall, {
    path: '/component-jobs',
    options: {
      method: 'POST',
      timeoutMs: 30_000,
      body: { release_id: RELEASE_ID, action: 'prepare' },
    },
  })
  assert.deepEqual(cancelCall, {
    path: `/component-jobs/${OPERATION_ID}/cancel`,
    options: { method: 'POST', timeoutMs: 30_000 },
  })
})

test('component client localizes job snapshots for another request identity', async () => {
  const otherOperation = 'a836c2a8-6dbd-4b48-a4e7-157b891f763f'
  const ctx: RestBridgeContext = {
    i18n: TEST_I18N,
    async rest(path) {
      if (path === '/component-jobs') return { ...job(), release_id: 'b'.repeat(64) }
      return { ...job(), operation_id: otherOperation }
    },
  }

  await assert.rejects(
    startComponentJob(ctx, RELEASE_ID, 'prepare'),
    hasTransportError,
  )
  await assert.rejects(
    getComponentJob(ctx, OPERATION_ID),
    hasTransportError,
  )
  await assert.rejects(
    cancelComponentJob(ctx, OPERATION_ID),
    hasTransportError,
  )
})

function hasTransportError(error: unknown): error is ToqraqApiError {
  return error instanceof ToqraqApiError && error.code === 'transport.unavailable'
}
