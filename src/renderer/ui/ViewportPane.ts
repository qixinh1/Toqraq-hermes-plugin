/** Native viewport pane composition. */

import { useCallback, useRef } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'
import { host, usePluginI18n, useValue } from '@hermes/plugin-sdk'
import type { PluginContext } from '@hermes/plugin-sdk'
import { useGameLifecycle } from '../hooks/useGameLifecycle.js'
import { useNativeDisplay } from '../hooks/useNativeDisplay.js'
import { useViewportSetup } from '../hooks/useViewportSetup.js'
import type { RendererSessionStore } from '../state/rendererSessionStore.js'
import { projectRuntimeState } from '../state/runtimePresentation.js'
import { Toolbar } from './Toolbar.js'
import { ViewportSurface } from './ViewportSurface.js'

interface ViewportPaneProps {
  readonly ctx: PluginContext
  readonly sessionStore: RendererSessionStore
}

export function ViewportPane({ ctx, sessionStore }: ViewportPaneProps) {
  const t = usePluginI18n('toqraq')
  const notifyDisplayError = useCallback(
    (error: Error) => host.notifyError(error, t('notify.displayFailed')),
    [t],
  )
  const game = useValue(sessionStore.gameState)
  const selectedSession =
    game.session?.id === game.readiness.sessionId ? game.session : null
  const runtimeState = projectRuntimeState(selectedSession)
  const sessionOwned =
    runtimeState === 'running' ||
    runtimeState === 'paused' ||
    runtimeState === 'stopping'
  const busy = useValue(sessionStore.busyState)
  const setup = useViewportSetup({
    ctx,
    sessionId: game.readiness.sessionId,
    sessionStatus: game.readiness.status,
    sessionOwned,
  })
  const lifecycle = useGameLifecycle({
    ctx,
    t,
    store: sessionStore,
    sessionId: game.readiness.sessionId,
    sessionStatus: game.readiness.status,
    selectedSession,
    workspaceDir: setup.workspaceDir,
    setupView: setup.view,
    invalidateSetup: setup.invalidate,
  })
  const areaRef = useRef<HTMLDivElement | null>(null)
  const previewView = useNativeDisplay({
    ctx,
    session: selectedSession,
    elementRef: areaRef,
    onError: notifyDisplayError,
  })

  return jsxs('div', {
    className: 'flex h-full flex-col',
    children: [
      sessionOwned &&
        selectedSession &&
        jsx(Toolbar, {
          projectDir: selectedSession.project_dir,
          runtime: selectedSession.runtime,
          processState: runtimeState,
          canPause: lifecycle.canPause,
          paused: selectedSession.process_state === 'paused',
          busy,
          onStop: lifecycle.stop,
          onTogglePause: lifecycle.togglePause,
        }),
      jsx(ViewportSurface, {
        ctx,
        areaRef,
        busy,
        setup: setup.setup,
        setupView: setup.view,
        setupRetrying: setup.retrying,
        previewView,
        previewError: selectedSession?.preview.error ?? null,
        onStart: lifecycle.start,
        onRetrySetup: setup.retry,
        onComponentTerminal: setup.componentTerminal,
      }),
    ],
  })
}
