import assert from 'node:assert/strict'
import test from 'node:test'
import { decodeSetup } from './decoders.js'

function setupResult() {
  return {
    host: { platform: 'windows', native_display: true },
    engine: {
      id: 'godot',
      runtime: { version: '4.5.0' },
      available_versions: [],
      required_component_release_ids: ['1'.repeat(64)],
      runtime_install_required: false,
    },
    project: {
      path: 'D:/game',
      state: 'ready',
      viewport_size: { width: 960, height: 540 },
      probed_engine_ids: ['godot'],
    },
    engine_choices: [],
    action: 'start',
  }
}

type RuntimeSetupAction =
  | 'runtime_unavailable'
  | 'select_version'
  | 'install'
  | 'start'
  | 'unsupported_host'

function setupForRuntimeAction(action: RuntimeSetupAction) {
  const value = setupResult()
  if (action === 'start') return value
  if (action === 'install') {
    return {
      ...value,
      action,
      engine: { ...value.engine, runtime_install_required: true },
    }
  }
  if (action === 'select_version') {
    return {
      ...value,
      action,
      engine: {
        id: 'godot',
        runtime: null,
        available_versions: ['4.7.1'],
        required_component_release_ids: [],
        runtime_install_required: false,
      },
    }
  }
  return {
    ...value,
    action,
    engine: {
      id: 'godot',
      runtime: null,
      available_versions: [],
      required_component_release_ids: [],
      runtime_install_required: false,
    },
  }
}

test('setup decoder rejects malformed nested results and freezes valid state', () => {
  const value = setupResult()
  const decoded = decodeSetup(value)
  assert.ok(Object.isFrozen(decoded.project.viewport_size))
  assert.ok(Object.isFrozen(decoded.project.probed_engine_ids))
  assert.ok(Object.isFrozen(decoded.engine_choices))
  assert.ok(decoded.engine)
  assert.ok(Object.isFrozen(decoded.engine.required_component_release_ids))
  assert.equal(
    decodeSetup({
      ...value,
      action: 'install',
      engine: { ...value.engine, runtime_install_required: true },
    }).action,
    'install',
  )
  assert.throws(
    () =>
      decodeSetup({
        ...value,
        engine: { ...value.engine, required_component_release_ids: ['not-an-id'] },
      }),
    TypeError,
  )
  assert.throws(
    () => decodeSetup({ ...value, project: { ...value.project, state: 'invented' } }),
    TypeError,
  )
})

test('setup decoder preserves the explicit empty certified-engine state', () => {
  const value = {
    host: { platform: 'windows', native_display: true },
    engine: null,
    project: {
      path: 'D:/game',
      state: 'unchecked',
      viewport_size: null,
      probed_engine_ids: [],
    },
    engine_choices: [],
    action: 'engine_unavailable',
  }

  const decoded = decodeSetup(value)

  assert.equal(decoded.engine, null)
  assert.equal(decoded.action, 'engine_unavailable')
  assert.ok(Object.isFrozen(decoded))
  assert.throws(
    () =>
      decodeSetup({
        ...value,
        engine: {
          id: 'godot',
          runtime: null,
          available_versions: [],
          required_component_release_ids: [],
          runtime_install_required: false,
        },
      }),
    TypeError,
  )
})

test('setup decoder preserves recognized project facts without inventing a runtime', () => {
  const value = {
    host: { platform: 'windows', native_display: true },
    engine: {
      id: 'godot',
      runtime: null,
      available_versions: [],
      required_component_release_ids: [],
      runtime_install_required: false,
    },
    project: {
      path: 'D:/game',
      state: 'ready',
      viewport_size: { width: 960, height: 540 },
      probed_engine_ids: ['godot'],
    },
    engine_choices: [],
    action: 'runtime_unavailable',
  }

  const decoded = decodeSetup(value)

  assert.equal(decoded.action, 'runtime_unavailable')
  assert.equal(decoded.engine?.id, 'godot')
  assert.equal(decoded.engine?.runtime, null)
  assert.throws(
    () =>
      decodeSetup({
        ...value,
        engine: { ...value.engine, available_versions: ['4.7.1'] },
      }),
    TypeError,
  )
})

test('setup decoder rejects probe evidence that contradicts the project state', () => {
  const unselected = {
    host: { platform: 'windows', native_display: true },
    engine: null,
    engine_choices: [],
  }
  const invalidValues = [
    {
      ...unselected,
      project: {
        path: 'D:/game',
        state: 'unchecked',
        viewport_size: null,
        probed_engine_ids: ['godot'],
      },
      action: 'engine_unavailable',
    },
    ...['missing', 'invalid'].map((state) => ({
      ...unselected,
      project: {
        path: state === 'missing' ? null : 'D:/game',
        state,
        viewport_size: null,
        probed_engine_ids: ['godot'],
      },
      action: 'select_project',
    })),
    {
      ...unselected,
      project: {
        path: 'D:/game',
        state: 'not_detected',
        viewport_size: null,
        probed_engine_ids: [],
      },
      action: 'select_project',
    },
    {
      ...unselected,
      project: {
        path: 'D:/game',
        state: 'ambiguous',
        viewport_size: null,
        probed_engine_ids: ['godot'],
      },
      engine_choices: [
        { id: 'godot', declared_version: null, confidence: 90 },
        { id: 'unity', declared_version: null, confidence: 80 },
      ],
      action: 'select_engine',
    },
    ...[[], ['godot', 'unity']].map((probedEngineIds) => ({
      ...setupResult(),
      project: {
        ...setupResult().project,
        probed_engine_ids: probedEngineIds,
      },
    })),
  ]

  for (const value of invalidValues) assert.throws(() => decodeSetup(value), TypeError)
})

test('setup decoder keeps project path and viewport facts coherent with state', () => {
  const unavailable = {
    host: { platform: 'windows', native_display: true },
    engine: null,
    engine_choices: [],
    action: 'select_project',
  }
  const invalidProjects = [
    { path: 'D:/game', state: 'missing', viewport_size: null, probed_engine_ids: [] },
    { path: null, state: 'invalid', viewport_size: null, probed_engine_ids: [] },
    {
      path: 'D:/game',
      state: 'not_detected',
      viewport_size: { width: 960, height: 540 },
      probed_engine_ids: ['godot'],
    },
  ]

  for (const project of invalidProjects) {
    assert.throws(() => decodeSetup({ ...unavailable, project }), TypeError)
  }
})

test('setup decoder requires engine choices to equal project probes in order', () => {
  const value = {
    host: { platform: 'windows', native_display: true },
    engine: null,
    project: {
      path: 'D:/game',
      state: 'ambiguous',
      viewport_size: null,
      probed_engine_ids: ['godot', 'unity'],
    },
    engine_choices: [
      { id: 'godot', declared_version: null, confidence: 90 },
      { id: 'unity', declared_version: null, confidence: 80 },
    ],
    action: 'select_engine',
  }

  assert.equal(decodeSetup(value).action, 'select_engine')
  assert.throws(
    () => decodeSetup({ ...value, engine_choices: [...value.engine_choices].reverse() }),
    TypeError,
  )
})

test('setup decoder requires every runtime action to match the sole project probe', () => {
  const actions: readonly RuntimeSetupAction[] = [
    'runtime_unavailable',
    'select_version',
    'install',
    'start',
    'unsupported_host',
  ]

  for (const action of actions) {
    const value = setupForRuntimeAction(action)
    assert.equal(decodeSetup(value).action, action)
    assert.throws(
      () =>
        decodeSetup({
          ...value,
          project: { ...value.project, probed_engine_ids: ['unity'] },
        }),
      TypeError,
    )
  }
})

test('unsupported host decoder state cannot offer runtime preparation', () => {
  const value = setupForRuntimeAction('unsupported_host')
  const selectedRuntime = setupResult().engine
  const installRuntime = { ...selectedRuntime, runtime_install_required: true }
  const versionChoice = setupForRuntimeAction('select_version').engine

  for (const engine of [selectedRuntime, installRuntime, versionChoice]) {
    assert.throws(() => decodeSetup({ ...value, engine }), TypeError)
  }
})
