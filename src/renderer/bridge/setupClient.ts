/** Project and managed-runtime setup projections. */

import type { SetupResult } from '../contracts/generated.js'
import { decodeOptionalSetup, decodeSetup } from './decoders.js'
import { REQUEST_TIMEOUT_MS, requestDecoded } from './transport.js'
import type { RestBridgeContext } from './transport.js'

export interface SetupOptions {
  readonly projectDir?: string
  readonly engine?: string
  readonly version?: string
}

export async function checkSetup(
  ctx: RestBridgeContext,
  options: SetupOptions = {},
): Promise<SetupResult> {
  return requestDecoded(
    ctx,
    '/setup',
    { method: 'POST', timeoutMs: REQUEST_TIMEOUT_MS, body: setupBody(options) },
    decodeSetup,
  )
}

export async function syncWorkspaceContext(
  ctx: RestBridgeContext,
  sessionId: string,
  options: SetupOptions = {},
): Promise<SetupResult | null> {
  return requestDecoded(
    ctx,
    `/workspace-context/${encodeURIComponent(sessionId)}`,
    { method: 'PUT', timeoutMs: REQUEST_TIMEOUT_MS, body: setupBody(options) },
    decodeOptionalSetup,
  )
}

function setupBody(options: SetupOptions): Readonly<Record<string, string>> {
  return {
    ...(options.projectDir ? { project_dir: options.projectDir } : {}),
    ...(options.engine ? { engine: options.engine } : {}),
    ...(options.version ? { version: options.version } : {}),
  }
}
