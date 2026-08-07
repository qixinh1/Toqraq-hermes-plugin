/** Plugin-lifetime projection of public Hermes workspace state. */

import { absoluteWorkspace } from './workspace.js'
import type { ReadableValue } from './readableValue.js'

const OPEN_GATEWAY_STATE = 'open'

interface WorkspaceContextSyncDependencies<Result> {
  activeSessionId: ReadableValue<string | null>
  cwd: ReadableValue<string>
  gateway: ReadableValue<string>
  fetch(ownerId: string, workspaceDir: string): Promise<Result>
}

/** Start one headless workspace synchronizer for the plugin incarnation. */
export function startWorkspaceContextSync<Result>(
  dependencies: WorkspaceContextSyncDependencies<Result>,
): () => void {
  let disposed = false
  let currentKey = ''

  const reconcile = (): void => {
    if (disposed) return
    const ownerId = dependencies.activeSessionId.get()
    if (!ownerId || dependencies.gateway.get() !== OPEN_GATEWAY_STATE) {
      currentKey = ''
      return
    }
    const workspaceDir = absoluteWorkspace(dependencies.cwd.get())
    const nextKey = JSON.stringify([ownerId, workspaceDir])
    if (nextKey === currentKey) return
    currentKey = nextKey
    try {
      void dependencies.fetch(ownerId, workspaceDir).catch(() => {
        if (!disposed && currentKey === nextKey) currentKey = ''
      })
    } catch {
      if (currentKey === nextKey) currentKey = ''
    }
  }

  const subscriptions = [
    dependencies.activeSessionId.subscribe(reconcile),
    dependencies.cwd.subscribe(reconcile),
    dependencies.gateway.subscribe(reconcile),
  ]
  return () => {
    if (disposed) return
    disposed = true
    for (const unsubscribe of subscriptions.reverse()) unsubscribe()
  }
}
