import assert from 'node:assert/strict'
import test from 'node:test'
import type { ComponentReleaseResult } from '../contracts/generated.js'
import {
  decodeActiveComponentJobs,
  decodeComponentJob,
  decodeComponentList,
} from '../bridge/componentDecoders.js'
import { decodeSetup } from '../bridge/decoders.js'
import {
  componentReleaseIdentity,
  componentReleaseTarget,
  formatExactBytes,
} from '../ui/componentText.js'
import {
  COMPONENT_JOB_POLL_INTERVAL_MS,
  COMPONENT_JOB_RETRY_INTERVAL_MS,
  componentJobPollInterval,
  componentPrepareActionKey,
  componentProgress,
  deriveComponentActions,
  deriveComponentCardState,
  isMissingRecoveredComponentJob,
  nextTerminalComponentOperation,
  resolveSetupComponentPlan,
  selectRecoverableComponentJob,
  shouldAdvanceComponentRecovery,
} from './componentSetup.js'

const RELEASE_ID = 'a'.repeat(64)
const BRIDGE_RELEASE_ID = 'c'.repeat(64)

function release(
  releaseId = RELEASE_ID,
  overrides: Readonly<Record<string, unknown>> = {},
): Readonly<Record<string, unknown>> {
  return {
    release_id: releaseId,
    component_id: 'engine.godot',
    kind: 'engine',
    label: 'Godot 4.5.0',
    version: '4.5.0',
    build_id: 'toqraq.1',
    platform: 'windows',
    architecture: 'x86_64',
    package_bytes: 100,
    installed_bytes: 200,
    package_sha256: 'b'.repeat(64),
    source: {
      publisher: 'Toqraq',
      package_url: 'https://downloads.example.test/godot.zip',
      provenance_url: 'https://example.test/provenance',
    },
    license: {
      identifier: 'MIT',
      name: 'MIT License',
      url: 'https://example.test/license',
      acceptance_required: false,
    },
    authentication_required: false,
    capabilities: ['toqraq.preview'],
    readiness: 'missing',
    in_use: false,
    ...overrides,
  }
}

function components(releases: readonly Readonly<Record<string, unknown>>[] = [release()]) {
  return decodeComponentList({ releases })
}

function onlyRelease(
  releases: readonly Readonly<Record<string, unknown>>[] = [release()],
): ComponentReleaseResult {
  const list = components(releases)
  const selected = list.releases[0]
  if (!selected || list.releases.length !== 1) throw new Error('expected one component release')
  return selected
}

function job(overrides: Readonly<Record<string, unknown>> = {}) {
  return decodeComponentJob({
    operation_id: '8f489b96-c438-4d13-a54d-9e3f1020f531',
    release_id: RELEASE_ID,
    component_id: 'engine.godot',
    action: 'prepare',
    state: 'running',
    phase: 'downloading',
    completed_bytes: 25,
    total_bytes: 100,
    revision: 1,
    error: null,
    ...overrides,
  })
}

function setup(releaseIds: readonly string[] = [RELEASE_ID]) {
  return decodeSetup({
    action: 'install',
    engine: {
      id: 'godot',
      runtime: { version: '4.7.1' },
      available_versions: [],
      required_component_release_ids: releaseIds,
      runtime_install_required: true,
    },
    host: { platform: 'windows', native_display: true },
    project: {
      path: 'D:\\game',
      state: 'ready',
      viewport_size: null,
      probed_engine_ids: ['godot'],
    },
    engine_choices: [],
  })
}

test('setup resolves opaque release ids in backend order across component kinds', () => {
  const list = components([
    release(RELEASE_ID),
    release(BRIDGE_RELEASE_ID, {
      component_id: 'bridge.godot',
      kind: 'bridge',
      label: 'Godot bridge',
    }),
  ])
  const plan = resolveSetupComponentPlan(
    setup([BRIDGE_RELEASE_ID, RELEASE_ID]),
    list,
  )

  assert.deepEqual(plan, [list.releases[1], list.releases[0]])
  assert.ok(Object.isFrozen(plan))
})

test('setup rejects missing, unknown, and repeated requested release ids', () => {
  const list = components()
  assert.throws(() => setup([]), TypeError)
  assert.equal(resolveSetupComponentPlan(setup([BRIDGE_RELEASE_ID]), list), null)
  assert.throws(() => setup([RELEASE_ID, RELEASE_ID]), TypeError)
  assert.equal(resolveSetupComponentPlan(null, list), null)
  assert.equal(resolveSetupComponentPlan(setup(), null), null)
})

test('setup with no admitted engine has no component plan', () => {
  const unavailable = decodeSetup({
    action: 'engine_unavailable',
    engine: null,
    engine_choices: [],
    host: { platform: 'windows', native_display: true },
    project: {
      path: 'D:\\game',
      state: 'unchecked',
      viewport_size: null,
      probed_engine_ids: [],
    },
  })

  assert.equal(resolveSetupComponentPlan(unavailable, components()), null)

  const recognized = decodeSetup({
    action: 'runtime_unavailable',
    engine: {
      id: 'godot',
      runtime: null,
      available_versions: [],
      required_component_release_ids: [],
      runtime_install_required: false,
    },
    engine_choices: [],
    host: { platform: 'windows', native_display: true },
    project: {
      path: 'D:\\game',
      state: 'ready',
      viewport_size: { width: 960, height: 540 },
      probed_engine_ids: ['godot'],
    },
  })

  assert.equal(resolveSetupComponentPlan(recognized, components()), null)
})

test('setup rejects a catalog with duplicate release records', () => {
  const duplicate = components([
    release(RELEASE_ID),
    release(RELEASE_ID, { label: 'Conflicting record' }),
  ])
  assert.equal(resolveSetupComponentPlan(setup(), duplicate), null)
})

test('component actions never remove a live or mutating runtime', () => {
  const missing = onlyRelease()
  assert.deepEqual(deriveComponentActions(missing, null), {
    canPrepare: true,
    canRemove: false,
    canCancel: false,
    canRetry: false,
    active: false,
  })

  const ready = onlyRelease([release(RELEASE_ID, { readiness: 'ready' })])
  assert.equal(deriveComponentActions(ready, null).canRemove, true)
  const leased = onlyRelease([
    release(RELEASE_ID, { readiness: 'ready', in_use: true }),
  ])
  assert.equal(deriveComponentActions(leased, null).canRemove, false)
  assert.equal(deriveComponentActions(missing, job()).canPrepare, false)
  assert.equal(deriveComponentActions(missing, job()).canCancel, true)
})

test('component card state isolates its job and blocks competing active operations', () => {
  const selectedRelease = onlyRelease()
  const selectedJob = job()
  const selected = deriveComponentCardState(selectedRelease, selectedJob, false)

  assert.equal(selected.job, selectedJob)
  assert.equal(selected.actionDisabled, false)
  assert.equal(selected.progress, 0.25)
  assert.equal(selected.actions.canCancel, true)
  assert.ok(Object.isFrozen(selected))

  const competingJob = job({
    release_id: BRIDGE_RELEASE_ID,
    component_id: 'bridge.godot',
  })
  const blocked = deriveComponentCardState(selectedRelease, competingJob, false)
  assert.equal(blocked.job, null)
  assert.equal(blocked.progress, null)
  assert.equal(blocked.actionDisabled, true)
  assert.equal(blocked.actions.canPrepare, true)

  assert.equal(
    deriveComponentCardState(selectedRelease, null, true).actionDisabled,
    true,
  )
})

test('prepare action keys reflect repair and license acceptance facts', () => {
  const acceptingLicense = {
    identifier: 'MIT',
    name: 'MIT License',
    url: 'https://example.test/license',
    acceptance_required: true,
  }
  const missing = onlyRelease()
  const acceptedMissing = onlyRelease([
    release(RELEASE_ID, { license: acceptingLicense }),
  ])
  const invalid = onlyRelease([
    release(RELEASE_ID, { readiness: 'invalid' }),
  ])
  const acceptedInvalid = onlyRelease([
    release(RELEASE_ID, {
      readiness: 'invalid',
      license: acceptingLicense,
    }),
  ])

  assert.equal(componentPrepareActionKey(missing), 'component.action.prepare')
  assert.equal(
    componentPrepareActionKey(acceptedMissing),
    'component.action.acceptAndPrepare',
  )
  assert.equal(componentPrepareActionKey(invalid), 'component.action.repair')
  assert.equal(
    componentPrepareActionKey(acceptedInvalid),
    'component.action.acceptAndRepair',
  )
})

test('component text preserves exact release identity, target, and byte count', () => {
  const selectedRelease = onlyRelease()

  assert.equal(
    componentReleaseIdentity(selectedRelease),
    'engine.godot / 4.5.0 / toqraq.1',
  )
  assert.equal(componentReleaseTarget(selectedRelease), 'windows / x86_64')
  assert.equal(formatExactBytes(0), '0')
  assert.equal(formatExactBytes(123_456).replaceAll(/\D/g, ''), '123456')
})

test('failed and cancelled jobs are retryable projections', () => {
  const release = onlyRelease()
  const failed = job({
    state: 'failed',
    phase: 'verifying',
    error: {
      code: 'component.install_failed',
      category: 'upstream',
      parameters: {},
      details: { retryable: true },
      trace_id: 'ae01a6c4-87ca-4c97-9713-6d467329ed50',
    },
  })
  assert.equal(deriveComponentActions(release, failed).canRetry, true)
  assert.equal(componentJobPollInterval(failed), false)
})

test('terminal reconciliation is observed once per backend operation', () => {
  const terminal = job({
    state: 'ready',
    phase: 'ready',
    completed_bytes: 100,
  })
  assert.equal(nextTerminalComponentOperation(job(), ''), null)
  assert.equal(nextTerminalComponentOperation(terminal, ''), terminal.operation_id)
  assert.equal(nextTerminalComponentOperation(terminal, terminal.operation_id), null)
  assert.equal(
    nextTerminalComponentOperation(
      job({
        state: 'ready',
        phase: 'ready',
        completed_bytes: 100,
        revision: 2,
      }),
      terminal.operation_id,
    ),
    null,
  )
})

test('only a successful terminal result advances recovery to the next plan job', () => {
  const ready = job({
    state: 'ready',
    phase: 'ready',
    completed_bytes: 100,
  })
  const failed = job({
    state: 'failed',
    phase: 'verifying',
    error: {
      code: 'component.install_failed',
      category: 'upstream',
      parameters: {},
      details: { retryable: true },
      trace_id: 'ae01a6c4-87ca-4c97-9713-6d467329ed50',
    },
  })

  assert.equal(shouldAdvanceComponentRecovery(ready, ready.operation_id), true)
  assert.equal(shouldAdvanceComponentRecovery(failed, failed.operation_id), false)
  assert.equal(shouldAdvanceComponentRecovery(ready, 'another-operation'), false)
  assert.equal(shouldAdvanceComponentRecovery(null, ready.operation_id), false)
})

test('active jobs poll and progress stays bounded', () => {
  assert.equal(componentJobPollInterval(job()), COMPONENT_JOB_POLL_INTERVAL_MS)
  assert.equal(componentJobPollInterval(null, true), COMPONENT_JOB_RETRY_INTERVAL_MS)
  assert.equal(
    componentJobPollInterval(job({ state: 'ready', phase: 'ready', completed_bytes: 100 }), true),
    false,
  )
  assert.equal(componentProgress(job()), 0.25)
  assert.equal(componentProgress(job({ completed_bytes: 0, total_bytes: 0 })), null)
})

test('remount recovery follows exact backend plan order', () => {
  const bridgeOperation = 'a836c2a8-6dbd-4b48-a4e7-157b891f763f'
  const engineJob = job()
  const bridgeJob = job({
    operation_id: bridgeOperation,
    release_id: BRIDGE_RELEASE_ID,
    component_id: 'bridge.godot',
  })
  const active = decodeActiveComponentJobs({ jobs: [engineJob, bridgeJob] })

  assert.equal(
    selectRecoverableComponentJob(
      [BRIDGE_RELEASE_ID, RELEASE_ID],
      active,
    ),
    active.jobs[1],
  )
  assert.equal(
    selectRecoverableComponentJob(
      [BRIDGE_RELEASE_ID, RELEASE_ID],
      active,
      bridgeOperation,
    ),
    active.jobs[0],
  )
})

test('remount recovery never adopts removals, unrelated jobs, or ambiguous values', () => {
  const unrelated = job({ release_id: BRIDGE_RELEASE_ID, component_id: 'bridge.godot' })
  const removal = job({ action: 'remove', phase: 'removing' })
  assert.equal(
    selectRecoverableComponentJob(
      [RELEASE_ID],
      decodeActiveComponentJobs({ jobs: [unrelated] }),
    ),
    null,
  )
  assert.equal(
    selectRecoverableComponentJob(
      [RELEASE_ID],
      decodeActiveComponentJobs({ jobs: [removal] }),
    ),
    null,
  )
  assert.equal(
    selectRecoverableComponentJob(
      [RELEASE_ID, RELEASE_ID],
      decodeActiveComponentJobs({ jobs: [job()] }),
    ),
    null,
  )
  assert.equal(
    selectRecoverableComponentJob(
      [RELEASE_ID],
      { jobs: [job(), job()] },
    ),
    null,
  )
})

test('a missing retained read refreshes only the operation recovered after remount', () => {
  const operationId = job().operation_id
  assert.equal(
    isMissingRecoveredComponentJob(
      operationId,
      operationId,
      'component.job_not_found',
    ),
    true,
  )
  assert.equal(
    isMissingRecoveredComponentJob(operationId, '', 'component.job_not_found'),
    false,
  )
  assert.equal(
    isMissingRecoveredComponentJob(operationId, operationId, 'transport.unavailable'),
    false,
  )
  assert.equal(
    isMissingRecoveredComponentJob(null, operationId, 'component.job_not_found'),
    false,
  )
})
