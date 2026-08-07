/** User-triggered start, stop, and pause orchestration for the viewport. */

import { useCallback } from 'react'
import { haptic, host } from '@hermes/plugin-sdk'
import type { PluginContext, usePluginI18n } from '@hermes/plugin-sdk'
import type { SessionResult } from '../contracts/generated.js'
import { normalizeThrown } from '../bridge/errorBoundary.js'
import { setPaused, startSession } from '../bridge/sessionClient.js'
import { canPauseGame } from '../state/pauseAvailability.js'
import type { RendererSessionStore } from '../state/rendererSessionStore.js'
import type { SessionSetupStatus, SetupView } from '../state/setupView.js'
import { stopGame } from '../state/stopGame.js'

interface GameLifecycleOptions {
  readonly ctx: PluginContext
  readonly t: ReturnType<typeof usePluginI18n>
  readonly store: RendererSessionStore
  readonly sessionId: string | null
  readonly sessionStatus: SessionSetupStatus
  readonly selectedSession: SessionResult | null
  readonly workspaceDir: string
  readonly setupView: SetupView
  readonly invalidateSetup: () => Promise<void>
}

interface GameLifecycleActions {
  readonly canPause: boolean
  readonly start: () => Promise<void>
  readonly stop: () => Promise<void>
  readonly togglePause: () => Promise<void>
}

export function useGameLifecycle({
  ctx,
  t,
  store,
  sessionId,
  sessionStatus,
  selectedSession,
  workspaceDir,
  setupView,
  invalidateSetup,
}: GameLifecycleOptions): GameLifecycleActions {
  const start = useCallback(async () => {
    if (!sessionId || sessionStatus !== 'ready') {
      host.notify({ kind: 'warning', message: t('notify.needSession') })
      return
    }
    if (!workspaceDir) {
      host.notify({ kind: 'warning', message: t('notify.needProject') })
      return
    }
    if (!setupView.startable) {
      host.notify({ kind: 'warning', message: blockedStartMessage(t, setupView) })
      return
    }
    const operation = store.beginSessionOperation(sessionId)
    if (operation === null) return
    try {
      try {
        await host.request('session.status', { session_id: sessionId })
      } catch {
        if (store.ownsSelectedSessionOperation(operation)) {
          host.notify({ kind: 'warning', message: t('notify.needSession') })
        }
        return
      }
      if (!store.ownsSelectedSessionOperation(operation)) return
      try {
        const started = await startSession(ctx, { projectDir: workspaceDir, hermesSession: sessionId })
        if (store.applySessionSnapshot(started)) {
          await invalidateSetup()
          haptic('success')
        }
      } catch (error: unknown) {
        if (store.ownsSelectedSessionOperation(operation)) {
          host.notifyError(normalizeThrown(ctx, error), t('notify.startFailed'))
        }
      }
    } finally {
      store.finishSessionOperation(operation)
    }
  }, [ctx, t, store, sessionId, sessionStatus, workspaceDir, setupView, invalidateSetup])

  const stop = useCallback(async () => {
    if (!selectedSession?.id) return
    const owner = selectedSession.id
    try {
      await stopGame(ctx, store, owner)
    } catch (error: unknown) {
      if (store.active && host.state.activeSessionId.get() === owner) {
        host.notifyError(normalizeThrown(ctx, error), t('notify.stopFailed'))
      }
    }
  }, [ctx, t, selectedSession, store])

  const togglePause = useCallback(async () => {
    if (!canPauseGame(selectedSession)) return
    const operation = store.beginSessionOperation(selectedSession.id)
    if (operation === null) return
    try {
      store.applySessionSnapshot(
        await setPaused(ctx, selectedSession.id, selectedSession.process_state !== 'paused'),
      )
    } catch (error: unknown) {
      if (store.ownsSelectedSessionOperation(operation)) {
        host.notifyError(normalizeThrown(ctx, error), t('notify.pauseFailed'))
      }
    } finally {
      store.finishSessionOperation(operation)
    }
  }, [ctx, t, selectedSession, store])

  return { canPause: canPauseGame(selectedSession), start, stop, togglePause }
}

function blockedStartMessage(
  t: ReturnType<typeof usePluginI18n>,
  setupView: SetupView,
): string {
  if (setupView.headline === 'host') return t('notify.unsupportedHost')
  if (setupView.headline === 'hostUnavailable') return t('notify.displayUnavailable')
  if (setupView.headline === 'install') return t('notify.componentRequired')
  return t('notify.projectInvalid')
}
