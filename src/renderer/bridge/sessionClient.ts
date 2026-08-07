/** Session lifecycle and simulation requests. */

import type { SessionResult } from '../contracts/generated.js'
import { decodeOptionalSession, decodeSession } from './sessionDecoders.js'
import { REQUEST_TIMEOUT_MS, requestDecoded } from './transport.js'
import type { RestBridgeContext } from './transport.js'

interface SessionStartOptions {
  readonly projectDir: string
  readonly hermesSession: string
  readonly engine?: string
  readonly version?: string
}

export async function startSession(
  ctx: RestBridgeContext,
  options: SessionStartOptions,
): Promise<SessionResult> {
  return requestDecoded(
    ctx,
    '/sessions',
    {
      method: 'POST',
      timeoutMs: REQUEST_TIMEOUT_MS,
      body: {
        project_dir: options.projectDir,
        ...(options.engine ? { engine: options.engine } : {}),
        ...(options.version ? { version: options.version } : {}),
        hermes_session: options.hermesSession,
      },
    },
    (value) => ownedSession(value, options.hermesSession),
  )
}

export async function stopSession(
  ctx: RestBridgeContext,
  sessionId: string,
  runRevision: number,
): Promise<SessionResult> {
  return requestDecoded(
    ctx,
    `/sessions/${encodeURIComponent(sessionId)}`,
    { method: 'DELETE', timeoutMs: REQUEST_TIMEOUT_MS, body: { run_revision: runRevision } },
    (value) => ownedSessionRun(value, sessionId, runRevision),
  )
}

export async function setPaused(
  ctx: RestBridgeContext,
  sessionId: string,
  paused: boolean,
): Promise<SessionResult> {
  return requestDecoded(
    ctx,
    `/sessions/${encodeURIComponent(sessionId)}/pause`,
    { method: 'POST', timeoutMs: REQUEST_TIMEOUT_MS, body: { paused } },
    (value) => ownedSession(value, sessionId),
  )
}

export async function getSession(
  ctx: RestBridgeContext,
  sessionId: string,
): Promise<SessionResult | null> {
  return requestDecoded(
    ctx,
    `/sessions/${encodeURIComponent(sessionId)}`,
    { timeoutMs: REQUEST_TIMEOUT_MS },
    (value) => {
      const session = decodeOptionalSession(value)
      if (session !== null && session.id !== sessionId) invalidSessionIdentity()
      return session
    },
  )
}

function ownedSession(value: unknown, sessionId: string): SessionResult {
  const session = decodeSession(value)
  if (session.id !== sessionId) invalidSessionIdentity()
  return session
}

function ownedSessionRun(value: unknown, sessionId: string, runRevision: number): SessionResult {
  const session = ownedSession(value, sessionId)
  if (session.run_revision !== runRevision) invalidSessionIdentity()
  return session
}

function invalidSessionIdentity(): never {
  throw new TypeError('invalid Toqraq session identity')
}
