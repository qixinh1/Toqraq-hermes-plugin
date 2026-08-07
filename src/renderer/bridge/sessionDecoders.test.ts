import assert from 'node:assert/strict'
import test from 'node:test'
import { decodeSession, decodeSessionEvent } from './sessionDecoders.js'

function session(overrides = {}) {
  return {
    id: 'session-1',
    run_revision: 2,
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
    process_state: 'running',
    alive: true,
    exit_code: null,
    started_at: 10.5,
    bridge: {
      id: 'toqraq.bridge',
      protocol: '1.0',
      capabilities: ['toqraq.control.input'],
    },
    capabilities: ['toqraq.control.input', 'toqraq.preview.display'],
    preview: {
      state: 'ready',
      error: null,
      surface: {
        kind: 'native_window',
        viewport_size: { width: 960, height: 540 },
      },
    },
    perception: { state: 'ready', error: null },
    control: { state: 'ready', error: null },
    ...overrides,
  }
}

test('session decoder copies the complete nested snapshot into frozen data', () => {
  const source = session()
  const decoded = decodeSession(source)
  source.capabilities.push('toqraq.zzz')
  source.preview.surface.viewport_size.width = 1

  assert.equal(decoded.runtime.build_id, 'godot-4.7.1+toqraq.1')
  assert.equal(decoded.bridge.capabilities[0], 'toqraq.control.input')
  assert.deepEqual(decoded.preview.surface?.viewport_size, { width: 960, height: 540 })
  assert.ok(Object.isFrozen(decoded))
  assert.ok(Object.isFrozen(decoded.runtime))
  assert.ok(Object.isFrozen(decoded.bridge.capabilities))
  assert.ok(Object.isFrozen(decoded.preview.surface?.viewport_size))
})

test('session decoder enforces process, readiness, and capability invariants', () => {
  assert.throws(
    () => decodeSession(session({ process_state: 'ended', alive: false, exit_code: null })),
    TypeError,
  )
  assert.throws(
    () => decodeSession(session({ preview: { state: 'ready', error: null, surface: null } })),
    TypeError,
  )
  assert.throws(
    () => decodeSession(session({ control: { state: 'ready', error: { malformed: true } } })),
    TypeError,
  )
  assert.throws(
    () =>
      decodeSession(
        session({
          bridge: {
            id: 'toqraq.bridge',
            protocol: '1.0',
            capabilities: ['toqraq.observe.frame'],
          },
        }),
      ),
    TypeError,
  )
  assert.throws(
    () =>
      decodeSession(
        session({ capabilities: ['toqraq.preview.display', 'toqraq.control.input'] }),
      ),
    TypeError,
  )
})

test('session decoder accepts contract-optional null fields when omitted', () => {
  const value = session({
    preview: {
      state: 'connecting',
    },
    perception: { state: 'unavailable' },
    control: { state: 'connecting' },
  })

  const decoded = decodeSession(value)

  assert.deepEqual(decoded.preview, { state: 'connecting', error: null, surface: null })
  assert.deepEqual(decoded.perception, { state: 'unavailable', error: null })
})

test('session decoder rejects extras, unsafe numbers, and accessors without reading them', () => {
  assert.throws(() => decodeSession({ ...session(), native_window_id: 123 }), TypeError)
  assert.throws(() => decodeSession(session({ root_pid: Number.MAX_SAFE_INTEGER + 1 })), TypeError)
  assert.throws(() => decodeSession(session({ started_at: Number.NaN })), TypeError)

  let reads = 0
  const hostile = session()
  Object.defineProperty(hostile, 'root_pid', {
    enumerable: true,
    get() {
      reads += 1
      return 42
    },
  })
  assert.throws(() => decodeSession(hostile), TypeError)
  assert.equal(reads, 0)
})

test('event decoder accepts all five event types and enforces revision-bound owners', () => {
  for (const type of [
    'session.started',
    'session.readiness',
    'session.process_state',
    'session.stopped',
  ]) {
    const decoded = decodeSessionEvent({
      session_id: 'session-1',
      sequence: 2,
      timestamp: 10.5,
      type,
      payload: session(),
    })
    assert.equal(decoded.type, type)
    assert.notEqual(decoded.type, 'session.failed')
    if (decoded.type === 'session.failed') assert.fail('expected a state event')
    assert.equal(decoded.payload.run_revision, 2)
    assert.ok(Object.isFrozen(decoded))
  }

  const failed = decodeSessionEvent({
    session_id: 'session-1',
    sequence: 3,
    timestamp: 11,
    type: 'session.failed',
    payload: {
      session: session({ process_state: 'stopping' }),
      error: {
        code: 'runtime.termination_failed',
        category: 'upstream',
        parameters: {},
        details: { retryable: true },
        trace_id: '8f489b96-c438-4d13-a54d-9e3f1020f531',
      },
    },
  })
  assert.equal(failed.type, 'session.failed')
  if (failed.type !== 'session.failed') assert.fail('expected a failed event')
  assert.equal(failed.payload.session.run_revision, 2)
  assert.equal(failed.payload.error.code, 'runtime.termination_failed')

  assert.throws(
    () =>
      decodeSessionEvent({
        session_id: 'another-session',
        sequence: 4,
        timestamp: 12,
        type: 'session.readiness',
        payload: session(),
      }),
    TypeError,
  )
})

test('event decoder rejects prototype-sensitive data keys', () => {
  const event = JSON.parse(
    `{"session_id":"session-1","sequence":1,"timestamp":10,"type":"session.readiness","payload":${JSON.stringify(session())},"__proto__":{}}`,
  )
  assert.throws(() => decodeSessionEvent(event), TypeError)
  assert.equal(Object.hasOwn({}, 'polluted'), false)
})
