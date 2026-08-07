/** Strict decoders for managed-component REST results. */

import type {
  ComponentActiveJobsResult,
  ComponentJobAction,
  ComponentJobResult,
  ComponentJobState,
  ComponentListResult,
  ComponentReleaseResult,
  ComponentWorkPhase,
  PublicError,
} from '../contracts/generated.js'
import {
  ComponentActiveJobsResultRules,
  ComponentJobResultRules,
  ComponentLicenseResultRules,
  ComponentListResultRules,
  ComponentReleaseResultRules,
  ComponentSourceResultRules,
} from '../contracts/runtimeRules.js'
import { decodePublicError } from './errorBoundary.js'
import {
  arrayValue,
  booleanValue,
  enumValue,
  integerValue,
  invalid,
  recordValue,
  stringArrayValue,
  stringValue,
} from './safeData.js'

const ACTIVE_JOB_STATES: ReadonlySet<ComponentJobState> = new Set([
  'queued',
  'running',
  'cancelling',
])
const PREPARE_PHASES: ReadonlySet<ComponentWorkPhase> = new Set([
  'checking',
  'downloading',
  'installing',
  'verifying',
  'ready',
])
const REMOVE_PHASES: ReadonlySet<ComponentWorkPhase> = new Set(['checking', 'removing', 'ready'])

export function decodeComponentList(value: unknown): ComponentListResult {
  const source = recordValue(value, ComponentListResultRules, 'component list')
  const releases = arrayValue(
    source.releases,
    ComponentListResultRules.releases,
    'component releases',
  )
  return Object.freeze({ releases: Object.freeze(releases.map(decodeRelease)) })
}

export function decodeActiveComponentJobs(value: unknown): ComponentActiveJobsResult {
  const source = recordValue(value, ComponentActiveJobsResultRules, 'active component jobs')
  const jobs = arrayValue(
    source.jobs,
    ComponentActiveJobsResultRules.jobs,
    'active component jobs',
  ).map(decodeComponentJob)
  const operationIds = new Set<string>()
  const releaseIds = new Set<string>()
  for (const job of jobs) {
    if (
      !ACTIVE_JOB_STATES.has(job.state) ||
      operationIds.has(job.operation_id) ||
      releaseIds.has(job.release_id)
    ) {
      invalid('active component jobs')
    }
    operationIds.add(job.operation_id)
    releaseIds.add(job.release_id)
  }
  return Object.freeze({ jobs: Object.freeze(jobs) })
}

export function decodeComponentJob(value: unknown): ComponentJobResult {
  const source = recordValue(value, ComponentJobResultRules, 'component job')
  const action = enumValue(source.action, ComponentJobResultRules.action, 'component job action')
  const state = enumValue(source.state, ComponentJobResultRules.state, 'component job state')
  const phase = enumValue(source.phase, ComponentJobResultRules.phase, 'component job phase')
  const completedBytes = integerValue(
    source.completed_bytes,
    ComponentJobResultRules.completed_bytes,
    'component job completed bytes',
  )
  const totalBytes = integerValue(
    source.total_bytes,
    ComponentJobResultRules.total_bytes,
    'component job total bytes',
  )
  const errorValue = Object.hasOwn(source, 'error') ? source.error : null
  const error = errorValue === null ? null : decodePublicError(errorValue)
  if (errorValue !== null && !error) invalid('component job error')
  validateJob(action, state, phase, completedBytes, totalBytes, error)
  return Object.freeze({
    operation_id: stringValue(
      source.operation_id,
      ComponentJobResultRules.operation_id,
      'operation id',
    ),
    release_id: stringValue(source.release_id, ComponentJobResultRules.release_id, 'release id'),
    component_id: stringValue(
      source.component_id,
      ComponentJobResultRules.component_id,
      'component id',
    ),
    action,
    state,
    phase,
    completed_bytes: completedBytes,
    total_bytes: totalBytes,
    revision: integerValue(
      source.revision,
      ComponentJobResultRules.revision,
      'component job revision',
    ),
    error,
  })
}

function decodeRelease(value: unknown): ComponentReleaseResult {
  const source = recordValue(value, ComponentReleaseResultRules, 'component release')
  const capabilities = stringArrayValue(
    source.capabilities,
    ComponentReleaseResultRules.capabilities,
    'component capability',
  )
  const componentKind = enumValue(source.kind, ComponentReleaseResultRules.kind, 'component kind')
  const readiness = enumValue(
    source.readiness,
    ComponentReleaseResultRules.readiness,
    'component readiness',
  )
  return Object.freeze({
    release_id: stringValue(source.release_id, ComponentReleaseResultRules.release_id, 'release id'),
    component_id: stringValue(
      source.component_id,
      ComponentReleaseResultRules.component_id,
      'component id',
    ),
    kind: componentKind,
    label: stringValue(source.label, ComponentReleaseResultRules.label, 'component label'),
    version: stringValue(source.version, ComponentReleaseResultRules.version, 'component version'),
    build_id: stringValue(source.build_id, ComponentReleaseResultRules.build_id, 'component build id'),
    platform: stringValue(
      source.platform,
      ComponentReleaseResultRules.platform,
      'component platform',
    ),
    architecture: stringValue(
      source.architecture,
      ComponentReleaseResultRules.architecture,
      'component architecture',
    ),
    package_bytes: integerValue(
      source.package_bytes,
      ComponentReleaseResultRules.package_bytes,
      'package bytes',
    ),
    installed_bytes: integerValue(
      source.installed_bytes,
      ComponentReleaseResultRules.installed_bytes,
      'installed bytes',
    ),
    package_sha256: stringValue(
      source.package_sha256,
      ComponentReleaseResultRules.package_sha256,
      'package digest',
    ),
    source: decodeSource(source.source),
    license: decodeLicense(source.license),
    authentication_required: booleanValue(
      source.authentication_required,
      'authentication requirement',
    ),
    capabilities,
    readiness,
    in_use: booleanValue(source.in_use, 'component lease state'),
  })
}

function decodeSource(value: unknown): ComponentReleaseResult['source'] {
  const source = recordValue(value, ComponentSourceResultRules, 'component source')
  return Object.freeze({
    publisher: stringValue(
      source.publisher,
      ComponentSourceResultRules.publisher,
      'component publisher',
    ),
    package_url: stringValue(
      source.package_url,
      ComponentSourceResultRules.package_url,
      'component package URL',
    ),
    provenance_url: stringValue(
      source.provenance_url,
      ComponentSourceResultRules.provenance_url,
      'component provenance URL',
    ),
  })
}

function decodeLicense(value: unknown): ComponentReleaseResult['license'] {
  const source = recordValue(value, ComponentLicenseResultRules, 'component license')
  return Object.freeze({
    identifier: stringValue(
      source.identifier,
      ComponentLicenseResultRules.identifier,
      'license identifier',
    ),
    name: stringValue(source.name, ComponentLicenseResultRules.name, 'license name'),
    url: stringValue(source.url, ComponentLicenseResultRules.url, 'license URL'),
    acceptance_required: booleanValue(
      source.acceptance_required,
      'license acceptance requirement',
    ),
  })
}

function validateJob(
  action: ComponentJobAction,
  state: ComponentJobState,
  phase: ComponentWorkPhase,
  completedBytes: number,
  totalBytes: number,
  error: PublicError | null,
): void {
  const allowedPhases = action === 'prepare' ? PREPARE_PHASES : REMOVE_PHASES
  if (!allowedPhases.has(phase)) invalid('component job action phase')
  if (completedBytes > totalBytes) invalid('component job progress')
  if ((state === 'failed') !== (error !== null)) invalid('component job failure state')
  if ((state === 'ready') !== (phase === 'ready')) invalid('component job ready phase')
  if (state === 'ready' && completedBytes !== totalBytes) invalid('component job completion')
  if (state === 'queued' && phase !== 'checking') invalid('component job queued phase')
}
