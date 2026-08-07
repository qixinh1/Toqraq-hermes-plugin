/** React lifetime owner for one revision-bound native preview attachment. */

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { PluginContext } from '@hermes/plugin-sdk'
import type { RectValue, SessionResult } from '../contracts/generated.js'
import { normalizeThrown } from '../bridge/errorBoundary.js'
import {
  attachNativePreview,
  detachNativePreview,
  followNativePreview,
  setNativePreviewVisible,
} from '../bridge/previewClient.js'
import { RectReporter } from '../bridge/rectReporter.js'
import { NativePreviewController } from '../state/nativePreviewController.js'
import { projectNativePreview } from '../state/nativePreviewProjection.js'
import type {
  NativePreviewAttachmentState,
  NativePreviewView,
} from '../state/nativePreviewProjection.js'

interface NativeDisplayOptions {
  readonly ctx: PluginContext
  readonly session: SessionResult | null
  readonly elementRef: { readonly current: Element | null }
  readonly onError: (error: Error) => void
}

/** Attach, report pane resize, hide, restore, and detach a native preview. */
export function useNativeDisplay({
  ctx,
  session,
  elementRef,
  onError,
}: NativeDisplayOptions): NativePreviewView {
  const [attachmentState, setAttachmentState] =
    useState<NativePreviewAttachmentState | null>(null)
  const errorRef = useRef(onError)
  errorRef.current = onError

  const preview = projectNativePreview(session, attachmentState)
  const sessionId = preview.attachment?.id ?? null
  const runRevision = preview.attachment?.run_revision ?? null

  useLayoutEffect(() => {
    if (preview.attachment === null && attachmentState !== null) {
      setAttachmentState(null)
    }
  }, [preview.attachment, attachmentState])

  useEffect(() => {
    const element = elementRef.current
    if (!sessionId || !runRevision || !element) {
      return undefined
    }

    let disposed = false
    const cleanupErrorSink = errorRef.current
    const attachmentId = globalThis.crypto.randomUUID()
    const controller = new NativePreviewController({
      sessionId,
      runRevision,
      documentVisible: document.visibilityState === 'visible',
      api: {
        attach: ({ paneRect }) =>
          attachNativePreview(ctx, {
            sessionId,
            attachmentId,
            paneRect,
          }),
        follow: (paneRect) =>
          followNativePreview(ctx, sessionId, attachmentId, paneRect),
        setVisible: (visible) =>
          setNativePreviewVisible(ctx, sessionId, attachmentId, visible),
        detach: () => detachNativePreview(ctx, sessionId, attachmentId),
      },
      scheduleRetry: (callback, delayMs) => window.setTimeout(callback, delayMs),
      cancelRetry: (handle) => {
        if (typeof handle === 'number') window.clearTimeout(handle)
      },
      onStatus: (nextStatus) => {
        if (!disposed) {
          setAttachmentState(Object.freeze({ sessionId, runRevision, status: nextStatus }))
        }
      },
      onError: (error) => {
        if (!disposed) errorRef.current(normalizeThrown(ctx, error))
      },
    })
    const reporter = new RectReporter(element, (rect: RectValue, settled: boolean) => {
      void controller.updatePane(rect, settled).then(() => {
        if (settled && document.visibilityState === 'visible') {
          void controller.setDocumentVisible(true)
        }
      })
    })
    reporter.start()

    const onVisibility = () => {
      const visible = document.visibilityState === 'visible'
      if (visible) reporter.refresh()
      else void controller.setDocumentVisible(false)
    }
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      disposed = true
      reporter.stop()
      document.removeEventListener('visibilitychange', onVisibility)
      void controller.close().catch((error) => {
        cleanupErrorSink(normalizeThrown(ctx, error))
      })
    }
  }, [ctx, sessionId, runRevision, elementRef])

  return preview.view
}
