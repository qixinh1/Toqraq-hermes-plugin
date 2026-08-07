import assert from 'node:assert/strict'
import test from 'node:test'
import type { SessionResult } from '../contracts/generated.js'
import { sessionResult } from '../bridge/sessionResult.fixture.js'
import type { RendererGameState, SessionReadStatus } from './rendererSessionStore.js'
import { projectGameRuntimeState } from './runtimePresentation.js'

function session(
  id: string,
  processState: SessionResult['process_state'],
): SessionResult {
  const terminal = processState === 'ended' || processState === 'crashed'
  return {
    ...sessionResult(),
    id,
    process_state: processState,
    alive: !terminal,
    exit_code: terminal ? (processState === 'crashed' ? 23 : 0) : null,
  }
}

function game(
  selected: SessionResult | null,
  sessionRead: SessionReadStatus = 'ready',
  readiness: RendererGameState['readiness'] = { sessionId: 'active', status: 'ready' },
): RendererGameState {
  return { readiness, sessionRead, session: selected }
}

test('status projection exposes readiness failure only without retained run truth', () => {
  assert.equal(projectGameRuntimeState(game(null, 'unavailable')), 'unavailable')
  assert.equal(
    projectGameRuntimeState(game(session('active', 'running'), 'unavailable')),
    'running',
  )
  assert.equal(
    projectGameRuntimeState(game(null, 'ready', { sessionId: null, status: 'unavailable' })),
    'unavailable',
  )
})

test('status projection preserves active paused, stopping, and crashed facts', () => {
  const states: readonly SessionResult['process_state'][] = [
    'running',
    'paused',
    'stopping',
    'crashed',
  ]
  for (const state of states) {
    assert.equal(projectGameRuntimeState(game(session('active', state))), state)
  }
  assert.equal(projectGameRuntimeState(game(session('active', 'ended'))), 'idle')
  assert.equal(
    projectGameRuntimeState(game(null, 'checking', { sessionId: null, status: 'checking' })),
    'idle',
  )
})
