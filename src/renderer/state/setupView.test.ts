import assert from 'node:assert/strict'
import test from 'node:test'
import { deriveSetupView, shouldCheckSetup } from './setupView.js'
import type { SetupViewInput, SetupViewSetup } from './setupView.js'

const ready: SetupViewSetup = {
  action: 'start',
  host: { platform: 'windows', native_display: true },
  project: { state: 'ready' },
  engine: { runtime: { version: '4.7.1' }, runtime_install_required: false },
}

test('setup requests require a workspace and no selected live game', () => {
  assert.equal(shouldCheckSetup('', false), false)
  assert.equal(shouldCheckSetup('D:/game', true), false)
  assert.equal(shouldCheckSetup('D:/game', false), true)
})

test('ready setup is startable only with a Hermes session', () => {
  assert.equal(view({ setup: ready }).startable, true)
  const missingSession = view({ setup: ready, sessionStatus: 'needed' })
  assert.equal(missingSession.startable, false)
  assert.equal(missingSession.headline, 'session')
})

test('a draft id is not ready until Hermes exposes a live session', () => {
  const checking = view({ setup: ready, sessionStatus: 'checking' })
  assert.equal(checking.startable, false)
  assert.equal(checking.headline, 'checking')

  const unavailable = view({ setup: ready, sessionStatus: 'unavailable' })
  assert.equal(unavailable.startable, false)
  assert.equal(unavailable.headline, 'sessionUnavailable')
})

test('an exhausted setup request is visible and blocks start', () => {
  const result = view({ setup: ready, failed: true })
  assert.equal(result.startable, false)
  assert.equal(result.headline, 'setupUnavailable')
  assert.equal(result.showComponentPlan, false)
  assert.equal(result.retryable, true)
})

test('an empty workspace is focused and does not invent readiness', () => {
  const result = view({ workspacePresent: false })
  assert.equal(result.headline, 'workspaceMissing')
  assert.equal(result.showReadiness, false)
  assert.equal(result.showComponentPlan, false)
  assert.equal(result.startable, false)
})

test('missing runtime requires explicit preparation and blocks start', () => {
  const result = view({
    setup: {
      ...ready,
      action: 'install',
      engine: { runtime: null, runtime_install_required: true },
    },
  })
  assert.equal(result.runtime, 'required')
  assert.equal(result.headline, 'install')
  assert.equal(result.startable, false)
  assert.equal(result.showComponentPlan, true)
})

test('project and host failures explain the blocking action', () => {
  const invalid = view({
    setup: { ...ready, action: 'select_project', project: { state: 'invalid' } },
  })
  assert.equal(invalid.headline, 'projectInvalid')
  assert.equal(invalid.startable, false)

  const unsupported = view({
    setup: {
      ...ready,
      action: 'unsupported_host',
      host: { platform: 'linux', native_display: false },
    },
  })
  assert.equal(unsupported.headline, 'host')
  assert.equal(unsupported.startable, false)
})

test('Windows backend failure is distinct from an unsupported system', () => {
  const result = view({
    setup: {
      ...ready,
      action: 'unsupported_host',
      host: { platform: 'windows', native_display: false },
    },
  })
  assert.equal(result.headline, 'hostUnavailable')
  assert.equal(result.host, 'unavailable')
})

test('a web-capable release is startable without a native display adapter', () => {
  const result = view({
    setup: {
      ...ready,
      host: { platform: 'linux', native_display: false },
    },
  })

  assert.equal(result.headline, 'ready')
  assert.equal(result.host, 'ready')
  assert.equal(result.startable, true)
})

test('empty certified-engine state is explicit and never startable', () => {
  const result = view({
    setup: {
      action: 'engine_unavailable',
      host: { platform: 'windows', native_display: true },
      project: { state: 'unchecked' },
      engine: null,
    },
  })

  assert.equal(result.headline, 'engineUnavailable')
  assert.equal(result.runtime, 'unavailable')
  assert.equal(result.project, 'unchecked')
  assert.equal(result.startable, false)

  const withoutSession = view({
    setup: {
      action: 'engine_unavailable',
      host: { platform: 'windows', native_display: true },
      project: { state: 'unchecked' },
      engine: null,
    },
    sessionStatus: 'needed',
  })
  assert.equal(withoutSession.headline, 'engineUnavailable')
})

test('recognized project without an admitted runtime remains visible and blocked', () => {
  const result = view({
    setup: {
      action: 'runtime_unavailable',
      host: { platform: 'windows', native_display: true },
      project: { state: 'ready' },
      engine: { runtime: null, runtime_install_required: false },
    },
  })

  assert.equal(result.headline, 'runtimeUnavailable')
  assert.equal(result.project, 'ready')
  assert.equal(result.runtime, 'unavailable')
  assert.equal(result.showComponentPlan, false)
  assert.equal(result.startable, false)
})

test('engine and version choice states stay distinct', () => {
  const engine = view({
    setup: {
      action: 'select_engine',
      host: { platform: 'windows', native_display: true },
      project: { state: 'ambiguous' },
      engine: null,
    },
  })
  const version = view({
    setup: {
      action: 'select_version',
      host: { platform: 'windows', native_display: true },
      project: { state: 'ready' },
      engine: { runtime: null, runtime_install_required: false },
    },
  })

  assert.equal(engine.headline, 'engineChoice')
  assert.equal(version.headline, 'versionChoice')
  assert.equal(version.runtime, 'choice')
})

function view(overrides: Partial<SetupViewInput> = {}) {
  return deriveSetupView({
    setup: null,
    sessionStatus: 'ready',
    workspacePresent: true,
    checking: false,
    ...overrides,
  })
}
