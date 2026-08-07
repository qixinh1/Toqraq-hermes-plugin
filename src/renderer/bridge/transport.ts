/** REST transport boundary shared by the focused Toqraq clients. */

import { normalizeThrown, unwrap } from './errorBoundary.js'
import type { TranslationContext } from './errorBoundary.js'
import { dataRecord } from './safeData.js'

export interface RestRequestOptions {
  readonly method?: string
  readonly timeoutMs?: number
  readonly body?: unknown
}

export interface RestBridgeContext extends TranslationContext {
  readonly rest: (path: string, options?: RestRequestOptions) => Promise<unknown>
}

export const REQUEST_TIMEOUT_MS = 30 * 1000

export async function requestDecoded<T>(
  ctx: RestBridgeContext,
  path: string,
  options: RestRequestOptions,
  decode: (value: unknown) => T,
): Promise<T> {
  try {
    return decode(unwrap(await ctx.rest(path, options), ctx.i18n.t))
  } catch (error) {
    throw normalizeThrown(ctx, error)
  }
}

/** Preserve a component job's nullable error while unwrapping error-only responses. */
export async function requestComponentJobSnapshot<T>(
  ctx: RestBridgeContext,
  path: string,
  options: RestRequestOptions,
  decode: (value: unknown) => T,
): Promise<T> {
  try {
    const value = await ctx.rest(path, options)
    const source = dataRecord(value)
    const payload = source && Object.hasOwn(source, 'operation_id') ? value : unwrap(value, ctx.i18n.t)
    return decode(payload)
  } catch (error) {
    throw normalizeThrown(ctx, error)
  }
}
