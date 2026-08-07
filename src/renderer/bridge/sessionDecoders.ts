/** Exact decoders for authoritative session snapshots and events. */

import type {
  FeatureReadinessResult,
  PreviewReadinessResult,
  PreviewSurfaceResult,
  SessionEvent,
  SessionResult,
} from '../contracts/generated.js'
import {
  BridgeIdentityResultRules,
  FeatureReadinessResultRules,
  PreviewReadinessResultRules,
  PreviewSurfaceResultRules,
  RuntimeIdentityResultRules,
  SessionFailedEventRules,
  SessionFailurePayloadRules,
  SessionResultRules,
  SessionStateEventRules,
} from '../contracts/runtimeRules.js'
import { decodePublicError } from './errorBoundary.js'
import {
  booleanValue,
  dataRecord,
  decodeSize,
  enumValue,
  integerValue,
  invalid,
  numberValue,
  recordValue,
  stringArrayValue,
  stringValue,
  type StringCollectionRule,
  type StringEnumRule,
} from './safeData.js'

export function decodeOptionalSession(value: unknown): SessionResult | null {
  return value === null ? null : decodeSession(value)
}

export function decodeSession(value: unknown): SessionResult {
  const source = recordValue(value, SessionResultRules, 'session result')
  const processState = enumValue(
    source.process_state,
    SessionResultRules.process_state,
    'process state',
  )
  const alive = booleanValue(source.alive, 'session alive')
  const exitCode = source.exit_code === null
    ? null
    : integerValue(source.exit_code, SessionResultRules.exit_code, 'exit code')
  validateProcessState(processState, alive, exitCode)

  const capabilities = decodeCapabilities(
    source.capabilities,
    SessionResultRules.capabilities,
    'session capabilities',
  )
  const bridge = decodeBridge(source.bridge)
  if (bridge.capabilities.some((capability) => !capabilities.includes(capability))) {
    invalid('bridge capability subset')
  }

  return Object.freeze({
    id: stringValue(source.id, SessionResultRules.id, 'session id'),
    run_revision: integerValue(
      source.run_revision,
      SessionResultRules.run_revision,
      'run revision',
    ),
    runtime: decodeRuntime(source.runtime),
    project_dir: stringValue(source.project_dir, SessionResultRules.project_dir, 'project path'),
    root_pid: integerValue(source.root_pid, SessionResultRules.root_pid, 'process id'),
    process_state: processState,
    alive,
    exit_code: exitCode,
    started_at: numberValue(source.started_at, SessionResultRules.started_at, 'start timestamp'),
    bridge,
    capabilities,
    preview: decodePreviewReadiness(source.preview),
    perception: decodeReadiness(source.perception, 'perception readiness'),
    control: decodeReadiness(source.control, 'control readiness'),
  })
}

export function decodeSessionEvent(value: unknown): SessionEvent {
  const candidate = dataRecord(value)
  if (!candidate) invalid('session event')
  if (candidate.type === 'session.failed') return decodeFailureEvent(value)
  const source = recordValue(value, SessionStateEventRules, 'session event')
  const sessionId = stringValue(
    source.session_id,
    SessionStateEventRules.session_id,
    'event session id',
  )
  const payload = decodeSession(source.payload)
  if (payload.id !== sessionId) invalid('session event owner')
  return Object.freeze({
    session_id: sessionId,
    sequence: integerValue(source.sequence, SessionStateEventRules.sequence, 'event sequence'),
    timestamp: numberValue(source.timestamp, SessionStateEventRules.timestamp, 'event timestamp'),
    type: enumValue(source.type, SessionStateEventRules.type, 'session event type'),
    payload,
  })
}

function decodeFailureEvent(value: unknown): SessionEvent {
  const source = recordValue(value, SessionFailedEventRules, 'failure event')
  const sessionId = stringValue(
    source.session_id,
    SessionFailedEventRules.session_id,
    'event session id',
  )
  const payload = recordValue(
    source.payload,
    SessionFailurePayloadRules,
    'failure event payload',
  )
  const session = decodeSession(payload.session)
  const error = decodePublicError(payload.error)
  if (!error || session.id !== sessionId) invalid('failure event')
  return Object.freeze({
    session_id: sessionId,
    sequence: integerValue(source.sequence, SessionFailedEventRules.sequence, 'event sequence'),
    timestamp: numberValue(source.timestamp, SessionFailedEventRules.timestamp, 'event timestamp'),
    type: enumValue(source.type, SessionFailedEventRules.type, 'session event type'),
    payload: Object.freeze({ session, error }),
  })
}

function decodeRuntime(value: unknown): SessionResult['runtime'] {
  const source = recordValue(value, RuntimeIdentityResultRules, 'runtime identity')
  return Object.freeze({
    engine: stringValue(source.engine, RuntimeIdentityResultRules.engine, 'runtime engine'),
    version: stringValue(source.version, RuntimeIdentityResultRules.version, 'runtime version'),
    build_id: stringValue(source.build_id, RuntimeIdentityResultRules.build_id, 'runtime build'),
    distribution_id: stringValue(
      source.distribution_id,
      RuntimeIdentityResultRules.distribution_id,
      'runtime distribution',
    ),
    platform: stringValue(
      source.platform,
      RuntimeIdentityResultRules.platform,
      'runtime platform',
    ),
    architecture: stringValue(
      source.architecture,
      RuntimeIdentityResultRules.architecture,
      'runtime architecture',
    ),
  })
}

function decodeBridge(value: unknown): SessionResult['bridge'] {
  const source = recordValue(value, BridgeIdentityResultRules, 'bridge identity')
  return Object.freeze({
    id: stringValue(source.id, BridgeIdentityResultRules.id, 'bridge id'),
    protocol: stringValue(source.protocol, BridgeIdentityResultRules.protocol, 'bridge protocol'),
    capabilities: decodeCapabilities(
      source.capabilities,
      BridgeIdentityResultRules.capabilities,
      'bridge capabilities',
    ),
  })
}

function decodeCapabilities(
  value: unknown,
  rule: StringCollectionRule,
  name: string,
): readonly string[] {
  const result = stringArrayValue(value, rule, name)
  if (new Set(result).size !== result.length || !isSorted(result)) invalid(name)
  return result
}

function decodePreviewReadiness(value: unknown): PreviewReadinessResult {
  const source = recordValue(value, PreviewReadinessResultRules, 'preview readiness')
  const base = decodeReadinessSource(
    source,
    PreviewReadinessResultRules.state,
    'preview readiness',
  )
  const surfaceValue = Object.hasOwn(source, 'surface') ? source.surface : null
  const surface = surfaceValue === null ? null : decodePreviewSurface(surfaceValue)
  if ((base.state === 'ready') !== (surface !== null)) invalid('preview readiness surface')
  return Object.freeze({ ...base, surface })
}

function decodeReadiness(value: unknown, name: string): FeatureReadinessResult {
  const source = recordValue(value, FeatureReadinessResultRules, name)
  return Object.freeze(decodeReadinessSource(source, FeatureReadinessResultRules.state, name))
}

function decodeReadinessSource(
  source: Readonly<Record<string, unknown>>,
  stateRule: StringEnumRule<FeatureReadinessResult['state']>,
  name: string,
): FeatureReadinessResult {
  const state = enumValue(source.state, stateRule, `${name} state`)
  const errorValue = Object.hasOwn(source, 'error') ? source.error : null
  const error = errorValue === null ? null : decodePublicError(errorValue)
  if (errorValue !== null && error === null) invalid(`${name} error`)
  if ((state === 'failed') !== (error !== null)) invalid(`${name} error`)
  return { state, error }
}

function decodePreviewSurface(value: unknown): PreviewSurfaceResult {
  const source = recordValue(value, PreviewSurfaceResultRules, 'preview surface')
  return Object.freeze({
    kind: enumValue(source.kind, PreviewSurfaceResultRules.kind, 'preview surface kind'),
    viewport_size: decodeSize(source.viewport_size),
  })
}

function validateProcessState(
  state: SessionResult['process_state'],
  alive: boolean,
  exitCode: number | null,
): void {
  if (state === 'running' || state === 'paused') {
    if (!alive || exitCode !== null) invalid('live process state')
    return
  }
  if (state === 'ended' || state === 'crashed') {
    if (alive || exitCode === null) invalid('terminal process state')
    return
  }
  if (alive !== (exitCode === null)) invalid('stopping process state')
}

function isSorted(values: readonly string[]): boolean {
  for (let index = 1; index < values.length; index += 1) {
    const previous = values[index - 1]
    const current = values[index]
    if (previous === undefined || current === undefined || previous > current) return false
  }
  return true
}
