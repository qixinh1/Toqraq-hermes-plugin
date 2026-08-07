/** One renderer action for stopping a game owned by a Hermes session. */

import type { PluginContext } from '@hermes/plugin-sdk'
import { getSession, stopSession } from '../bridge/sessionClient.js'
import type { RendererSessionStore } from './rendererSessionStore.js'
import { executeStopGame } from './stopGameFlow.js'

export async function stopGame(
  ctx: PluginContext,
  store: RendererSessionStore,
  sessionId: string,
): Promise<boolean> {
  return executeStopGame(ctx, sessionId, {
    beginSessionOperation: (owner) => store.beginSessionOperation(owner),
    finishSessionOperation: (token) => store.finishSessionOperation(token),
    currentSession: () => store.currentSession(),
    applySessionSnapshot: (session) => store.applySessionSnapshot(session),
    clearSessionRun: (owner, runRevision) => store.clearSessionRun(owner, runRevision),
    getSession,
    stopSession,
  })
}
