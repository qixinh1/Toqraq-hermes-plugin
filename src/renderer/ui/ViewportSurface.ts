/** Native game-window host surface. */

import { jsx, jsxs } from 'react/jsx-runtime'
import { usePluginI18n } from '@hermes/plugin-sdk'
import type { PluginContext } from '@hermes/plugin-sdk'
import type { PublicError, SetupResult } from '../contracts/generated.js'
import { localizePublicError } from '../bridge/errorBoundary.js'
import type { NativePreviewView } from '../state/nativePreviewProjection.js'
import type { deriveSetupView } from '../state/setupView.js'
import { SetupGuide } from './SetupGuide.js'

interface ViewportSurfaceProps {
  readonly ctx: PluginContext
  readonly areaRef: { current: HTMLDivElement | null }
  readonly busy: boolean
  readonly setup: SetupResult | null
  readonly setupView: ReturnType<typeof deriveSetupView>
  readonly setupRetrying: boolean
  readonly previewView: NativePreviewView
  readonly previewError: PublicError | null
  readonly onStart: () => void
  readonly onRetrySetup: () => void
  readonly onComponentTerminal: () => Promise<void>
}

export function ViewportSurface({
  ctx,
  areaRef,
  busy,
  setup,
  setupView,
  setupRetrying,
  previewView,
  previewError,
  onStart,
  onRetrySetup,
  onComponentTerminal,
}: ViewportSurfaceProps) {
  const t = usePluginI18n('toqraq')
  let child: ReturnType<typeof jsx>
  if (previewView === 'setup') {
    child = jsx(SetupGuide, {
      ctx,
      setup,
      view: setupView,
      retrying: setupRetrying,
      busy,
      onStart,
      onRetry: onRetrySetup,
      onComponentTerminal,
    })
  } else {
    child = previewStatus(t, previewView, previewError)
  }
  return jsx('div', {
    ref: areaRef,
    role: 'region',
    'aria-label': t('pane.previewLabel'),
    className:
      'relative flex-1 min-h-[10rem] flex items-center justify-center overflow-hidden text-xs text-(--ui-text-tertiary)',
    children: child,
  })
}

function previewStatus(
  t: ReturnType<typeof usePluginI18n>,
  view: Exclude<NativePreviewView, 'setup'>,
  error: PublicError | null,
) {
  const failed = view === 'failed'
  return jsxs('div', {
    ...(failed
      ? { role: 'alert', 'aria-atomic': true }
      : { role: 'status', 'aria-live': 'polite', 'aria-atomic': true }),
    className: 'space-y-1 text-center',
    children: [
      jsx('p', { children: previewMessage(t, view) }),
      failed && error &&
        jsx('p', {
          className: 'text-destructive',
          children: localizePublicError(t, error),
        }),
    ],
  })
}

function previewMessage(
  t: ReturnType<typeof usePluginI18n>,
  view: Exclude<NativePreviewView, 'setup'>,
): string {
  if (view === 'failed') return t('pane.previewFailed')
  if (view === 'retrying') return t('pane.nativeRetrying')
  if (view === 'unavailable') return t('pane.previewUnavailable')
  if (view === 'attached') return t('pane.nativeActive')
  return t('pane.nativeConnecting')
}
