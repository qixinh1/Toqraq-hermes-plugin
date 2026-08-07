/** Native-preview attachment and geometry requests. */

import type { PreviewOperationResult, RectValue, SessionResult } from '../contracts/generated.js'
import { decodePreviewOperation } from './previewDecoders.js'
import { decodeSession } from './sessionDecoders.js'
import { REQUEST_TIMEOUT_MS, requestDecoded } from './transport.js'
import type { RestBridgeContext } from './transport.js'

interface NativePreviewAttachment {
  readonly sessionId: string
  readonly attachmentId: string
  readonly paneRect: RectValue
}

export async function attachNativePreview(
  ctx: RestBridgeContext,
  attachment: NativePreviewAttachment,
): Promise<SessionResult> {
  return requestDecoded(
    ctx,
    '/preview/native/attach',
    {
      method: 'POST',
      timeoutMs: REQUEST_TIMEOUT_MS,
      body: {
        session_id: attachment.sessionId,
        attachment_id: attachment.attachmentId,
        pane_rect: attachment.paneRect,
      },
    },
    (value) => {
      const session = decodeSession(value)
      if (session.id !== attachment.sessionId) invalidPreviewOwner()
      return session
    },
  )
}

export async function followNativePreview(
  ctx: RestBridgeContext,
  sessionId: string,
  attachmentId: string,
  paneRect: RectValue,
): Promise<PreviewOperationResult> {
  return requestDecoded(
    ctx,
    '/preview/native/rect',
    {
      method: 'POST',
      timeoutMs: REQUEST_TIMEOUT_MS,
      body: { session_id: sessionId, attachment_id: attachmentId, pane_rect: paneRect },
    },
    decodePreviewOperation,
  )
}

export async function setNativePreviewVisible(
  ctx: RestBridgeContext,
  sessionId: string,
  attachmentId: string,
  visible: boolean,
): Promise<PreviewOperationResult> {
  return requestDecoded(
    ctx,
    '/preview/native/visible',
    {
      method: 'POST',
      timeoutMs: REQUEST_TIMEOUT_MS,
      body: { session_id: sessionId, attachment_id: attachmentId, visible },
    },
    decodePreviewOperation,
  )
}

export async function detachNativePreview(
  ctx: RestBridgeContext,
  sessionId: string,
  attachmentId: string,
): Promise<PreviewOperationResult> {
  return requestDecoded(
    ctx,
    '/preview/native/detach',
    {
      method: 'POST',
      timeoutMs: REQUEST_TIMEOUT_MS,
      body: { session_id: sessionId, attachment_id: attachmentId },
    },
    decodePreviewOperation,
  )
}

function invalidPreviewOwner(): never {
  throw new TypeError('invalid Toqraq preview session identity')
}
