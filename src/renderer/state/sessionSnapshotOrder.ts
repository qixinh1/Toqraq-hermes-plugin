/** Pure ordering rules for the selected Hermes session's current game run. */

import type { SessionResult } from '../contracts/generated.js'

type SessionRunIdentity = Pick<SessionResult, 'id' | 'run_revision'>

export function canApplySessionSnapshot(
  current: SessionRunIdentity | null,
  incoming: SessionRunIdentity,
): boolean {
  return (
    current === null ||
    current.id !== incoming.id ||
    current.run_revision <= incoming.run_revision
  )
}

export function canClearSessionRun(
  current: SessionRunIdentity | null,
  sessionId: string,
  terminalRunRevision: number,
): boolean {
  return (
    current !== null &&
    current.id === sessionId &&
    current.run_revision <= terminalRunRevision
  )
}
