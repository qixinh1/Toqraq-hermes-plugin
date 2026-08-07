import assert from 'node:assert/strict'
import test from 'node:test'
import { canPauseGame } from './pauseAvailability.js'

type PauseCandidate = NonNullable<Parameters<typeof canPauseGame>[0]>

function pauseCandidate(overrides: Partial<PauseCandidate> = {}): PauseCandidate {
  return {
    id: 'session-1',
    alive: true,
    process_state: 'running' as const,
    control: { state: 'ready' as const },
    capabilities: ['toqraq.play.pause'],
    ...overrides,
  }
}

test('pause availability requires a live controllable run with the capability', () => {
  assert.equal(canPauseGame(pauseCandidate()), true)
  assert.equal(canPauseGame(pauseCandidate({ process_state: 'paused' })), true)
  assert.equal(canPauseGame(pauseCandidate({ alive: false })), false)
  assert.equal(canPauseGame(pauseCandidate({ process_state: 'stopping' })), false)
  assert.equal(canPauseGame(pauseCandidate({ control: { state: 'failed' } })), false)
  assert.equal(canPauseGame(pauseCandidate({ capabilities: [] })), false)
  assert.equal(canPauseGame(null), false)
})
