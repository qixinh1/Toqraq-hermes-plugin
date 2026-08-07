/** Safe public-error decoding and Desktop localization. */

import type { JsonValue, PublicError } from '../contracts/generated.js'
import { ErrorEnvelopeRules, PublicErrorRules } from '../contracts/runtimeRules.js'
import {
  codePointLength,
  dataArray,
  dataRecord,
  enumValue,
  hasExactKeys,
  recordValue,
  safeKey,
  stringValue,
} from './safeData.js'

export type Translator = (key: string, ...args: unknown[]) => string

export interface TranslationContext {
  readonly i18n: { readonly t: Translator }
}

const ERROR_JSON = PublicErrorRules.errorJson

/** Public API failure with a domain code. */
export class ToqraqApiError extends Error {
  readonly code: PublicError['code']
  readonly category: PublicError['category']
  readonly parameters: PublicError['parameters']
  readonly details: PublicError['details']
  readonly traceId: PublicError['trace_id']

  constructor(failure: PublicError, message: string) {
    super(message)
    this.name = 'ToqraqApiError'
    this.code = failure.code
    this.category = failure.category
    this.parameters = failure.parameters
    this.details = failure.details
    this.traceId = failure.trace_id
  }
}

/**
 * Return a successful transport value or throw its exact safe error.
 */
export function unwrap(value: unknown, translate: Translator): unknown {
  const envelope = dataRecord(value)
  if (!envelope) {
    try {
      if (typeof value === 'object' && value !== null && Object.hasOwn(value, 'error')) {
        throw transportError(translate)
      }
    } catch (error) {
      if (error instanceof ToqraqApiError) throw error
      throw transportError(translate)
    }
    return value
  }
  if (!Object.hasOwn(envelope, 'error')) return value
  if (!hasExactKeys(envelope, ErrorEnvelopeRules.requiredKeys)) throw transportError(translate)
  const failure = decodePublicError(envelope.error)
  if (!failure) throw transportError(translate)
  throw new ToqraqApiError(failure, localizePublicError(translate, failure))
}

export function normalizeThrown(ctx: TranslationContext, error: unknown): ToqraqApiError {
  if (error instanceof ToqraqApiError) return error
  const translate = ctx.i18n.t
  const candidate = dataRecord(error)
  const response = dataRecord(candidate?.response)
  const body = candidate?.body ?? candidate?.data ?? response?.data
  try {
    unwrap(body, translate)
  } catch (nested) {
    if (nested instanceof ToqraqApiError) return nested
  }
  return transportError(translate)
}

export function decodePublicError(value: unknown): PublicError | null {
  try {
    return decodePublicErrorValue(value)
  } catch {
    return null
  }
}

function decodePublicErrorValue(value: unknown): PublicError | null {
  const source = recordValue(value, PublicErrorRules, 'public error')
  const code = stringValue(source.code, PublicErrorRules.code, 'error code')
  const category = enumValue(source.category, PublicErrorRules.category, 'error category')
  const traceId = stringValue(source.trace_id, PublicErrorRules.trace_id, 'trace id')
  const parameters = decodeFields(source.parameters, { remaining: ERROR_JSON.maximumNodes })
  const details = decodeFields(source.details, { remaining: ERROR_JSON.maximumNodes })
  if (!parameters || !details) return null
  return Object.freeze({
    code,
    category,
    parameters,
    details,
    trace_id: traceId,
  })
}

function decodeFields(
  value: unknown,
  budget: { remaining: number },
): Readonly<Record<string, JsonValue>> | null {
  const source = dataRecord(value)
  if (!source || Object.keys(source).length > ERROR_JSON.maximumFields) return null
  const result: Record<string, JsonValue> = Object.create(null)
  for (const [key, item] of Object.entries(source)) {
    if (!safeKey(key) || codePointLength(key) > ERROR_JSON.maximumKeyLength) return null
    const decoded = decodeJson(item, 1, budget)
    if (!decoded.ok) return null
    result[key] = decoded.value
  }
  return Object.freeze(result)
}

function decodeJson(
  value: unknown,
  depth: number,
  budget: { remaining: number },
): { readonly ok: true; readonly value: JsonValue } | { readonly ok: false } {
  budget.remaining -= 1
  if (budget.remaining < 0 || depth > ERROR_JSON.maximumDepth) return { ok: false }
  if (value === null || typeof value === 'boolean') return { ok: true, value }
  if (typeof value === 'number') {
    const safe =
      Number.isFinite(value) &&
      (!Number.isInteger(value) || Math.abs(value) <= ERROR_JSON.maximumSafeInteger)
    return safe ? { ok: true, value } : { ok: false }
  }
  if (typeof value === 'string') {
    return codePointLength(value) <= ERROR_JSON.maximumStringLength
      ? { ok: true, value }
      : { ok: false }
  }
  if (Array.isArray(value)) {
    const items = dataArray(value, ERROR_JSON.maximumSequenceItems)
    if (!items) return { ok: false }
    const result: JsonValue[] = []
    for (const item of items) {
      const decoded = decodeJson(item, depth + 1, budget)
      if (!decoded.ok) return { ok: false }
      result.push(decoded.value)
    }
    return { ok: true, value: Object.freeze(result) }
  }
  const source = dataRecord(value)
  if (!source || Object.keys(source).length > ERROR_JSON.maximumFields) return { ok: false }
  const result: Record<string, JsonValue> = Object.create(null)
  for (const [key, item] of Object.entries(source)) {
    if (!safeKey(key) || codePointLength(key) > ERROR_JSON.maximumKeyLength) return { ok: false }
    const decoded = decodeJson(item, depth + 1, budget)
    if (!decoded.ok) return { ok: false }
    result[key] = decoded.value
  }
  return { ok: true, value: Object.freeze(result) }
}

export function localizePublicError(translate: Translator, failure: PublicError): string {
  return translate('failure.withTraceId', translate(`errors.${failure.code}`), failure.trace_id)
}

export function localizeApiError(translate: Translator, error: ToqraqApiError): string {
  return translate('failure.withTraceId', translate(`errors.${error.code}`), error.traceId)
}

function transportError(translate: Translator): ToqraqApiError {
  const failure: PublicError = Object.freeze({
    code: 'transport.unavailable',
    category: 'unavailable',
    parameters: Object.freeze({}),
    details: Object.freeze({ retryable: true }),
    trace_id: globalThis.crypto.randomUUID(),
  })
  const message = translate(
    'failure.withTraceId',
    translate('failure.transportUnavailable'),
    failure.trace_id,
  )
  return new ToqraqApiError(failure, message)
}
