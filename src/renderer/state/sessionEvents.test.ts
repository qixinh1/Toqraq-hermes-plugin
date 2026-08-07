import assert from 'node:assert/strict'
import test from 'node:test'
import { openEvents } from '../bridge/sessionEventClient.js'
import type { EventsBridgeContext } from '../bridge/sessionEventClient.js'
import type { ToqraqApiError } from '../bridge/errorBoundary.js'
import type {
  SessionProcessState,
  SessionResult,
  SessionStateEvent,
} from '../contracts/generated.js'
import { createSessionEventConsumer } from './sessionEvents.js'

const TEST_I18N: EventsBridgeContext['i18n'] = Object.freeze({
  t(key: string, ...args: unknown[]): string {
    if (key === 'failure.transportUnavailable') return 'The Toqraq connection is unavailable.'
    if (key === 'failure.withTraceId') return `${String(args[0])} Trace: ${String(args[1])}`
    throw new Error(`unexpected translation key: ${key}`)
  },
})

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

function session(
  runRevision = 1,
  processState: SessionProcessState = 'running',
): SessionResult {
  const terminal = processState === 'ended' || processState === 'crashed'
  return Object.freeze({
    id: 'session-1',
    run_revision: runRevision,
    runtime: Object.freeze({
      engine: 'godot',
      version: '4.7.1',
      build_id: 'godot-4.7.1+toqraq.1',
      distribution_id: 'toqraq.windows',
      platform: 'windows',
      architecture: 'x86_64',
    }),
    project_dir: 'D:/game',
    root_pid: 42,
    process_state: processState,
    alive: !terminal,
    exit_code: terminal ? 0 : null,
    started_at: 10,
    bridge: Object.freeze({
      id: 'toqraq.bridge',
      protocol: '1.0',
      capabilities: Object.freeze([]),
    }),
    capabilities: Object.freeze(['toqraq.preview.display']),
    preview: Object.freeze({ state: 'connecting', error: null, surface: null }),
    perception: Object.freeze({ state: 'connecting', error: null }),
    control: Object.freeze({ state: 'connecting', error: null }),
  })
}

function event(
  sequence: number,
  runRevision = 1,
  processState: SessionProcessState = 'running',
  type: SessionStateEvent['type'] = 'session.readiness',
): SessionStateEvent {
  return Object.freeze({
    session_id: 'session-1',
    sequence,
    timestamp: 10 + sequence,
    type,
    payload: session(runRevision, processState),
  })
}

interface StateOwner {
  values: Array<SessionResult | null>
  get(): SessionResult | null
  apply(value: SessionResult): boolean
  clear(sessionId: string, runRevision: number): boolean
}

function stateOwner(initial: SessionResult | null = null): StateOwner {
  let current = initial
  const values: Array<SessionResult | null> = []
  return {
    values,
    get: () => current,
    apply(value) {
      if (current !== null && current.run_revision > value.run_revision) return false
      current = value
      values.push(value)
      return true
    },
    clear(_sessionId, runRevision) {
      if (current === null || current.run_revision > runRevision) return false
      current = null
      values.push(null)
      return true
    },
  }
}

test('first event and sequence gap reconcile while contiguous events apply directly', async () => {
  const firstTruth = session(1, 'running')
  const gapTruth = session(1, 'stopping')
  const reads = [firstTruth, gapTruth]
  const owner = stateOwner()
  let readCount = 0
  let ended = 0
  const terminal: SessionResult[] = []
  const consumer = createSessionEventConsumer({
    sessionId: 'session-1',
    read: async () => reads[readCount++] ?? null,
    ...owner,
    onEnded: (session) => {
      ended += 1
      terminal.push(session)
    },
  })

  await consumer.accept(event(4, 1, 'paused'))
  assert.equal(owner.values.at(-1), firstTruth)
  assert.equal(readCount, 1)

  const paused = event(5, 1, 'paused')
  await consumer.accept(paused)
  assert.equal(owner.values.at(-1), paused.payload)

  await consumer.accept(event(7, 1, 'running'))
  assert.equal(owner.values.at(-1), gapTruth)
  assert.equal(readCount, 2)

  await consumer.accept(event(6, 1, 'running'))
  assert.equal(owner.values.at(-1), gapTruth)

  await consumer.accept(event(8, 1, 'ended', 'session.stopped'))
  assert.equal(owner.values.at(-1), null)
  assert.equal(ended, 1)
  assert.equal(terminal[0]?.process_state, 'ended')
})

test('terminal callback preserves crash classification and exit code', async () => {
  const owner = stateOwner(session(1))
  const terminal: SessionResult[] = []
  const consumer = createSessionEventConsumer({
    sessionId: 'session-1',
    read: async () => owner.get(),
    ...owner,
    onEnded: (session) => {
      terminal.push(session)
    },
  })
  await consumer.reconcile()
  const crashed = {
    ...session(1, 'crashed'),
    exit_code: 23,
  } satisfies SessionResult

  await consumer.accept({
    session_id: 'session-1',
    sequence: 1,
    timestamp: 11,
    type: 'session.stopped',
    payload: crashed,
  })

  assert.equal(terminal[0]?.process_state, 'crashed')
  assert.equal(terminal[0]?.exit_code, 23)
})

test('old-run readiness and stop events cannot mutate a replacement run', async () => {
  const owner = stateOwner(session(1))
  let ended = 0
  const consumer = createSessionEventConsumer({
    sessionId: 'session-1',
    read: async () => owner.get(),
    ...owner,
    onEnded: () => {
      ended += 1
    },
  })
  await consumer.reconcile()

  const replacement = event(2, 2, 'running', 'session.started')
  await consumer.accept(replacement)
  assert.equal(owner.get()?.run_revision, 2)

  await consumer.accept(event(3, 1, 'running', 'session.readiness'))
  await consumer.accept(event(4, 1, 'ended', 'session.stopped'))

  assert.equal(owner.get(), replacement.payload)
  assert.equal(ended, 0)
})

test('a null REST response cannot clear a run published after the read began', async () => {
  const owner = stateOwner(session(1))
  const readStarted = deferred<void>()
  const read = deferred<SessionResult | null>()
  const consumer = createSessionEventConsumer({
    sessionId: 'session-1',
    read: async () => {
      readStarted.resolve()
      return read.promise
    },
    ...owner,
  })

  const reconciling = consumer.reconcile()
  await readStarted.promise
  owner.apply(session(2))
  read.resolve(null)
  await reconciling

  assert.equal(owner.get()?.run_revision, 2)
})

test('explicit recovery reconciles malformed-frame or reconnect state', async () => {
  const truth = session(2, 'paused')
  const owner = stateOwner()
  let readCount = 0
  const consumer = createSessionEventConsumer({
    sessionId: 'session-1',
    read: async () => {
      readCount += 1
      return truth
    },
    ...owner,
  })
  await consumer.reconcile()
  assert.equal(owner.get(), truth)

  consumer.close()
  await consumer.accept(event(1))
  await consumer.reconcile()
  assert.equal(owner.values.length, 1)
  assert.equal(readCount, 1)
})

test('malformed socket frame drives the consumer recovery path', async () => {
  let socketMessage = (_value: unknown): void => {}
  let socketPath = ''
  let reads = 0
  let recovery: Promise<void> = Promise.resolve()
  const truth = session()
  const owner = stateOwner()
  const consumer = createSessionEventConsumer({
    sessionId: 'session-1',
    read: async () => {
      reads += 1
      return truth
    },
    ...owner,
  })
  const ctx: EventsBridgeContext = {
    i18n: TEST_I18N,
    socket(path, callback) {
      socketPath = path
      socketMessage = callback
      return () => {}
    },
  }
  openEvents(
    ctx,
    'session-1',
    (value) => consumer.accept(value),
    () => {
      recovery = consumer.reconcile()
    },
  )

  socketMessage({ malformed: true })
  await recovery
  assert.equal(socketPath, '/sessions/session-1/events')
  assert.equal(reads, 1)
})

test('asynchronous socket consumer failures are observed as transport errors', async () => {
  let socketMessage = (_value: unknown): void => {}
  const reported: ToqraqApiError[] = []
  const ctx: EventsBridgeContext = {
    i18n: TEST_I18N,
    socket(_path, callback) {
      socketMessage = callback
      return () => {}
    },
  }
  openEvents(
    ctx,
    'session-1',
    async () => {
      throw new Error('private callback failure')
    },
    (error) => {
      reported.push(error)
    },
  )

  socketMessage(event(1))
  await new Promise<void>((resolve) => setImmediate(resolve))
  assert.equal(reported[0]?.code, 'transport.unavailable')
})
