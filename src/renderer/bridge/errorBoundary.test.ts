import assert from 'node:assert/strict'
import test from 'node:test'
import { ToqraqApiError, unwrap } from './errorBoundary.js'

const TEST_TRANSLATIONS: Readonly<Record<string, (args: readonly unknown[]) => string>> = Object.freeze({
  'errors.session.not_found': () => 'The game session was not found.',
  'failure.transportUnavailable': () => 'The Toqraq connection is unavailable.',
  'failure.withTraceId': ([message, traceId]) => `${String(message)} Trace: ${String(traceId)}`,
})

function translate(key: string, ...args: unknown[]): string {
  const render = TEST_TRANSLATIONS[key]
  assert.ok(render, `unexpected translation key: ${key}`)
  return render(args)
}

test('unwrap returns successful payload unchanged', () => {
  const value = { ok: true }
  assert.equal(unwrap(value, translate), value)
})

test('unwrap raises structured API errors', () => {
  const traceId = '8f489b96-c438-4d13-a54d-9e3f1020f531'
  assert.throws(
    () =>
      unwrap(
        {
          error: {
            code: 'session.not_found',
            category: 'not_found',
            parameters: { session_id: 'session-1' },
            details: { reason: 'not_owned' },
            trace_id: traceId,
          },
        },
        translate,
      ),
    (error) =>
      error instanceof ToqraqApiError &&
      error.code === 'session.not_found' &&
      error.category === 'not_found' &&
      error.traceId === traceId &&
      error.message === `The game session was not found. Trace: ${traceId}`,
  )
})

test('unwrap rejects malformed error objects', () => {
  assert.throws(
    () => unwrap({ error: 'failure' }, translate),
    (error) =>
      error instanceof ToqraqApiError &&
      error.code === 'transport.unavailable' &&
      error.message.startsWith('The Toqraq connection is unavailable.') &&
      error.cause === undefined,
  )
})

test('unwrap rejects extra envelope and error fields', () => {
  const error = {
    code: 'session.not_found',
    category: 'not_found',
    parameters: {},
    details: {},
    trace_id: '8f489b96-c438-4d13-a54d-9e3f1020f531',
  }
  assert.throws(() => unwrap({ error, extra: true }, translate), hasTransportError)
  assert.throws(
    () => unwrap({ error: { ...error, message: 'unsafe' } }, translate),
    hasTransportError,
  )
})

test('unwrap requires a canonical UUID4 with the RFC variant', () => {
  const error = {
    code: 'session.not_found',
    category: 'not_found',
    parameters: {},
    details: {},
  }
  assert.throws(
    () =>
      unwrap(
        { error: { ...error, trace_id: 'f47ac10b-58cc-11cf-a447-001122334455' } },
        translate,
      ),
    hasTransportError,
  )
  assert.throws(
    () =>
      unwrap(
        { error: { ...error, trace_id: '8f489b96-c438-4d13-754d-9e3f1020f531' } },
        translate,
      ),
    hasTransportError,
  )
})

test('unwrap rejects unsafe integers before JavaScript can round them', () => {
  assert.throws(
    () =>
      unwrap(
        {
          error: {
            code: 'session.not_found',
            category: 'not_found',
            parameters: { sequence: Number.MAX_SAFE_INTEGER + 1 },
            details: {},
            trace_id: '8f489b96-c438-4d13-a54d-9e3f1020f531',
          },
        },
        translate,
      ),
    hasTransportError,
  )
})

test('unwrap measures text and nesting like the Python contract', () => {
  const failure = {
    code: 'session.not_found',
    category: 'not_found',
    details: {},
    trace_id: '8f489b96-c438-4d13-a54d-9e3f1020f531',
  }
  assert.throws(
    () =>
      unwrap(
        { error: { ...failure, parameters: { value: '🎮'.repeat(512) } } },
        translate,
      ),
    (error) => error instanceof ToqraqApiError && error.code === 'session.not_found',
  )
  assert.throws(
    () =>
      unwrap(
        { error: { ...failure, parameters: { value: '🎮'.repeat(513) } } },
        translate,
      ),
    hasTransportError,
  )
  assert.throws(
    () => unwrap({ error: { ...failure, parameters: { value: [[[[1]]]] } } }, translate),
    hasTransportError,
  )
})

test('unwrap neither invokes accessors nor accepts prototype-sensitive keys', () => {
  let reads = 0
  const envelope = {}
  Object.defineProperty(envelope, 'error', {
    enumerable: true,
    get() {
      reads += 1
      throw new Error('must not execute')
    },
  })
  assert.throws(() => unwrap(envelope, translate), hasTransportError)
  assert.equal(reads, 0)

  const parameters = JSON.parse('{"__proto__":{"polluted":true}}')
  assert.throws(
    () =>
      unwrap(
        {
          error: {
            code: 'session.not_found',
            category: 'not_found',
            parameters,
            details: {},
            trace_id: '8f489b96-c438-4d13-a54d-9e3f1020f531',
          },
        },
        translate,
      ),
    hasTransportError,
  )
  assert.equal(Object.hasOwn({}, 'polluted'), false)
})

test('unwrap neither invokes array accessors nor accepts sparse arrays', () => {
  let reads = 0
  const hostile = [null]
  Object.defineProperty(hostile, '0', {
    enumerable: true,
    get() {
      reads += 1
      throw new Error('must not execute')
    },
  })
  const failure = {
    code: 'session.not_found',
    category: 'not_found',
    details: {},
    trace_id: '8f489b96-c438-4d13-a54d-9e3f1020f531',
  }
  assert.throws(
    () => unwrap({ error: { ...failure, parameters: { hostile } } }, translate),
    hasTransportError,
  )
  assert.equal(reads, 0)

  const sparse = Array(1)
  assert.throws(
    () => unwrap({ error: { ...failure, parameters: { sparse } } }, translate),
    hasTransportError,
  )
})

function hasTransportError(error: unknown): error is ToqraqApiError {
  return error instanceof ToqraqApiError && error.code === 'transport.unavailable'
}
