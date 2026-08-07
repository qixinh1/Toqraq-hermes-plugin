/** Derive the small set of first-run states rendered by the pane. */

import type {
  EngineSetupResult,
  HostSetupResult,
  ProjectSetupResult,
  ProjectState,
  SetupAction,
} from '../contracts/generated.js'

export type SessionSetupStatus = 'checking' | 'ready' | 'needed' | 'unavailable'
export type SetupHeadline =
  | 'workspaceMissing'
  | 'session'
  | 'sessionUnavailable'
  | 'setupUnavailable'
  | 'checking'
  | 'ready'
  | 'engineUnavailable'
  | 'runtimeUnavailable'
  | 'engineChoice'
  | 'versionChoice'
  | 'host'
  | 'hostUnavailable'
  | 'projectInvalid'
  | 'projectMissing'
  | 'install'

export interface SetupViewSetup {
  action: SetupAction
  host: Pick<HostSetupResult, 'platform' | 'native_display'>
  project: Pick<ProjectSetupResult, 'state'>
  engine: Pick<EngineSetupResult, 'runtime' | 'runtime_install_required'> | null
}

export interface SetupViewInput {
  setup: SetupViewSetup | null
  sessionStatus: SessionSetupStatus
  workspacePresent: boolean
  checking: boolean
  failed?: boolean
}

export interface SetupView {
  headline: SetupHeadline
  showReadiness: boolean
  showComponentPlan: boolean
  retryable: boolean
  startable: boolean
  session: SessionSetupStatus
  host: 'checking' | 'ready' | 'unavailable' | 'unsupported'
  project: 'checking' | 'missing' | ProjectState
  runtime: 'checking' | 'unavailable' | 'choice' | 'required' | 'ready'
}

/** Decide whether the pane has one valid setup request target. */
export function shouldCheckSetup(workspaceDir: string, sessionOwned: boolean): boolean {
  return workspaceDir.length > 0 && !sessionOwned
}

export function deriveSetupView({
  setup,
  sessionStatus,
  workspacePresent,
  checking,
  failed = false,
}: SetupViewInput): SetupView {
  if (!workspacePresent) {
    return {
      headline: 'workspaceMissing',
      showReadiness: false,
      showComponentPlan: false,
      retryable: false,
      startable: false,
      session: sessionStatus,
      host: 'checking',
      project: 'missing',
      runtime: 'checking',
    }
  }
  if (failed) {
    const headline: SetupHeadline =
      sessionStatus === 'needed'
        ? 'session'
        : sessionStatus === 'unavailable'
          ? 'sessionUnavailable'
          : 'setupUnavailable'
    return {
      headline,
      showReadiness: true,
      showComponentPlan: false,
      retryable: headline === 'setupUnavailable',
      startable: false,
      session: sessionStatus,
      host: 'checking',
      project: 'checking',
      runtime: 'checking',
    }
  }
  if (checking || !setup) {
    return {
      headline:
        sessionStatus === 'needed'
          ? 'session'
          : sessionStatus === 'unavailable'
            ? 'sessionUnavailable'
            : 'checking',
      showReadiness: true,
      showComponentPlan: false,
      retryable: false,
      startable: false,
      session: sessionStatus,
      host: 'checking',
      project: 'checking',
      runtime: 'checking',
    }
  }
  const project = setup.project.state
  const host: SetupView['host'] = setup.action !== 'unsupported_host'
    ? 'ready'
    : setup.host.platform === 'windows' && !setup.host.native_display
      ? 'unavailable'
      : 'unsupported'
  const runtime: SetupView['runtime'] = setup.engine === null
    ? 'unavailable'
    : setup.action === 'select_version'
      ? 'choice'
      : setup.engine.runtime_install_required
        ? 'required'
        : setup.engine.runtime === null
          ? 'unavailable'
          : 'ready'
  let headline: SetupHeadline = 'ready'
  if (setup.action === 'engine_unavailable') headline = 'engineUnavailable'
  else if (setup.action === 'runtime_unavailable') headline = 'runtimeUnavailable'
  else if (sessionStatus === 'needed') headline = 'session'
  else if (sessionStatus === 'unavailable') headline = 'sessionUnavailable'
  else if (sessionStatus === 'checking') headline = 'checking'
  else if (setup.action === 'select_engine') headline = 'engineChoice'
  else if (setup.action === 'select_version') headline = 'versionChoice'
  else if (host === 'unsupported') headline = 'host'
  else if (host === 'unavailable') headline = 'hostUnavailable'
  else if (project === 'invalid' || project === 'not_detected') headline = 'projectInvalid'
  else if (project !== 'ready') headline = 'projectMissing'
  else if (setup.action === 'install') headline = 'install'
  return {
    headline,
    showReadiness: true,
    showComponentPlan: setup.action === 'install' || setup.action === 'start',
    retryable: false,
    startable: sessionStatus === 'ready' && setup.action === 'start',
    session: sessionStatus,
    host,
    project,
    runtime,
  }
}
