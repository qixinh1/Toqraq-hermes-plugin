/** Exact decoder for idempotent native-preview acknowledgements. */

import type { PreviewOperationResult } from '../contracts/generated.js'
import { PreviewOperationResultRules } from '../contracts/runtimeRules.js'
import { booleanValue, recordValue } from './safeData.js'

export function decodePreviewOperation(value: unknown): PreviewOperationResult {
  const source = recordValue(value, PreviewOperationResultRules, 'preview operation')
  return Object.freeze({ ok: booleanValue(source.ok, 'preview operation acknowledgement') })
}
