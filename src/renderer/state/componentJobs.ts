/** Immutable component-job state with authoritative revision reconciliation. */

import type { ComponentJobResult } from '../contracts/generated.js'

export type ComponentJobState = Readonly<{
  byOperationId: Readonly<Record<string, ComponentJobResult>>
}>

const EMPTY_JOBS: Readonly<Record<string, ComponentJobResult>> = Object.freeze({})

export function createComponentJobState(): ComponentJobState {
  return Object.freeze({ byOperationId: EMPTY_JOBS })
}

/** Replace one operation with a newer complete server snapshot. */
export function reconcileComponentJob(
  state: ComponentJobState,
  snapshot: ComponentJobResult,
): ComponentJobState {
  const current = state.byOperationId[snapshot.operation_id]
  if (current && current.revision >= snapshot.revision) return state

  return Object.freeze({
    byOperationId: Object.freeze({
      ...state.byOperationId,
      [snapshot.operation_id]: snapshot,
    }),
  })
}

export function selectComponentJob(
  state: ComponentJobState,
  operationId: string,
): ComponentJobResult | null {
  return Object.hasOwn(state.byOperationId, operationId)
    ? state.byOperationId[operationId] ?? null
    : null
}
