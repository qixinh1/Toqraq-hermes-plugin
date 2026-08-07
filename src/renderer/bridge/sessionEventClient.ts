/** Live session-event subscription. */

import type { SessionEvent } from '../contracts/generated.js'
import { normalizeThrown, ToqraqApiError, unwrap } from './errorBoundary.js'
import type { TranslationContext } from './errorBoundary.js'
import { decodeSessionEvent } from './sessionDecoders.js'

export interface EventsBridgeContext extends TranslationContext {
  readonly socket: (path: string, onMessage: (data: unknown) => void) => () => void
}

export function openEvents(
  ctx: EventsBridgeContext,
  sessionId: string,
  onEvent: (event: SessionEvent) => void | Promise<void>,
  onError?: (error: ToqraqApiError) => void,
): () => void {
  try {
    return ctx.socket(`/sessions/${encodeURIComponent(sessionId)}/events`, (data) => {
      try {
        void Promise.resolve(onEvent(decodeSessionEvent(unwrap(data, ctx.i18n.t)))).catch(
          (error) => onError?.(normalizeThrown(ctx, error)),
        )
      } catch (error) {
        onError?.(normalizeThrown(ctx, error))
      }
    })
  } catch (error) {
    onError?.(normalizeThrown(ctx, error))
    return () => {}
  }
}
