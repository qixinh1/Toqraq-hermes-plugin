/** Canonical TanStack cache identities for the Toqraq Desktop incarnation. */

const COMPONENT_CATALOG_KEY = Object.freeze(['toqraq', 'components'] as const)
const WORKSPACE_SETUP_ROOT = Object.freeze(['toqraq', 'setup'] as const)

export function hermesSessionQueryKey(
  sessionId: string | null,
): readonly ['toqraq', 'hermes-session', string | null] {
  return Object.freeze(['toqraq', 'hermes-session', sessionId] as const)
}

export function componentCatalogQueryKey(): typeof COMPONENT_CATALOG_KEY {
  return COMPONENT_CATALOG_KEY
}

export function activeComponentJobsQueryKey(
  planKey: string,
): readonly ['toqraq', 'component-jobs', 'active', string] {
  return Object.freeze(['toqraq', 'component-jobs', 'active', planKey] as const)
}

export function componentJobQueryKey(
  operationId: string | null,
): readonly ['toqraq', 'component-job', string | null] {
  return Object.freeze(['toqraq', 'component-job', operationId] as const)
}

export function workspaceSetupQueryRoot(): typeof WORKSPACE_SETUP_ROOT {
  return WORKSPACE_SETUP_ROOT
}

export function workspaceSetupQueryKey(
  ownerId: string | null,
  workspaceDir: string,
): readonly ['toqraq', 'setup', string | null, string] {
  return Object.freeze(['toqraq', 'setup', ownerId, workspaceDir] as const)
}
