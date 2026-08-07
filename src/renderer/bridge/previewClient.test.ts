import assert from 'node:assert/strict'
import test from 'node:test'
import {
  attachNativePreview,
  detachNativePreview,
  followNativePreview,
  setNativePreviewVisible,
} from './previewClient.js'
import { sessionResult } from './sessionResult.fixture.js'
import type { RestBridgeContext, RestRequestOptions } from './transport.js'

const TEST_I18N = Object.freeze({ t: () => 'Localized test message.' })

interface RestCall {
  readonly path: string
  readonly options: RestRequestOptions
}

test('native preview operations use focused routes and exact request owners', async () => {
  const calls: RestCall[] = []
  const ctx: RestBridgeContext = {
    i18n: TEST_I18N,
    rest: async (path, options) => {
      calls.push({ path, options: options ?? {} })
      return path.endsWith('/attach') ? sessionResult() : { ok: true }
    },
  }

  await attachNativePreview(ctx, {
    sessionId: 'session-1',
    attachmentId: 'pane-1',
    paneRect: { x: 10, y: 10, width: 100, height: 50 },
  })
  await followNativePreview(ctx, 'session-1', 'pane-1', {
    x: 10,
    y: 10,
    width: 200,
    height: 100,
  })
  await setNativePreviewVisible(ctx, 'session-1', 'pane-1', false)
  await detachNativePreview(ctx, 'session-1', 'pane-1')

  assert.deepEqual(calls.map((entry) => entry.path), [
    '/preview/native/attach',
    '/preview/native/rect',
    '/preview/native/visible',
    '/preview/native/detach',
  ])
  const [attach, follow] = calls
  assert.ok(attach)
  assert.ok(follow)
  assert.deepEqual(attach.options.body, {
    session_id: 'session-1',
    attachment_id: 'pane-1',
    pane_rect: { x: 10, y: 10, width: 100, height: 50 },
  })
  assert.deepEqual(follow.options.body, {
    session_id: 'session-1',
    attachment_id: 'pane-1',
    pane_rect: { x: 10, y: 10, width: 200, height: 100 },
  })
})
