/** Exact non-localized values embedded in localized component presentation. */

import type { ComponentReleaseResult } from '../contracts/generated.js'

export function componentReleaseIdentity(release: ComponentReleaseResult): string {
  return `${release.component_id} / ${release.version} / ${release.build_id}`
}

export function componentReleaseTarget(release: ComponentReleaseResult): string {
  return `${release.platform} / ${release.architecture}`
}

export function formatExactBytes(bytes: number): string {
  return new Intl.NumberFormat().format(bytes)
}
