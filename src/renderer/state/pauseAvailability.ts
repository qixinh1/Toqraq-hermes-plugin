/** Pure pause availability projection for one selected game session. */

import type { SessionResult } from '../contracts/generated.js'

export type PauseCandidate = Pick<
  SessionResult,
  'id' | 'alive' | 'process_state' | 'control' | 'capabilities'
>

export function canPauseGame(session: PauseCandidate | null): session is PauseCandidate {
  return Boolean(
    session?.alive &&
      (session.process_state === 'running' || session.process_state === 'paused') &&
      session.control.state === 'ready' &&
      session.capabilities.includes('toqraq.play.pause'),
  )
}
