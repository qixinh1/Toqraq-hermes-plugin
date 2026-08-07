/** Session-keyed event ordering with revision-safe REST reconciliation. */

import type { SessionEvent, SessionResult } from '../contracts/generated.js'

interface SessionEventConsumerOptions {
  sessionId: string
  read(sessionId: string): Promise<SessionResult | null>
  get(): SessionResult | null
  apply(session: SessionResult): boolean
  clear(sessionId: string, runRevision: number): boolean
  onObserved?(event: SessionEvent): void
  onSynchronized?(session: SessionResult | null): void
  onEnded?(session: SessionResult): void
  onError?(error: Error): void
}

interface SessionEventConsumer {
  accept(event: SessionEvent): Promise<void>
  reconcile(): Promise<void>
  close(): void
}

export function createSessionEventConsumer(
  options: SessionEventConsumerOptions,
): SessionEventConsumer {
  let closed = false
  let synchronized = false
  let greatestRunRevision = ownedRevision(options.get(), options.sessionId)
  let lastSequence: number | null = null
  let tail: Promise<void> = Promise.resolve()

  const enqueue = (operation: () => Promise<void>): Promise<void> => {
    tail = tail.then(operation).catch((error: unknown) => {
      if (!closed) {
        options.onError?.(
          error instanceof Error ? error : new Error('session reconcile failed'),
        )
      }
    })
    return tail
  }

  const reconcileNow = async (): Promise<void> => {
    if (closed) return
    const revisionBeforeRead = Math.max(
      greatestRunRevision,
      ownedRevision(options.get(), options.sessionId),
    )
    const session = await options.read(options.sessionId)
    if (closed) return
    if (session !== null) {
      if (session.id !== options.sessionId) {
        throw new TypeError('session reconcile owner mismatch')
      }
      greatestRunRevision = Math.max(greatestRunRevision, session.run_revision)
      options.apply(session)
    } else {
      const current = options.get()
      if (
        current !== null &&
        current.id === options.sessionId &&
        current.run_revision <= revisionBeforeRead
      ) {
        options.clear(options.sessionId, revisionBeforeRead)
      }
    }
    synchronized = true
    options.onSynchronized?.(session)
  }

  const applyEvent = (event: SessionEvent): void => {
    const session = eventSession(event)
    const currentRevision = ownedRevision(options.get(), options.sessionId)
    if (session.run_revision < Math.max(greatestRunRevision, currentRevision)) return
    greatestRunRevision = Math.max(greatestRunRevision, session.run_revision)
    if (event.type === 'session.stopped') {
      if (options.clear(options.sessionId, session.run_revision)) options.onEnded?.(session)
      return
    }
    options.apply(session)
  }

  return Object.freeze({
    accept(event: SessionEvent): Promise<void> {
      return enqueue(async () => {
        if (closed || event.session_id !== options.sessionId) return
        if (lastSequence !== null && event.sequence <= lastSequence) return
        options.onObserved?.(event)
        const gap = lastSequence !== null && event.sequence !== lastSequence + 1
        lastSequence = event.sequence
        if (!synchronized || gap) {
          await reconcileNow()
          return
        }
        applyEvent(event)
      })
    },
    reconcile(): Promise<void> {
      return enqueue(reconcileNow)
    },
    close(): void {
      closed = true
    },
  })
}

function eventSession(event: SessionEvent): SessionResult {
  return event.type === 'session.failed' ? event.payload.session : event.payload
}

function ownedRevision(session: SessionResult | null, sessionId: string): number {
  return session?.id === sessionId ? session.run_revision : 0
}
