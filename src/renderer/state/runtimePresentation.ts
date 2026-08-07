/** Project authoritative session snapshots into the compact Desktop vocabulary. */

import type { SessionResult } from '../contracts/generated.js'
import type { RendererGameState } from './rendererSessionStore.js'

export type RuntimeDisplayState =
  | 'idle'
  | 'running'
  | 'paused'
  | 'stopping'
  | 'crashed'

type RuntimeStatusState = RuntimeDisplayState | 'unavailable'

type RuntimeSnapshot = Pick<SessionResult, 'id' | 'process_state'>

/** Project the shared readiness and selected-session truth for the status bar. */
export function projectGameRuntimeState(
  game: RendererGameState,
): RuntimeStatusState {
  if (
    game.readiness.status === 'unavailable' ||
    (game.session === null && game.sessionRead === 'unavailable')
  ) return 'unavailable'
  return projectRuntimeState(game.session)
}

/** Collapse the terminal normal-exit fact into the Desktop idle state. */
export function projectRuntimeState(
  session: RuntimeSnapshot | null,
): RuntimeDisplayState {
  if (!session || session.process_state === 'ended') return 'idle'
  return session.process_state
}
