import assert from 'node:assert/strict'
import test from 'node:test'
import { syncWorkspaceContext } from './setupClient.js'
import type { RestBridgeContext, RestRequestOptions } from './transport.js'

const TEST_I18N = Object.freeze({ t: () => 'Localized test message.' })

interface RestCall {
  readonly path: string
  readonly options: RestRequestOptions
}

function setupResult() {
  return {
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
}

test('workspace context uses the active Hermes task and explicit clear body', async () => {
  const calls: RestCall[] = []
  const ctx: RestBridgeContext = {
    i18n: TEST_I18N,
    rest: async (path, options) => {
      calls.push({ path, options: options ?? {} })
      const body = options?.body
      return typeof body === 'object' && body !== null && Object.hasOwn(body, 'project_dir')
        ? setupResult()
        : null
    },
  }

  assert.deepEqual(
    await syncWorkspaceContext(ctx, 'session / 1', { projectDir: 'D:/game' }),
    setupResult(),
  )
  assert.equal(await syncWorkspaceContext(ctx, 'session / 1'), null)
  assert.deepEqual(calls.map((entry) => entry.path), [
    '/workspace-context/session%20%2F%201',
    '/workspace-context/session%20%2F%201',
  ])
  const [first, second] = calls
  assert.ok(first)
  assert.ok(second)
  assert.equal(first.options.method, 'PUT')
  assert.deepEqual(first.options.body, { project_dir: 'D:/game' })
  assert.deepEqual(second.options.body, {})
})
