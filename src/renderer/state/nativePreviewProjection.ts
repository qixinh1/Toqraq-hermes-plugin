/** Project one selected run into native attachment ownership and pane presentation. */

import type { SessionResult } from '../contracts/generated.js'
import type { NativePreviewStatus } from './nativePreviewController.js'

export type NativePreviewView =
  | 'setup'
  | 'unavailable'
  | 'connecting'
  | 'attached'
  | 'failed'
  | 'retrying'

export interface NativePreviewAttachmentState {
  readonly sessionId: string
  readonly runRevision: number
  readonly status: NativePreviewStatus
}

export interface NativePreviewProjection {
  readonly attachment: SessionResult | null
  readonly view: NativePreviewView
}

export function projectNativePreview(
  session: SessionResult | null,
  attachmentState: NativePreviewAttachmentState | null,
): NativePreviewProjection {
  if (!session) return projection(null, 'setup')
  if (session.process_state === 'stopping') return projection(null, 'unavailable')
  if (!session.alive) return projection(null, 'setup')
  if (
    (session.process_state !== 'running' && session.process_state !== 'paused') ||
    !session.capabilities.includes('toqraq.preview.display')
  ) {
    return projection(null, 'unavailable')
  }
  if (session.preview.state === 'failed') return projection(null, 'failed')
  if (session.preview.state === 'connecting') return projection(null, 'connecting')
  if (
    session.preview.state !== 'ready' ||
    session.preview.surface?.kind !== 'native_window'
  ) {
    return projection(null, 'unavailable')
  }

  const status = attachmentOwnerMatches(attachmentState, session)
    ? attachmentState.status
    : 'connecting'
  return projection(session, status === 'failed' ? 'retrying' : status)
}

function attachmentOwnerMatches(
  attachmentState: NativePreviewAttachmentState | null,
  session: SessionResult,
): attachmentState is NativePreviewAttachmentState {
  return Boolean(
    attachmentState &&
      attachmentState.sessionId === session.id &&
      attachmentState.runRevision === session.run_revision,
  )
}

function projection(
  attachment: SessionResult | null,
  view: NativePreviewView,
): NativePreviewProjection {
  return Object.freeze({ attachment, view })
}
