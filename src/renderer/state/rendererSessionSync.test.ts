import assert from 'node:assert/strict'
import test from 'node:test'
import type { SessionEvent, SessionResult } from '../contracts/generated.js'
import { sessionResult } from '../bridge/sessionResult.fixture.js'
import type { ReadableValue } from './readableValue.js'
import { RendererSessionStore } from './rendererSessionStore.js'
import type { RendererAtom } from './rendererSessionStore.js'
import { startRendererSessionSync } from './rendererSessionSync.js'

interface Deferred<Value> {
  readonly promise: Promise<Value>
  resolve(value: Value): void
  reject(error: Error): void
}

interface Channel {
  readonly owner: string
  readonly onEvent: (event: SessionEvent) => void | Promise<void>
  readonly onError: (error: unknown) => void
  closed: boolean
}

interface Retry {
  readonly run: () => void
  cancelled: boolean
}

class TestValue<Value> implements ReadableValue<Value> {
  readonly #listeners = new Set<(value: Value) => void>()
  #value: Value

  constructor(value: Value) {
    this.#value = value
  }

  get(): Value {
    return this.#value
  }

  set(value: Value): void {
    this.#value = value
    for (const listener of this.#listeners) listener(value)
  }

  subscribe(listener: (value: Value) => void): () => void {
    this.#listeners.add(listener)
    listener(this.#value)
    return () => this.#listeners.delete(listener)
  }

  get listenerCount(): number {
    return this.#listeners.size
  }
}

class SyncHarness {
  readonly active = new TestValue<string | null>('session-1')
  readonly gateway = new TestValue('open')
  readonly store = new RendererSessionStore(memoryAtom)
  readonly statusReads: Array<{ owner: string; request: Deferred<unknown> }> = []
  readonly sessionReads: Array<{ owner: string; request: Deferred<SessionResult | null> }> = []
  readonly cancelledStatuses: string[] = []
  readonly channels: Channel[] = []
  readonly retries: Retry[] = []
  readonly loadErrors: unknown[] = []
  readonly eventErrors: unknown[] = []
  readonly ended: SessionResult[] = []

  start(): () => void {
    return startRendererSessionSync({
      activeSessionId: this.active,
      gateway: this.gateway,
      store: this.store,
      readHermesStatus: (owner) => {
        const request = deferred<unknown>()
        this.statusReads.push({ owner, request })
        return request.promise
      },
      cancelHermesStatus: (owner) => {
        this.cancelledStatuses.push(owner)
      },
      readSession: (owner) => {
        const request = deferred<SessionResult | null>()
        this.sessionReads.push({ owner, request })
        return request.promise
      },
      openEvents: (owner, onEvent, onError) => {
        const channel = { owner, onEvent, onError, closed: false }
        this.channels.push(channel)
        return () => {
          channel.closed = true
        }
      },
      scheduleRetry: (retry) => {
        const scheduled = { run: retry, cancelled: false }
        this.retries.push(scheduled)
        return () => {
          scheduled.cancelled = true
        }
      },
      onLoadError: (error) => this.loadErrors.push(error),
      onEventError: (error) => this.eventErrors.push(error),
      onEnded: (session) => this.ended.push(session),
    })
  }
}

test('plugin owner synchronizes readiness, REST, and events without a pane', async () => {
  const harness = new SyncHarness()
  const dispose = harness.start()
  assert.deepEqual(harness.store.currentGame().readiness, {
    sessionId: null,
    status: 'checking',
  })

  await eventually(() => harness.statusReads.length === 1)
  harness.statusReads[0]?.request.resolve({ ready: true })
  await eventually(() => harness.channels.length === 1 && harness.sessionReads.length === 1)
  harness.sessionReads[0]?.request.resolve(session('session-1', 2, 'running'))
  await eventually(() => harness.store.currentGame().sessionRead === 'ready')
  assert.equal(harness.store.currentSession()?.process_state, 'running')

  await harness.channels[0]?.onEvent(event(session('session-1', 2, 'paused'), 1))
  assert.equal(harness.store.currentSession()?.process_state, 'paused')
  await harness.channels[0]?.onEvent(stoppedEvent(session('session-1', 2, 'ended'), 2))
  assert.equal(harness.store.currentSession(), null)
  assert.equal(harness.ended.length, 1)
  dispose()
  assert.equal(harness.channels[0]?.closed, true)
})

test('owner changes close the old channel and reject its late REST and events', async () => {
  const harness = new SyncHarness()
  const dispose = harness.start()
  await eventually(() => harness.statusReads.length === 1)
  harness.statusReads[0]?.request.resolve({ ready: true })
  await eventually(() => harness.channels.length === 1 && harness.sessionReads.length === 1)

  harness.active.set('session-2')
  assert.equal(harness.channels[0]?.closed, true)
  assert.equal(harness.store.currentSession(), null)
  harness.sessionReads[0]?.request.resolve(session('session-1', 5, 'running'))
  await harness.channels[0]?.onEvent(event(session('session-1', 6, 'paused'), 1))
  await eventually(() => harness.statusReads.length === 2)
  assert.equal(harness.store.currentSession(), null)

  harness.statusReads[1]?.request.resolve({ ready: true })
  await eventually(() => harness.sessionReads.length === 2)
  harness.sessionReads[1]?.request.resolve(session('session-2', 1, 'running'))
  await eventually(() => harness.store.currentSession()?.id === 'session-2')
  assert.deepEqual(harness.cancelledStatuses, ['session-1'])
  dispose()
})

test('Hermes readiness retries without opening a duplicate session channel', async () => {
  const harness = new SyncHarness()
  const dispose = harness.start()
  await eventually(() => harness.statusReads.length === 1)
  harness.statusReads[0]?.request.reject(new Error('gateway unavailable'))
  await eventually(() => harness.retries.length === 1)
  assert.equal(harness.store.currentGame().readiness.status, 'unavailable')
  assert.equal(harness.channels.length, 0)

  harness.retries[0]?.run()
  assert.equal(harness.store.currentGame().readiness.status, 'checking')
  await eventually(() => harness.statusReads.length === 2)
  harness.statusReads[1]?.request.resolve({ ready: true })
  await eventually(() => harness.sessionReads.length === 1)
  harness.sessionReads[0]?.request.resolve(null)
  await eventually(() => harness.store.currentGame().sessionRead === 'ready')
  assert.equal(harness.channels.length, 1)
  assert.equal(harness.loadErrors.length, 0)
  dispose()
})

test('failed selected-session reads retain one bounded retry and one visible error', async () => {
  const harness = new SyncHarness()
  const dispose = harness.start()
  await eventually(() => harness.statusReads.length === 1)
  harness.statusReads[0]?.request.resolve({ ready: true })
  await eventually(() => harness.sessionReads.length === 1)
  harness.sessionReads[0]?.request.reject(new Error('read failed'))
  await eventually(() => harness.retries.length === 1)
  assert.equal(harness.store.currentGame().sessionRead, 'unavailable')
  assert.equal(harness.loadErrors.length, 1)

  harness.retries[0]?.run()
  await eventually(() => harness.sessionReads.length === 2)
  harness.sessionReads[1]?.request.resolve(null)
  await eventually(() => harness.store.currentGame().sessionRead === 'ready')
  assert.equal(harness.loadErrors.length, 1)
  dispose()
})

test('dispose is idempotent, cancels owned work, and rejects late settlement', async () => {
  const harness = new SyncHarness()
  const dispose = harness.start()
  await eventually(() => harness.statusReads.length === 1)
  const before = harness.store.currentGame()
  dispose()
  dispose()
  assert.equal(harness.active.listenerCount, 0)
  assert.equal(harness.gateway.listenerCount, 0)
  assert.deepEqual(harness.cancelledStatuses, ['session-1'])

  harness.statusReads[0]?.request.resolve({ ready: true })
  await Promise.resolve()
  await Promise.resolve()
  assert.equal(harness.channels.length, 0)
  assert.equal(harness.store.currentGame(), before)
})

function event(payload: SessionResult, sequence: number): SessionEvent {
  return {
    session_id: payload.id,
    sequence,
    timestamp: 10 + sequence,
    type: 'session.process_state',
    payload,
  }
}

function stoppedEvent(payload: SessionResult, sequence: number): SessionEvent {
  return {
    session_id: payload.id,
    sequence,
    timestamp: 10 + sequence,
    type: 'session.stopped',
    payload,
  }
}

function session(
  id: string,
  runRevision: number,
  processState: SessionResult['process_state'],
): SessionResult {
  const terminal = processState === 'ended' || processState === 'crashed'
  return {
    ...sessionResult(),
    id,
    run_revision: runRevision,
    process_state: processState,
    alive: !terminal,
    exit_code: terminal ? (processState === 'crashed' ? 23 : 0) : null,
  }
}

function deferred<Value>(): Deferred<Value> {
  let resolve = (_value: Value): void => {
    throw new Error('deferred promise was not initialized')
  }
  let reject = (_error: Error): void => {
    throw new Error('deferred promise was not initialized')
  }
  const promise = new Promise<Value>((done, fail) => {
    resolve = done
    reject = fail
  })
  return { promise, resolve, reject }
}

async function eventually(condition: () => boolean): Promise<void> {
  for (let turn = 0; turn < 20; turn += 1) {
    if (condition()) return
    await new Promise<void>((resolve) => setImmediate(resolve))
  }
  assert.fail('condition did not settle')
}

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
