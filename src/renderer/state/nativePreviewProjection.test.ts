import assert from 'node:assert/strict'
import test from 'node:test'
import type { SessionResult } from '../contracts/generated.js'
import { sessionResult } from '../bridge/sessionResult.fixture.js'
import { projectNativePreview } from './nativePreviewProjection.js'
import type { NativePreviewAttachmentState } from './nativePreviewProjection.js'

function session(overrides: Partial<SessionResult> = {}): SessionResult {
  return { ...sessionResult(), ...overrides }
}

function attachment(
  status: NativePreviewAttachmentState['status'],
  runRevision = 2,
): NativePreviewAttachmentState {
  return { sessionId: 'session-1', runRevision, status }
}

test('terminal and stopping runs never retain a native attachment placeholder', () => {
  assert.deepEqual(projectNativePreview(null, null), {
    attachment: null,
    view: 'setup',
  })

  const ended = session({ process_state: 'ended', alive: false, exit_code: 0 })
  assert.equal(projectNativePreview(ended, attachment('attached')).view, 'setup')

  for (const alive of [true, false]) {
    const stopping = session({
      process_state: 'stopping',
      alive,
      exit_code: alive ? null : 0,
    })
    const projected = projectNativePreview(stopping, attachment('attached'))
    assert.equal(projected.attachment, null)
    assert.equal(projected.view, 'unavailable')
  }
})

test('process, capability, readiness, and surface jointly gate native attachment', () => {
  const ready = sessionResult()
  assert.equal(
    projectNativePreview(session({ capabilities: [] }), null).view,
    'unavailable',
  )
  assert.equal(
    projectNativePreview(
      session({ preview: { state: 'connecting', error: null, surface: null } }),
      null,
    ).view,
    'connecting',
  )
  assert.equal(
    projectNativePreview(
      session({ preview: { state: 'unavailable', error: null, surface: null } }),
      null,
    ).view,
    'unavailable',
  )
  assert.equal(
    projectNativePreview(
      session({
        preview: {
          state: 'failed',
          surface: null,
          error: {
            code: 'preview.failed',
            category: 'unavailable',
            parameters: {},
            details: {},
            trace_id: '4f9dd55e-9154-44bb-9705-dc865dd26f2f',
          },
        },
      }),
      null,
    ).view,
    'failed',
  )
  assert.equal(
    projectNativePreview(
      session({
        preview: {
          state: 'ready',
          error: null,
          surface: { kind: 'web', viewport_size: { width: 960, height: 540 } },
        },
      }),
      null,
    ).view,
    'unavailable',
  )
  assert.equal(projectNativePreview(ready, null).attachment, ready)
})

test('attached and retrying display states belong only to their exact run owner', () => {
  const ready = sessionResult()
  const pending = projectNativePreview(ready, null)
  assert.equal(pending.view, 'connecting')
  assert.ok(Object.isFrozen(pending))

  assert.equal(projectNativePreview(ready, attachment('attached')).view, 'attached')
  assert.equal(projectNativePreview(ready, attachment('failed')).view, 'retrying')
  assert.equal(
    projectNativePreview(ready, attachment('attached', ready.run_revision + 1)).view,
    'connecting',
  )

  const paused = session({ process_state: 'paused' })
  assert.equal(projectNativePreview(paused, attachment('attached')).view, 'attached')
})
