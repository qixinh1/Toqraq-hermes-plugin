/** Revision-safe Stop orchestration independent of Hermes renderer state. */

import type { SessionResult } from '../contracts/generated.js'
import { ToqraqApiError } from '../bridge/errorBoundary.js'
import type { SessionOperationToken } from './sessionOperations.js'

export interface StopGamePorts<Context> {
  beginSessionOperation(sessionId: string): SessionOperationToken | null
  finishSessionOperation(token: SessionOperationToken): boolean
  currentSession(): SessionResult | null
  applySessionSnapshot(session: SessionResult): boolean
  clearSessionRun(sessionId: string, runRevision: number): boolean
  getSession(ctx: Context, sessionId: string): Promise<SessionResult | null>
  stopSession(
    ctx: Context,
    sessionId: string,
    runRevision: number,
  ): Promise<SessionResult>
}

/** Stop exactly the observed run and reconcile a replacement without clearing it. */
export async function executeStopGame<Context>(
  ctx: Context,
  sessionId: string,
  ports: StopGamePorts<Context>,
): Promise<boolean> {
  const operation = ports.beginSessionOperation(sessionId)
  if (operation === null) return false
  const observed = ports.currentSession()
  const observedRevision = observed?.id === sessionId ? observed.run_revision : null
  try {
    const current = await ports.getSession(ctx, sessionId)
    if (current === null) {
      if (observedRevision !== null) ports.clearSessionRun(sessionId, observedRevision)
      return false
    }
    ports.applySessionSnapshot(current)
    if (observedRevision !== null && current.run_revision !== observedRevision) return false

    const requestedRevision = current.run_revision
    try {
      const stopped = await ports.stopSession(ctx, sessionId, requestedRevision)
      requireStoppedRun(stopped, sessionId, requestedRevision)
      ports.clearSessionRun(sessionId, requestedRevision)
      return true
    } catch (error: unknown) {
      if (!isRunReplacement(error)) throw error
      const replacement = await ports.getSession(ctx, sessionId)
      if (replacement === null) ports.clearSessionRun(sessionId, requestedRevision)
      else ports.applySessionSnapshot(replacement)
      return false
    }
  } finally {
    ports.finishSessionOperation(operation)
  }
}

function requireStoppedRun(
  stopped: SessionResult,
  sessionId: string,
  runRevision: number,
): void {
  if (stopped.id !== sessionId || stopped.run_revision !== runRevision) {
    throw new TypeError('invalid Toqraq stopped run identity')
  }
}

function isRunReplacement(error: unknown): boolean {
  return (
    error instanceof ToqraqApiError &&
    error.code === 'session.invalid_state' &&
    error.details.reason === 'run_replaced'
  )
}
