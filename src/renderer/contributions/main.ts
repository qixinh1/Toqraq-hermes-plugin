/** Hermes desktop contributions for Toqraq. */

import { jsx } from 'react/jsx-runtime'
import {
  atom,
  host,
  PANES_AREA,
  PALETTE_AREA,
  queryClient,
  STATUSBAR_AREAS,
} from '@hermes/plugin-sdk'
import type { PluginContext, PluginDisposer } from '@hermes/plugin-sdk'
import { normalizeThrown } from '../bridge/errorBoundary.js'
import { openEvents } from '../bridge/sessionEventClient.js'
import { getSession } from '../bridge/sessionClient.js'
import { syncWorkspaceContext } from '../bridge/setupClient.js'
import {
  HERMES_SESSION_ERROR_REFRESH_INTERVAL_MS,
  SETUP_QUERY_RETRY_COUNT,
  SETUP_QUERY_RETRY_DELAY_MS,
} from '../state/queryPolicy.js'
import {
  hermesSessionQueryKey,
  workspaceSetupQueryKey,
  workspaceSetupQueryRoot,
} from '../state/queryKeys.js'
import { RendererSessionStore } from '../state/rendererSessionStore.js'
import { startRendererSessionSync } from '../state/rendererSessionSync.js'
import { stopGame } from '../state/stopGame.js'
import { startWorkspaceContextSync } from '../state/workspaceContextSync.js'
import { StatusChip } from '../ui/StatusChip.js'
import { ViewportPane } from '../ui/ViewportPane.js'

/** Register the viewport pane and its lightweight controls. */
export function registerContributions(ctx: PluginContext): PluginDisposer {
  const sessionStore = new RendererSessionStore(atom)
  ctx.own(() => sessionStore.dispose())
  ctx.own(
    startRendererSessionSync({
      activeSessionId: host.state.activeSessionId,
      gateway: host.state.gateway,
      store: sessionStore,
      readHermesStatus: (sessionId) =>
        queryClient.fetchQuery({
          queryKey: hermesSessionQueryKey(sessionId),
          queryFn: () => host.request('session.status', { session_id: sessionId }),
          retry: false,
          staleTime: 0,
        }),
      cancelHermesStatus: (sessionId) => {
        void queryClient.cancelQueries({
          queryKey: hermesSessionQueryKey(sessionId),
          exact: true,
        })
      },
      readSession: (sessionId) => getSession(ctx, sessionId),
      openEvents: (sessionId, onEvent, onError) =>
        openEvents(ctx, sessionId, onEvent, onError),
      scheduleRetry: (retry) => {
        const timer = globalThis.setTimeout(
          retry,
          HERMES_SESSION_ERROR_REFRESH_INTERVAL_MS,
        )
        return () => globalThis.clearTimeout(timer)
      },
      onLoadError: (error) => {
        host.notifyError(
          normalizeThrown(ctx, error),
          ctx.i18n.t('notify.loadFailed'),
        )
      },
      onEventError: (error) => {
        host.notifyError(
          normalizeThrown(ctx, error),
          ctx.i18n.t('notify.displayFailed'),
        )
      },
      onEnded: (session) => {
        if (session.process_state === 'crashed') {
          host.notify({
            kind: 'warning',
            message: ctx.i18n.t('notify.sessionCrashed', session.exit_code),
          })
          return
        }
        host.notify({ kind: 'info', message: ctx.i18n.t('notify.sessionEnded') })
      },
    }),
  )
  ctx.own(() => {
    void queryClient.cancelQueries({ queryKey: workspaceSetupQueryRoot() })
  })
  ctx.own(
    startWorkspaceContextSync({
      activeSessionId: host.state.activeSessionId,
      cwd: host.state.cwd,
      gateway: host.state.gateway,
      fetch: (ownerId, workspaceDir) =>
        queryClient.fetchQuery({
          queryKey: workspaceSetupQueryKey(ownerId, workspaceDir),
          queryFn: () =>
            syncWorkspaceContext(
              ctx,
              ownerId,
              workspaceDir ? { projectDir: workspaceDir } : {},
            ),
          retry: SETUP_QUERY_RETRY_COUNT,
          retryDelay: SETUP_QUERY_RETRY_DELAY_MS,
          staleTime: 0,
        }),
    }),
  )
  return ctx.registerMany([
    {
      id: 'pane',
      area: PANES_AREA,
      title: ctx.i18n.t('pane.title'),
      data: {
        collapsible: true,
        placement: 'bottom',
        dock: { pane: 'workspace', pos: 'bottom' },
        height: '32vh',
        minHeight: '10rem',
      },
      render: () => jsx(ViewportPane, { ctx, sessionStore }),
    },
    {
      id: 'status',
      area: STATUSBAR_AREAS.right,
      order: 140,
      render: () => jsx(StatusChip, { sessionStore }),
    },
    {
      id: 'palette.stop',
      area: PALETTE_AREA,
      data: {
        id: 'toqraq.stop',
        label: ctx.i18n.t('palette.stop'),
        keywords: ['game', 'engine', 'toqraq'],
        run: async () => {
          const sessionId = sessionStore.currentSession()?.id
          if (!sessionId) return
          try {
            await stopGame(ctx, sessionStore, sessionId)
          } catch (error) {
            if (
              sessionStore.active &&
              sessionStore.currentGame().readiness.sessionId === sessionId
            ) {
              host.notifyError(
                normalizeThrown(ctx, error),
                ctx.i18n.t('notify.stopFailed'),
              )
            }
          }
        },
      },
    },
  ])
}
