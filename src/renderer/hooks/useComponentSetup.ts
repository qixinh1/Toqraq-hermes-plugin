/** Own component REST reconciliation for the mounted setup surface. */

import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery } from '@hermes/plugin-sdk'
import type { PluginContext } from '@hermes/plugin-sdk'
import type {
  ComponentJobAction,
  ComponentJobResult,
} from '../contracts/generated.js'
import {
  cancelComponentJob,
  getComponentJob,
  listActiveComponentJobs,
  listComponents,
  startComponentJob,
} from '../bridge/componentClient.js'
import { normalizeThrown, ToqraqApiError } from '../bridge/errorBoundary.js'
import {
  createComponentJobState,
  reconcileComponentJob,
  selectComponentJob,
} from '../state/componentJobs.js'
import {
  componentJobPollInterval,
  isMissingRecoveredComponentJob,
  nextTerminalComponentOperation,
  selectRecoverableComponentJob,
  shouldAdvanceComponentRecovery,
} from '../state/componentSetup.js'
import { COMPONENT_QUERY_RETRY_COUNT } from '../state/queryPolicy.js'
import {
  activeComponentJobsQueryKey,
  componentCatalogQueryKey,
  componentJobQueryKey,
} from '../state/queryKeys.js'

export function useComponentSetup(
  ctx: PluginContext,
  enabled: boolean,
  requiredReleaseIds: readonly string[],
  onTerminal: () => Promise<void>,
) {
  const [jobs, setJobs] = useState(createComponentJobState)
  const [operationId, setOperationId] = useState<string | null>(null)
  const [requesting, setRequesting] = useState(false)
  const [requestError, setRequestError] = useState<ToqraqApiError | null>(null)
  const observedTerminal = useRef('')
  const mounted = useRef(false)
  const requestInFlight = useRef(false)
  const requestRevision = useRef(0)
  const recoveredOperation = useRef('')
  const ignoredRecoveryOperation = useRef('')
  const planKey = requiredReleaseIds.join(':')
  const currentPlan = useRef(planKey)
  const job = operationId ? selectComponentJob(jobs, operationId) : null

  useEffect(() => {
    mounted.current = true
    return () => {
      // The backend owns the job across pane remounts; only local completions are discarded.
      mounted.current = false
      requestInFlight.current = false
      requestRevision.current += 1
    }
  }, [])

  useEffect(() => {
    if (currentPlan.current === planKey) return
    currentPlan.current = planKey
    requestRevision.current += 1
    requestInFlight.current = false
    recoveredOperation.current = ''
    ignoredRecoveryOperation.current = ''
    observedTerminal.current = ''
    setRequesting(false)
    setRequestError(null)
    setJobs(createComponentJobState())
    setOperationId(null)
  }, [planKey])

  const componentsQuery = useQuery({
    queryKey: componentCatalogQueryKey(),
    enabled,
    queryFn: () => listComponents(ctx),
    retry: COMPONENT_QUERY_RETRY_COUNT,
  })
  const activeJobsQuery = useQuery({
    queryKey: activeComponentJobsQueryKey(planKey),
    enabled: enabled && requiredReleaseIds.length > 0 && !operationId,
    queryFn: () => listActiveComponentJobs(ctx),
    retry: COMPONENT_QUERY_RETRY_COUNT,
    refetchOnMount: 'always',
  })
  const jobQuery = useQuery({
    queryKey: componentJobQueryKey(operationId),
    enabled: enabled && Boolean(operationId),
    queryFn: () => getComponentJob(ctx, operationId ?? ''),
    retry: COMPONENT_QUERY_RETRY_COUNT,
    refetchInterval: (query) =>
      componentJobPollInterval(
        query.state.data ?? null,
        query.state.status === 'error',
      ),
  })

  useEffect(() => {
    if (
      !enabled ||
      operationId ||
      !activeJobsQuery.data ||
      activeJobsQuery.error ||
      activeJobsQuery.isFetching
    ) {
      return
    }
    const recovered = selectRecoverableComponentJob(
      requiredReleaseIds,
      activeJobsQuery.data,
      ignoredRecoveryOperation.current,
    )
    if (!recovered) return
    setJobs((current) => reconcileComponentJob(current, recovered))
    recoveredOperation.current = recovered.operation_id
    setOperationId(recovered.operation_id)
  }, [
    activeJobsQuery.data,
    activeJobsQuery.error,
    activeJobsQuery.isFetching,
    enabled,
    operationId,
    planKey,
    requiredReleaseIds,
  ])

  useEffect(() => {
    if (!jobQuery.data || jobQuery.data.operation_id !== operationId) return
    setJobs((current) => reconcileComponentJob(current, jobQuery.data))
  }, [jobQuery.data, operationId])

  useEffect(() => {
    const errorCode = jobQuery.error instanceof ToqraqApiError ? jobQuery.error.code : ''
    if (
      !operationId ||
      !isMissingRecoveredComponentJob(
        operationId,
        recoveredOperation.current,
        errorCode,
      )
    ) {
      return
    }
    ignoredRecoveryOperation.current = operationId
    recoveredOperation.current = ''
    observedTerminal.current = operationId
    setOperationId(null)
    void onTerminal().catch((error) => {
      if (mounted.current && ignoredRecoveryOperation.current === operationId) {
        setRequestError(normalizeThrown(ctx, error))
      }
    })
  }, [ctx, jobQuery.error, onTerminal, operationId])

  useEffect(() => {
    if (!enabled) return
    const terminalOperation = nextTerminalComponentOperation(job, observedTerminal.current)
    if (!terminalOperation) return
    observedTerminal.current = terminalOperation
    const terminalPlan = currentPlan.current
    if (shouldAdvanceComponentRecovery(job, terminalOperation)) {
      ignoredRecoveryOperation.current = terminalOperation
      recoveredOperation.current = ''
      setOperationId(null)
    }
    void onTerminal().catch((error) => {
      if (mounted.current && currentPlan.current === terminalPlan) {
        setRequestError(normalizeThrown(ctx, error))
      }
    })
  }, [ctx, enabled, job, onTerminal])

  const performRequest = useCallback(
    async (request: () => Promise<ComponentJobResult>) => {
      if (!mounted.current || requestInFlight.current) return
      requestInFlight.current = true
      const revision = ++requestRevision.current
      setRequesting(true)
      setRequestError(null)
      try {
        const snapshot = await request()
        if (!mounted.current || requestRevision.current !== revision) return
        setJobs((current) => reconcileComponentJob(current, snapshot))
        recoveredOperation.current = ''
        setOperationId(snapshot.operation_id)
      } catch (error) {
        if (mounted.current && requestRevision.current === revision) {
          setRequestError(normalizeThrown(ctx, error))
        }
      } finally {
        if (requestRevision.current === revision) {
          requestInFlight.current = false
          if (mounted.current) setRequesting(false)
        }
      }
    },
    [ctx],
  )

  const start = useCallback(
    async (releaseId: string, action: ComponentJobAction) => {
      await performRequest(() => startComponentJob(ctx, releaseId, action))
    },
    [ctx, performRequest],
  )

  const cancel = useCallback(async () => {
    if (!operationId) return
    await performRequest(() => cancelComponentJob(ctx, operationId))
  }, [ctx, operationId, performRequest])

  const retry = useCallback(async () => {
    if (!job) return
    await start(job.release_id, job.action)
  }, [job, start])

  return Object.freeze({
    components: componentsQuery.data ?? null,
    componentsPending: componentsQuery.isPending,
    componentsRefreshing: componentsQuery.isFetching,
    componentsError: componentsQuery.error ?? null,
    job,
    jobError: operationId
      ? jobQuery.error ?? null
      : activeJobsQuery.error ?? null,
    requestError,
    requesting:
      requesting ||
      (enabled && requiredReleaseIds.length > 0 && !operationId && activeJobsQuery.isFetching),
    refreshComponents: async () => {
      setRequestError(null)
      await componentsQuery.refetch()
    },
    start,
    cancel,
    retry,
  })
}
