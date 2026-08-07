/** Accept only resolved absolute workspace roots published by Hermes. */

const WINDOWS_DRIVE_ROOT = /^[A-Za-z]:[\\/]/
const WINDOWS_UNC_ROOT = /^\\\\[^\\/]+[\\/][^\\/]+(?:[\\/]|$)/

/** Return an absolute host path, or empty while Hermes has not resolved one. */
export function absoluteWorkspace(value: unknown): string {
  if (typeof value !== 'string') return ''
  const candidate = value.trim()
  if (
    candidate.startsWith('/') ||
    WINDOWS_DRIVE_ROOT.test(candidate) ||
    WINDOWS_UNC_ROOT.test(candidate)
  ) {
    return candidate
  }
  return ''
}
