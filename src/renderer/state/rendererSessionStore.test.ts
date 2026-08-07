import assert from 'node:assert/strict'
import test from 'node:test'
import { decodeSession } from '../bridge/sessionDecoders.js'
import type { SessionResult } from '../contracts/generated.js'
import { projectOwnedHermesSession } from './hermesSessionReadiness.js'
import { RendererSessionStore } from './rendererSessionStore.js'
import type { RendererAtom } from './rendererSessionStore.js'

function memoryAtom<Value>(initialValue: Value): RendererAtom<Value> {
  let value = initialValue
  return {
    init: initialValue,
    lc: 0,
    value: initialValue,
    get: () => value,
    set(nextValue) {
      value = nextValue
    },
    listen(_listener) {
      return () => {}
    },
    subscribe(_subscriber) {
      return () => {}
    },
    notify() {},
    off() {},
  }
}

interface Deferred<Value> {
  promise: Promise<Value>
  resolve(value: Value): void
}

function deferred<Value>(): Deferred<Value> {
  let resolve = (_value: Value): void => {
    throw new Error('deferred promise was not initialized')
  }
  const promise = new Promise<Value>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

test('plugin incarnations isolate selected sessions, revisions, and busy state', () => {
  const first = new RendererSessionStore(memoryAtom)
  const second = new RendererSessionStore(memoryAtom)
  first.applyHermesReadiness(ready('session-1'))
  second.applyHermesReadiness(ready('session-1'))

  const operation = first.beginSessionOperation('session-1')
  assert.ok(operation)
  assert.equal(first.busyState.get(), true)
  assert.equal(second.busyState.get(), false)

  const current = session(2)
  assert.equal(first.applySessionSnapshot(current), true)
  assert.equal(first.applySessionSnapshot(session(1)), false)
  assert.equal(first.currentSession(), current)
  assert.equal(second.currentSession(), null)
  assert.equal(first.clearSessionRun('session-1', 1), false)
  assert.equal(first.clearSessionRun('session-1', 2), true)
  assert.equal(first.currentSession(), null)

  assert.equal(first.finishSessionOperation(operation), true)
  assert.equal(first.busyState.get(), false)
})

test('selection changes clear snapshots while preserving the exact old operation owner', () => {
  const store = new RendererSessionStore(memoryAtom)
  store.applyHermesReadiness(ready('session-1'))
  const operation = store.beginSessionOperation('session-1')
  assert.ok(operation)
  store.applySessionSnapshot(session(1))

  assert.equal(store.applyHermesReadiness(ready('session-2')), true)
  assert.equal(store.currentSession(), null)
  assert.equal(store.busyState.get(), false)
  assert.equal(store.ownsSelectedSessionOperation(operation), false)

  assert.equal(store.applyHermesReadiness(ready('session-1')), true)
  assert.equal(store.busyState.get(), true)
  assert.equal(store.ownsSelectedSessionOperation(operation), true)
  assert.equal(store.finishSessionOperation(operation), true)
})

test('dispose clears presentation and permanently rejects late settlements', async () => {
  const store = new RendererSessionStore(memoryAtom)
  store.applyHermesReadiness(ready('session-1'))
  const operation = store.beginSessionOperation('session-1')
  assert.ok(operation)
  assert.equal(store.applySessionSnapshot(session(1)), true)

  const request = deferred<SessionResult>()
  const settlement = request.promise.then((result) => ({
    applied: store.applySessionSnapshot(result),
    finished: store.finishSessionOperation(operation),
  }))

  store.dispose()
  store.dispose()
  assert.equal(store.active, false)
  assert.equal(store.gameState.get().session, null)
  assert.equal(store.busyState.get(), false)
  assert.equal(store.currentSession(), null)
  assert.equal(store.ownsSelectedSessionOperation(operation), false)

  request.resolve(session(2))
  assert.deepEqual(await settlement, { applied: false, finished: false })
  assert.equal(store.gameState.get().session, null)
  assert.equal(store.beginSessionOperation('session-1'), null)
  assert.equal(store.applyHermesReadiness(ready('session-1')), false)
  assert.equal(store.clearSessionRun('session-1', 2), false)
})

test('one projection combines readiness, REST state, and the selected snapshot', () => {
  const store = new RendererSessionStore(memoryAtom)
  assert.deepEqual(store.currentGame(), {
    readiness: { sessionId: null, status: 'needed' },
    sessionRead: 'ready',
    session: null,
  })

  store.applyHermesReadiness(ready('session-1'))
  assert.equal(store.currentGame().sessionRead, 'checking')
  assert.equal(store.applySessionReadStatus('another-session', 'ready'), false)
  assert.equal(store.applySessionReadStatus('session-1', 'unavailable'), true)
  const current = session(2)
  store.applySessionSnapshot(current)
  assert.deepEqual(store.currentGame(), {
    readiness: { sessionId: 'session-1', status: 'ready' },
    sessionRead: 'unavailable',
    session: current,
  })

  store.applyHermesReadiness(projectOwnedHermesSession('session-1', true, 'error'))
  assert.equal(store.currentGame().session, null)
  assert.equal(store.currentGame().sessionRead, 'unavailable')
})

function ready(sessionId: string) {
  return projectOwnedHermesSession(sessionId, true, 'success')
}

function session(runRevision: number): SessionResult {
  return decodeSession({
    id: 'session-1',
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
    process_state: 'running',
    alive: true,
    exit_code: null,
    started_at: 10,
    bridge: { id: 'toqraq.bridge', protocol: '1.0', capabilities: [] },
    capabilities: ['toqraq.preview.display'],
    preview: { state: 'connecting', error: null, surface: null },
    perception: { state: 'connecting', error: null },
    control: { state: 'connecting', error: null },
  })
}
