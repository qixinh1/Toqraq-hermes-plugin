import assert from 'node:assert/strict'
import test from 'node:test'
import {
  decodeActiveComponentJobs,
  decodeComponentJob,
  decodeComponentList,
} from './componentDecoders.js'

const OPERATION_ID = '8f489b96-c438-4d13-a54d-9e3f1020f531'
const RELEASE_ID = 'a'.repeat(64)

function release() {
  return {
    release_id: RELEASE_ID,
    component_id: 'engine.godot',
    kind: 'engine',
    label: 'Godot Engine',
    version: '4.5.0',
    build_id: 'toqraq-1',
    platform: 'windows',
    architecture: 'x86_64',
    package_bytes: 100,
    installed_bytes: 200,
    package_sha256: 'b'.repeat(64),
    source: {
      publisher: 'Godot Engine',
      package_url: 'https://downloads.example/godot.zip',
      provenance_url: 'https://example/provenance',
    },
    license: {
      identifier: 'MIT',
      name: 'MIT License',
      url: 'https://example/license',
      acceptance_required: false,
    },
    authentication_required: false,
    capabilities: ['runtime.launch', 'runtime.preview'],
    readiness: 'missing',
    in_use: false,
  }
}

function job(overrides = {}) {
  return {
    operation_id: OPERATION_ID,
    release_id: RELEASE_ID,
    component_id: 'engine.godot',
    action: 'prepare',
    state: 'running',
    phase: 'downloading',
    completed_bytes: 25,
    total_bytes: 100,
    revision: 2,
    error: null,
    ...overrides,
  }
}

function failure() {
  return {
    code: 'component.download_failed',
    category: 'upstream',
    parameters: { component_id: 'engine.godot' },
    details: { retryable: true, attempts: [1, 2] },
    trace_id: 'a836c2a8-6dbd-4b48-a4e7-157b891f763f',
  }
}

test('component list decoder makes a detached deeply frozen copy', () => {
  const source = { releases: [release()] }
  const decoded = decodeComponentList(source)
  const sourceRelease = source.releases[0]
  const decodedRelease = decoded.releases[0]
  assert.ok(sourceRelease)
  assert.ok(decodedRelease)
  sourceRelease.source.publisher = 'changed'
  sourceRelease.capabilities.push('late')

  assert.equal(decodedRelease.source.publisher, 'Godot Engine')
  assert.deepEqual(decodedRelease.capabilities, ['runtime.launch', 'runtime.preview'])
  assert.ok(Object.isFrozen(decoded))
  assert.ok(Object.isFrozen(decoded.releases))
  assert.ok(Object.isFrozen(decodedRelease))
  assert.ok(Object.isFrozen(decodedRelease.source))
  assert.ok(Object.isFrozen(decodedRelease.license))
  assert.ok(Object.isFrozen(decodedRelease.capabilities))
  assert.throws(
    () => Reflect.apply(Array.prototype.push, decodedRelease.capabilities, ['mutate']),
    TypeError,
  )
})

test('component list decoder rejects extras, unsafe values, and invalid enums', () => {
  assert.throws(() => decodeComponentList({ releases: [], extra: true }), TypeError)
  assert.throws(
    () => decodeComponentList({ releases: [{ ...release(), package_bytes: 0 }] }),
    TypeError,
  )
  assert.throws(
    () =>
      decodeComponentList({
        releases: [{ ...release(), installed_bytes: Number.MAX_SAFE_INTEGER + 1 }],
      }),
    TypeError,
  )

  const invalidFields: ReadonlyArray<readonly [string, unknown]> = [
    ['kind', 'runtime'],
    ['readiness', 'installing'],
    ['in_use', 'yes'],
  ]
  for (const [field, value] of invalidFields) {
    assert.throws(
      () => decodeComponentList({ releases: [{ ...release(), [field]: value }] }),
      TypeError,
    )
  }
})

test('component decoders reject accessors and prototype-sensitive keys without reading them', () => {
  let reads = 0
  const hostile = release()
  Object.defineProperty(hostile, 'label', {
    enumerable: true,
    get() {
      reads += 1
      return 'unsafe'
    },
  })
  assert.throws(() => decodeComponentList({ releases: [hostile] }), TypeError)
  assert.equal(reads, 0)

  const polluted = release()
  Object.defineProperty(polluted, '__proto__', { enumerable: true, value: { polluted: true } })
  assert.throws(() => decodeComponentList({ releases: [polluted] }), TypeError)
  assert.equal(Object.hasOwn({}, 'polluted'), false)

  const inherited = Object.create({ inherited: true })
  Object.assign(inherited, job())
  assert.throws(() => decodeComponentJob(inherited), TypeError)
})

test('component job decoder copies and freezes a valid public failure', () => {
  const error = failure()
  const decoded = decodeComponentJob(
    job({ state: 'failed', phase: 'verifying', revision: 4, error }),
  )
  error.details.attempts.push(3)
  error.parameters.component_id = 'changed'

  assert.equal(decoded.error?.code, 'component.download_failed')
  assert.deepEqual(decoded.error?.details.attempts, [1, 2])
  assert.equal(decoded.error?.parameters.component_id, 'engine.godot')
  assert.ok(Object.isFrozen(decoded))
  assert.ok(Object.isFrozen(decoded.error))
  assert.ok(Object.isFrozen(decoded.error?.parameters))
  assert.ok(Object.isFrozen(decoded.error?.details))
  assert.ok(Object.isFrozen(decoded.error?.details.attempts))

  const withoutOptionalError = job()
  Reflect.deleteProperty(withoutOptionalError, 'error')
  assert.equal(decodeComponentJob(withoutOptionalError).error, null)
})

test('component job decoder rejects malformed public errors and extra fields', () => {
  assert.throws(() => decodeComponentJob({ ...job(), extra: true }), TypeError)
  assert.throws(
    () =>
      decodeComponentJob(
        job({
          state: 'failed',
          error: { ...failure(), message: 'uncontracted prose' },
        }),
      ),
    TypeError,
  )

  let reads = 0
  const error = failure()
  Object.defineProperty(error, 'details', {
    enumerable: true,
    get() {
      reads += 1
      return {}
    },
  })
  assert.throws(() => decodeComponentJob(job({ state: 'failed', error })), TypeError)
  assert.equal(reads, 0)
})

test('component job decoder rejects unsafe numbers and unknown enum values', () => {
  const invalidFields: ReadonlyArray<readonly [string, unknown]> = [
    ['completed_bytes', -1],
    ['total_bytes', Number.MAX_SAFE_INTEGER + 1],
    ['revision', 0],
    ['action', 'repair'],
    ['state', 'complete'],
    ['phase', 'publishing'],
  ]
  for (const [field, value] of invalidFields) {
    assert.throws(() => decodeComponentJob(job({ [field]: value })), TypeError)
  }
})

test('component job decoder rejects incoherent action, state, phase, and progress', () => {
  const invalidJobs = [
    job({ action: 'prepare', phase: 'removing' }),
    job({ action: 'remove', phase: 'downloading' }),
    job({ state: 'queued', phase: 'downloading' }),
    job({ state: 'ready', phase: 'verifying', completed_bytes: 100 }),
    job({ state: 'running', phase: 'ready', completed_bytes: 100 }),
    job({ state: 'ready', phase: 'ready', completed_bytes: 99 }),
    job({ state: 'failed', phase: 'verifying', error: null }),
    job({ state: 'running', error: failure() }),
    job({ completed_bytes: 101 }),
  ]
  for (const value of invalidJobs) assert.throws(() => decodeComponentJob(value), TypeError)

  const ready = decodeComponentJob(
    job({ state: 'ready', phase: 'ready', completed_bytes: 100, revision: 5 }),
  )
  assert.equal(ready.state, 'ready')
})

test('active component jobs decoder preserves order and deeply freezes snapshots', () => {
  const secondOperation = 'a836c2a8-6dbd-4b48-a4e7-157b891f763f'
  const secondRelease = 'c'.repeat(64)
  const source = {
    jobs: [
      job(),
      job({
        operation_id: secondOperation,
        release_id: secondRelease,
        component_id: 'bridge.godot',
        state: 'cancelling',
      }),
    ],
  }

  const decoded = decodeActiveComponentJobs(source)
  const sourceJob = source.jobs[0]
  const decodedJob = decoded.jobs[0]
  assert.ok(sourceJob)
  assert.ok(decodedJob)
  sourceJob.completed_bytes = 99

  assert.deepEqual(
    decoded.jobs.map((snapshot) => snapshot.operation_id),
    [OPERATION_ID, secondOperation],
  )
  assert.equal(decodedJob.completed_bytes, 25)
  assert.ok(Object.isFrozen(decoded))
  assert.ok(Object.isFrozen(decoded.jobs))
  assert.ok(Object.isFrozen(decodedJob))
})

test('active component jobs decoder rejects terminal, duplicate, and extra entries', () => {
  const secondOperation = 'a836c2a8-6dbd-4b48-a4e7-157b891f763f'
  const secondRelease = 'c'.repeat(64)
  assert.throws(
    () =>
      decodeActiveComponentJobs({
        jobs: [job({ state: 'ready', phase: 'ready', completed_bytes: 100 })],
      }),
    TypeError,
  )
  assert.throws(
    () =>
      decodeActiveComponentJobs({
        jobs: [job(), job({ release_id: secondRelease })],
      }),
    TypeError,
  )
  assert.throws(
    () =>
      decodeActiveComponentJobs({
        jobs: [job(), job({ operation_id: secondOperation })],
      }),
    TypeError,
  )
  assert.throws(
    () => decodeActiveComponentJobs({ jobs: [], internal_tasks: [] }),
    TypeError,
  )
})
