/** Derive component setup controls directly from authoritative backend facts. */

import type {
  ComponentActiveJobsResult,
  ComponentJobResult,
  ComponentListResult,
  ComponentReleaseResult,
  SetupResult,
} from '../contracts/generated.js'

export const COMPONENT_JOB_POLL_INTERVAL_MS = 750
export const COMPONENT_JOB_RETRY_INTERVAL_MS = 4_000

export interface ComponentActions {
  readonly canPrepare: boolean
  readonly canRemove: boolean
  readonly canCancel: boolean
  readonly canRetry: boolean
  readonly active: boolean
}

interface ComponentCardState {
  readonly job: ComponentJobResult | null
  readonly actions: ComponentActions
  readonly actionDisabled: boolean
  readonly progress: number | null
}

type ComponentPrepareActionKey =
  | 'component.action.acceptAndPrepare'
  | 'component.action.acceptAndRepair'
  | 'component.action.prepare'
  | 'component.action.repair'

/** Resolve the backend-owned component plan without deriving package identity. */
export function resolveSetupComponentPlan(
  setup: SetupResult | null,
  components: ComponentListResult | null,
): readonly ComponentReleaseResult[] | null {
  if (!setup?.engine || !components) return null
  const releaseIds = setup.engine.required_component_release_ids
  if (releaseIds.length === 0) return null

  const catalog = new Map<string, ComponentReleaseResult>()
  for (const release of components.releases) {
    if (catalog.has(release.release_id)) return null
    catalog.set(release.release_id, release)
  }

  const requested = new Set<string>()
  const releases: ComponentReleaseResult[] = []
  for (const releaseId of releaseIds) {
    if (requested.has(releaseId)) return null
    requested.add(releaseId)
    const release = catalog.get(releaseId)
    if (!release) return null
    releases.push(release)
  }
  return Object.freeze(releases)
}

export function componentJobPollInterval(
  job: ComponentJobResult | null,
  readFailed = false,
): number | false {
  if (job && !isActiveComponentJob(job)) return false
  if (readFailed) return COMPONENT_JOB_RETRY_INTERVAL_MS
  return job ? COMPONENT_JOB_POLL_INTERVAL_MS : false
}

export function isActiveComponentJob(job: ComponentJobResult): boolean {
  return job.state === 'queued' || job.state === 'running' || job.state === 'cancelling'
}

/** Select only a unique active prepare job from the exact setup plan. */
export function selectRecoverableComponentJob(
  requiredReleaseIds: readonly string[],
  activeJobs: ComponentActiveJobsResult | null,
  ignoredOperationId = '',
): ComponentJobResult | null {
  if (!activeJobs || requiredReleaseIds.length === 0) return null
  const planIds = new Set(requiredReleaseIds)
  if (planIds.size !== requiredReleaseIds.length) return null

  const operationIds = new Set<string>()
  const jobsByRelease = new Map<string, ComponentJobResult>()
  for (const job of activeJobs.jobs) {
    if (
      !isActiveComponentJob(job) ||
      operationIds.has(job.operation_id) ||
      jobsByRelease.has(job.release_id)
    ) {
      return null
    }
    operationIds.add(job.operation_id)
    jobsByRelease.set(job.release_id, job)
  }

  for (const releaseId of requiredReleaseIds) {
    const job = jobsByRelease.get(releaseId)
    if (job?.action === 'prepare' && job.operation_id !== ignoredOperationId) return job
  }
  return null
}

/** Identify the retained-read race for one operation recovered after remount. */
export function isMissingRecoveredComponentJob(
  operationId: string | null,
  recoveredOperationId: string,
  errorCode: string,
): boolean {
  return Boolean(
    operationId &&
      operationId === recoveredOperationId &&
      errorCode === 'component.job_not_found',
  )
}

export function nextTerminalComponentOperation(
  job: ComponentJobResult | null,
  observedOperationId: string,
): string | null {
  if (!job || isActiveComponentJob(job) || job.operation_id === observedOperationId) {
    return null
  }
  return job.operation_id
}

/** A successful terminal result no longer needs to occupy the observed slot. */
export function shouldAdvanceComponentRecovery(
  job: ComponentJobResult | null,
  operationId: string,
): boolean {
  return Boolean(
    job &&
      job.operation_id === operationId &&
      job.state === 'ready',
  )
}

/** UI permissions are projections of authoritative release and job facts. */
export function deriveComponentActions(
  release: ComponentReleaseResult,
  job: ComponentJobResult | null,
): ComponentActions {
  const sameRelease = job?.release_id === release.release_id ? job : null
  const active = sameRelease ? isActiveComponentJob(sameRelease) : false
  const failed = sameRelease?.state === 'failed' || sameRelease?.state === 'cancelled'
  return Object.freeze({
    canPrepare: !active && release.readiness !== 'ready',
    canRemove: !active && !release.in_use && release.readiness === 'ready',
    canCancel: sameRelease?.state === 'queued' || sameRelease?.state === 'running',
    canRetry: Boolean(failed),
    active,
  })
}

export function componentProgress(job: ComponentJobResult | null): number | null {
  if (!job || job.total_bytes === 0) return null
  return Math.min(1, job.completed_bytes / job.total_bytes)
}

/** Project one release against the sole component operation visible to the pane. */
export function deriveComponentCardState(
  release: ComponentReleaseResult,
  job: ComponentJobResult | null,
  requesting: boolean,
): ComponentCardState {
  const releaseJob = job?.release_id === release.release_id ? job : null
  return Object.freeze({
    job: releaseJob,
    actions: deriveComponentActions(release, releaseJob),
    actionDisabled: requesting || Boolean(job && !releaseJob && isActiveComponentJob(job)),
    progress: componentProgress(releaseJob),
  })
}

export function componentPrepareActionKey(
  release: ComponentReleaseResult,
): ComponentPrepareActionKey {
  if (release.readiness === 'invalid') {
    return release.license.acceptance_required
      ? 'component.action.acceptAndRepair'
      : 'component.action.repair'
  }
  return release.license.acceptance_required
    ? 'component.action.acceptAndPrepare'
    : 'component.action.prepare'
}
