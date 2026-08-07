/** Session presentation state owned by one Desktop plugin incarnation. */

import type { atom as createHermesAtom } from '@hermes/plugin-sdk'
import type { SessionResult } from '../contracts/generated.js'
import type { HermesGameProjection } from './hermesSessionReadiness.js'
import { projectOwnedHermesSession } from './hermesSessionReadiness.js'
import { SessionOperations } from './sessionOperations.js'
import type { SessionOperationToken } from './sessionOperations.js'
import { canApplySessionSnapshot, canClearSessionRun } from './sessionSnapshotOrder.js'

export type RendererAtom<Value> = ReturnType<typeof createHermesAtom<Value>>

interface RendererAtomFactory {
  <Value>(initialValue: Value): RendererAtom<Value>
}

export type SessionReadStatus = 'checking' | 'ready' | 'unavailable'

export interface RendererGameState {
  readonly readiness: HermesGameProjection
  readonly sessionRead: SessionReadStatus
  readonly session: SessionResult | null
}

export class RendererSessionStore {
  readonly gameState: RendererAtom<RendererGameState>
  readonly busyState: RendererAtom<boolean>
  readonly #operations = new SessionOperations()
  #disposed = false

  constructor(createAtom: RendererAtomFactory) {
    this.gameState = createAtom(initialGameState())
    this.busyState = createAtom(false)
  }

  get active(): boolean {
    return !this.#disposed
  }

  applyHermesReadiness(readiness: HermesGameProjection): boolean {
    if (this.#disposed) return false
    const current = this.gameState.get()
    const sameOwner =
      readiness.sessionId !== null &&
      current.readiness.sessionId === readiness.sessionId
    this.#operations.select(readiness.sessionId)
    const next = gameState(
      readiness,
      sameOwner ? current.sessionRead : initialReadStatus(readiness),
      sameOwner ? current.session : null,
    )
    if (sameGameState(current, next)) return false
    this.gameState.set(next)
    this.#projectBusyState()
    return true
  }

  applySessionReadStatus(
    sessionId: string,
    status: SessionReadStatus,
  ): boolean {
    if (this.#disposed) return false
    const current = this.gameState.get()
    if (current.readiness.sessionId !== sessionId || current.sessionRead === status) {
      return false
    }
    this.gameState.set(gameState(current.readiness, status, current.session))
    return true
  }

  beginSessionOperation(sessionId: string): SessionOperationToken | null {
    if (this.#disposed) return null
    const token = this.#operations.begin(sessionId)
    this.#projectBusyState()
    return token
  }

  ownsSelectedSessionOperation(token: SessionOperationToken): boolean {
    return (
      !this.#disposed &&
      this.#operations.owns(token) &&
      this.#operations.accepts(token.owner)
    )
  }

  finishSessionOperation(token: SessionOperationToken): boolean {
    if (this.#disposed) return false
    const finished = this.#operations.finish(token)
    this.#projectBusyState()
    return finished
  }

  currentSession(): SessionResult | null {
    return this.#disposed ? null : this.gameState.get().session
  }

  currentGame(): RendererGameState {
    return this.gameState.get()
  }

  /** Apply one snapshot unless this incarnation already knows a newer run. */
  applySessionSnapshot(session: SessionResult): boolean {
    if (this.#disposed || !this.#operations.accepts(session.id)) return false
    const current = this.gameState.get()
    if (!canApplySessionSnapshot(current.session, session)) return false
    this.gameState.set(gameState(current.readiness, current.sessionRead, session))
    return true
  }

  /** Clear only the run named by a terminal result or a newer replacement. */
  clearSessionRun(sessionId: string, runRevision: number): boolean {
    if (this.#disposed || !this.#operations.accepts(sessionId)) return false
    const current = this.gameState.get()
    if (!canClearSessionRun(current.session, sessionId, runRevision)) return false
    this.gameState.set(gameState(current.readiness, current.sessionRead, null))
    return true
  }

  dispose(): void {
    if (this.#disposed) return
    this.#disposed = true
    this.#operations.dispose()
    this.gameState.set(initialGameState())
    this.busyState.set(false)
  }

  #projectBusyState(): void {
    this.busyState.set(this.#operations.busy())
  }
}

function initialGameState(): RendererGameState {
  return gameState(projectOwnedHermesSession(null, false, 'pending'), 'ready', null)
}

function initialReadStatus(readiness: HermesGameProjection): SessionReadStatus {
  if (readiness.status === 'unavailable') return 'unavailable'
  return readiness.status === 'ready' || readiness.status === 'checking'
    ? 'checking'
    : 'ready'
}

function gameState(
  readiness: HermesGameProjection,
  sessionRead: SessionReadStatus,
  session: SessionResult | null,
): RendererGameState {
  return Object.freeze({ readiness, sessionRead, session })
}

function sameGameState(
  left: RendererGameState,
  right: RendererGameState,
): boolean {
  return (
    left.readiness.sessionId === right.readiness.sessionId &&
    left.readiness.status === right.readiness.status &&
    left.sessionRead === right.sessionRead &&
    left.session === right.session
  )
}
