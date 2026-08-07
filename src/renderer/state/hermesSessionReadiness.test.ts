import assert from 'node:assert/strict'
import test from 'node:test'
import { projectOwnedHermesSession } from './hermesSessionReadiness.js'
import type { HermesSessionStatusRead } from './hermesSessionReadiness.js'

interface ReadinessCase {
  readonly name: string
  readonly activeSessionId: string | null
  readonly gatewayOpen: boolean
  readonly statusRead: HermesSessionStatusRead
  readonly expectedStatus: 'needed' | 'checking' | 'ready' | 'unavailable'
  readonly expectedOwner: string | null
}

const CASES: readonly ReadinessCase[] = [
  {
    name: 'no active Hermes session',
    activeSessionId: null,
    gatewayOpen: true,
    statusRead: 'success',
    expectedStatus: 'needed',
    expectedOwner: null,
  },
  {
    name: 'closed gateway',
    activeSessionId: 'session-1',
    gatewayOpen: false,
    statusRead: 'success',
    expectedStatus: 'checking',
    expectedOwner: null,
  },
  {
    name: 'pending host status',
    activeSessionId: 'session-1',
    gatewayOpen: true,
    statusRead: 'pending',
    expectedStatus: 'checking',
    expectedOwner: null,
  },
  {
    name: 'failed host status',
    activeSessionId: 'session-1',
    gatewayOpen: true,
    statusRead: 'error',
    expectedStatus: 'unavailable',
    expectedOwner: null,
  },
  {
    name: 'confirmed host status',
    activeSessionId: 'session-1',
    gatewayOpen: true,
    statusRead: 'success',
    expectedStatus: 'ready',
    expectedOwner: 'session-1',
  },
]

test('only a confirmed Hermes session is exposed as the game owner', () => {
  for (const entry of CASES) {
    const projected = projectOwnedHermesSession(
      entry.activeSessionId,
      entry.gatewayOpen,
      entry.statusRead,
    )
    assert.equal(projected.status, entry.expectedStatus, entry.name)
    assert.equal(projected.sessionId, entry.expectedOwner, entry.name)
    assert.ok(Object.isFrozen(projected), entry.name)
  }
})
