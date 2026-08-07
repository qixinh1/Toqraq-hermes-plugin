/** Expose a Hermes session owner only after the host confirms it is ready. */

import type { SessionSetupStatus } from './setupView.js'

export type HermesSessionStatusRead = 'pending' | 'success' | 'error'

export type HermesGameProjection =
  | Readonly<{
      sessionId: null
      status: Exclude<SessionSetupStatus, 'ready'>
    }>
  | Readonly<{
      sessionId: string
      status: 'ready'
    }>

export function projectOwnedHermesSession(
  activeSessionId: string | null,
  gatewayOpen: boolean,
  statusRead: HermesSessionStatusRead,
): HermesGameProjection {
  if (!activeSessionId) {
    return Object.freeze({ sessionId: null, status: 'needed' })
  }
  if (!gatewayOpen || statusRead === 'pending') {
    return Object.freeze({ sessionId: null, status: 'checking' })
  }
  if (statusRead === 'error') {
    return Object.freeze({ sessionId: null, status: 'unavailable' })
  }
  return Object.freeze({ sessionId: activeSessionId, status: 'ready' })
}
