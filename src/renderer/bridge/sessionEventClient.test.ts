import assert from 'node:assert/strict'
import test from 'node:test'
import { ToqraqApiError } from './errorBoundary.js'
import { openEvents } from './sessionEventClient.js'
import type { EventsBridgeContext } from './sessionEventClient.js'

test('session events subscribe to the encoded owner and observe malformed frames', () => {
  let subscribedPath = ''
  let receive: ((data: unknown) => void) | undefined
  let disposed = false
  let failure: ToqraqApiError | undefined
  const ctx: EventsBridgeContext = {
    i18n: { t: () => 'Localized test message.' },
    socket: (path, onMessage) => {
      subscribedPath = path
      receive = onMessage
      return () => {
        disposed = true
      }
    },
  }

  const close = openEvents(ctx, 'session / 1', () => {}, (error) => {
    failure = error
  })
  assert.equal(subscribedPath, '/sessions/session%20%2F%201/events')
  assert.ok(receive)
  receive({ malformed: true })
  assert.equal(failure?.code, 'transport.unavailable')
  close()
  assert.equal(disposed, true)
})
