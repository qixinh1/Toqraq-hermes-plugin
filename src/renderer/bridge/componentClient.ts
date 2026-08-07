/** Managed-component reads and lifecycle requests. */

import type {
  ComponentActiveJobsResult,
  ComponentJobAction,
  ComponentJobResult,
  ComponentListResult,
} from '../contracts/generated.js'
import {
  decodeActiveComponentJobs,
  decodeComponentJob,
  decodeComponentList,
} from './componentDecoders.js'
import {
  REQUEST_TIMEOUT_MS,
  requestComponentJobSnapshot,
  requestDecoded,
} from './transport.js'
import type { RestBridgeContext } from './transport.js'

export async function listComponents(ctx: RestBridgeContext): Promise<ComponentListResult> {
  return requestDecoded(ctx, '/components', { timeoutMs: REQUEST_TIMEOUT_MS }, decodeComponentList)
}

export async function listActiveComponentJobs(
  ctx: RestBridgeContext,
): Promise<ComponentActiveJobsResult> {
  return requestDecoded(
    ctx,
    '/component-jobs/active',
    { timeoutMs: REQUEST_TIMEOUT_MS },
    decodeActiveComponentJobs,
  )
}

export async function startComponentJob(
  ctx: RestBridgeContext,
  releaseId: string,
  action: ComponentJobAction,
): Promise<ComponentJobResult> {
  return requestComponentJobSnapshot(
    ctx,
    '/component-jobs',
    {
      method: 'POST',
      timeoutMs: REQUEST_TIMEOUT_MS,
      body: { release_id: releaseId, action },
    },
    (value) => {
      const job = decodeComponentJob(value)
      if (job.release_id !== releaseId || job.action !== action) invalidComponentJobIdentity()
      return job
    },
  )
}

export async function getComponentJob(
  ctx: RestBridgeContext,
  operationId: string,
): Promise<ComponentJobResult> {
  return requestComponentJobSnapshot(
    ctx,
    `/component-jobs/${encodeURIComponent(operationId)}`,
    { timeoutMs: REQUEST_TIMEOUT_MS },
    (value) => {
      const job = decodeComponentJob(value)
      if (job.operation_id !== operationId) invalidComponentJobIdentity()
      return job
    },
  )
}

export async function cancelComponentJob(
  ctx: RestBridgeContext,
  operationId: string,
): Promise<ComponentJobResult> {
  return requestComponentJobSnapshot(
    ctx,
    `/component-jobs/${encodeURIComponent(operationId)}/cancel`,
    { method: 'POST', timeoutMs: REQUEST_TIMEOUT_MS },
    (value) => {
      const job = decodeComponentJob(value)
      if (job.operation_id !== operationId) invalidComponentJobIdentity()
      return job
    },
  )
}

function invalidComponentJobIdentity(): never {
  throw new TypeError('invalid Toqraq component job identity')
}
