/** Plugin-lifetime synchronization of the active Hermes-owned game. */

import type { SessionEvent, SessionResult } from '../contracts/generated.js'
import { projectOwnedHermesSession } from './hermesSessionReadiness.js'
import type { ReadableValue } from './readableValue.js'
import type { RendererSessionStore } from './rendererSessionStore.js'
import { createSessionEventConsumer } from './sessionEvents.js'

const OPEN_GATEWAY_STATE = 'open'

interface RendererSessionSyncDependencies {
  readonly activeSessionId: ReadableValue<string | null>
  readonly gateway: ReadableValue<string>
  readonly store: RendererSessionStore
  readonly readHermesStatus: (sessionId: string) => Promise<unknown>
  readonly cancelHermesStatus: (sessionId: string) => void
  readonly readSession: (sessionId: string) => Promise<SessionResult | null>
  readonly openEvents: (
    sessionId: string,
    onEvent: (event: SessionEvent) => void | Promise<void>,
    onError: (error: unknown) => void,
  ) => () => void
  readonly scheduleRetry: (retry: () => void) => () => void
  readonly onLoadError: (error: unknown) => void
  readonly onEventError: (error: unknown) => void
  readonly onEnded: (session: SessionResult) => void
}

/** Start the sole active-game synchronizer owned by one plugin incarnation. */
export function startRendererSessionSync(
  dependencies: RendererSessionSyncDependencies,
): () => void {
  let disposed = false
  let generation = 0
  let observedOwner: string | null | undefined
  let observedGatewayOpen: boolean | undefined
  let cancelStatus = noOp
  let closeChannel = noOp
  let cancelRetry = noOp

  const current = (owner: string, ownerGeneration: number): boolean =>
    !disposed &&
    generation === ownerGeneration &&
    observedOwner === owner &&
    observedGatewayOpen === true

  const clearRetry = (): void => {
    const cancel = cancelRetry
    cancelRetry = noOp
    cancel()
  }

  const clearTarget = (): void => {
    clearRetry()
    const close = closeChannel
    closeChannel = noOp
    close()
    const cancel = cancelStatus
    cancelStatus = noOp
    cancel()
  }

  const schedule = (
    owner: string,
    ownerGeneration: number,
    retry: () => void,
  ): void => {
    clearRetry()
    cancelRetry = dependencies.scheduleRetry(() => {
      cancelRetry = noOp
      if (current(owner, ownerGeneration)) retry()
    })
  }

  const openChannel = (owner: string, ownerGeneration: number): void => {
    let loadErrorReported = false
    const consumer = createSessionEventConsumer({
      sessionId: owner,
      read: dependencies.readSession,
      get: () => dependencies.store.currentSession(),
      apply: (session) => dependencies.store.applySessionSnapshot(session),
      clear: (sessionId, runRevision) =>
        dependencies.store.clearSessionRun(sessionId, runRevision),
      onSynchronized: () => {
        if (!current(owner, ownerGeneration)) return
        loadErrorReported = false
        clearRetry()
        dependencies.store.applySessionReadStatus(owner, 'ready')
      },
      onEnded: (session) => {
        if (current(owner, ownerGeneration)) dependencies.onEnded(session)
      },
      onError: (error) => {
        if (!current(owner, ownerGeneration)) return
        dependencies.store.applySessionReadStatus(owner, 'unavailable')
        if (!loadErrorReported) {
          loadErrorReported = true
          dependencies.onLoadError(error)
        }
        schedule(owner, ownerGeneration, () => {
          void consumer.reconcile()
        })
      },
    })
    let closeSocket = noOp
    try {
      closeSocket = dependencies.openEvents(
        owner,
        (event) => consumer.accept(event),
        (error) => {
          if (!current(owner, ownerGeneration)) return
          dependencies.onEventError(error)
          void consumer.reconcile()
        },
      )
    } catch (error) {
      dependencies.onEventError(error)
    }
    closeChannel = () => {
      consumer.close()
      closeSocket()
    }
    void consumer.reconcile()
  }

  const checkHermesStatus = (owner: string, ownerGeneration: number): void => {
    clearRetry()
    cancelStatus()
    cancelStatus = () => dependencies.cancelHermesStatus(owner)
    dependencies.store.applyHermesReadiness(
      projectOwnedHermesSession(owner, true, 'pending'),
    )
    void Promise.resolve()
      .then(() => dependencies.readHermesStatus(owner))
      .then(
        () => {
          if (!current(owner, ownerGeneration)) return
          dependencies.store.applyHermesReadiness(
            projectOwnedHermesSession(owner, true, 'success'),
          )
          openChannel(owner, ownerGeneration)
        },
        () => {
          if (!current(owner, ownerGeneration)) return
          dependencies.store.applyHermesReadiness(
            projectOwnedHermesSession(owner, true, 'error'),
          )
          schedule(owner, ownerGeneration, () => {
            checkHermesStatus(owner, ownerGeneration)
          })
        },
      )
  }

  const reconcile = (): void => {
    if (disposed) return
    const owner = dependencies.activeSessionId.get()
    const gatewayOpen = dependencies.gateway.get() === OPEN_GATEWAY_STATE
    if (owner === observedOwner && gatewayOpen === observedGatewayOpen) return
    generation += 1
    clearTarget()
    observedOwner = owner
    observedGatewayOpen = gatewayOpen
    dependencies.store.applyHermesReadiness(
      projectOwnedHermesSession(owner, gatewayOpen, 'pending'),
    )
    if (owner && gatewayOpen) checkHermesStatus(owner, generation)
  }

  const subscriptions = [
    dependencies.activeSessionId.subscribe(reconcile),
    dependencies.gateway.subscribe(reconcile),
  ]
  return () => {
    if (disposed) return
    disposed = true
    generation += 1
    for (const unsubscribe of subscriptions.reverse()) unsubscribe()
    clearTarget()
  }
}

function noOp(): void {}
