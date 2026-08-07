import assert from 'node:assert/strict'
import test from 'node:test'
import { ToqraqApiError } from './errorBoundary.js'
import { getSession, startSession, stopSession } from './sessionClient.js'
import { sessionResult } from './sessionResult.fixture.js'
import type { RestBridgeContext, RestRequestOptions } from './transport.js'

const TEST_I18N = Object.freeze({ t: () => 'Localized test message.' })

interface RestCall {
  readonly path: string
  readonly options: RestRequestOptions
}

test('session start is a bounded launch request, not a component download', async () => {
  let call: RestCall | undefined
  const ctx: RestBridgeContext = {
    i18n: TEST_I18N,
    rest: async (path, options) => {
      call = { path, options: options ?? {} }
      return sessionResult()
    },
  }

  await startSession(ctx, { projectDir: 'D:/game', hermesSession: 'session-1' })
  assert.ok(call)
  assert.equal(call.path, '/sessions')
  assert.equal(call.options.timeoutMs, 30_000)
  assert.deepEqual(call.options.body, {
    project_dir: 'D:/game',
    hermes_session: 'session-1',
  })
})

test('owned game lookup accepts an ordinary null result', async () => {
  let call: RestCall | undefined
  const ctx: RestBridgeContext = {
    i18n: TEST_I18N,
    rest: async (path, options) => {
      call = { path, options: options ?? {} }
      return null
    },
  }

  assert.equal(await getSession(ctx, 'session-1'), null)
  assert.ok(call)
  assert.equal(call.path, '/sessions/session-1')
  assert.ok((call.options.timeoutMs ?? 0) >= 30_000)
})

test('session stop is conditional on the exact observed run revision', async () => {
  let call: RestCall | undefined
  const ctx: RestBridgeContext = {
    i18n: TEST_I18N,
    rest: async (path, options) => {
      call = { path, options: options ?? {} }
      return sessionResult()
    },
  }

  await stopSession(ctx, 'session-1', 2)
  assert.ok(call)
  assert.equal(call.path, '/sessions/session-1')
  assert.equal(call.options.method, 'DELETE')
  assert.deepEqual(call.options.body, { run_revision: 2 })
})

test('session stop rejects a terminal response for another run revision', async () => {
  const ctx: RestBridgeContext = {
    i18n: TEST_I18N,
    rest: async () => ({ ...sessionResult(), run_revision: 3 }),
  }
  await assert.rejects(stopSession(ctx, 'session-1', 2), hasTransportError)
})

test('malformed successful responses become localized transport failures', async () => {
  for (const response of [{ broken: true }, { ...sessionResult(), id: 'another-session' }]) {
    const ctx: RestBridgeContext = { i18n: TEST_I18N, rest: async () => response }
    await assert.rejects(
      startSession(ctx, { projectDir: 'D:/game', hermesSession: 'session-1' }),
      hasTransportError,
    )
  }
})

function hasTransportError(error: unknown): error is ToqraqApiError {
  return error instanceof ToqraqApiError && error.code === 'transport.unavailable'
}
