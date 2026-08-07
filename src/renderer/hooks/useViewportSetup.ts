/** Workspace setup projection and its cache invalidation ownership. */

import { useCallback } from 'react'
import { host, queryClient, useQuery, useValue } from '@hermes/plugin-sdk'
import type { PluginContext } from '@hermes/plugin-sdk'
import type { SetupResult } from '../contracts/generated.js'
import { checkSetup, syncWorkspaceContext } from '../bridge/setupClient.js'
import {
  SETUP_QUERY_RETRY_COUNT,
  SETUP_QUERY_RETRY_DELAY_MS,
} from '../state/queryPolicy.js'
import {
  componentCatalogQueryKey,
  workspaceSetupQueryKey,
} from '../state/queryKeys.js'
import { deriveSetupView, shouldCheckSetup } from '../state/setupView.js'
import type { SessionSetupStatus, SetupView } from '../state/setupView.js'
import { absoluteWorkspace } from '../state/workspace.js'

interface ViewportSetupOptions {
  readonly ctx: PluginContext
  readonly sessionId: string | null
  readonly sessionStatus: SessionSetupStatus
  readonly sessionOwned: boolean
}

interface ViewportSetupProjection {
  readonly workspaceDir: string
  readonly setup: SetupResult | null
  readonly view: SetupView
  readonly retrying: boolean
  readonly retry: () => void
  readonly invalidate: () => Promise<void>
  readonly componentTerminal: () => Promise<void>
}

export function useViewportSetup({
  ctx,
  sessionId,
  sessionStatus,
  sessionOwned,
}: ViewportSetupOptions): ViewportSetupProjection {
  const workspaceDir = absoluteWorkspace(useValue(host.state.cwd))
  const enabled = shouldCheckSetup(workspaceDir, sessionOwned)
  const queryKey = workspaceSetupQueryKey(sessionId, workspaceDir)
  const setupQuery = useQuery({
    queryKey,
    enabled,
    queryFn: () =>
      sessionId
        ? syncWorkspaceContext(ctx, sessionId, { projectDir: workspaceDir })
        : checkSetup(ctx, { projectDir: workspaceDir }),
    retry: SETUP_QUERY_RETRY_COUNT,
    retryDelay: SETUP_QUERY_RETRY_DELAY_MS,
    staleTime: Infinity,
  })
  const setup = enabled ? (setupQuery.data ?? null) : null
  const view = deriveSetupView({
    setup,
    sessionStatus,
    workspacePresent: Boolean(workspaceDir),
    checking: enabled && setupQuery.isPending,
    failed: enabled && setupQuery.isError,
  })
  const invalidate = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey })
  }, [sessionId, workspaceDir])
  const componentTerminal = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: componentCatalogQueryKey() }),
      queryClient.invalidateQueries({ queryKey }),
    ])
  }, [sessionId, workspaceDir])
  const retry = useCallback(() => {
    void setupQuery.refetch()
  }, [setupQuery])

  return {
    workspaceDir,
    setup,
    view,
    retrying: setupQuery.isFetching,
    retry,
    invalidate,
    componentTerminal,
  }
}
