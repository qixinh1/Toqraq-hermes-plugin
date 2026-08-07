/** English user-facing renderer strings. */

import type { PluginMessages } from '@hermes/plugin-sdk'
import { interpolated } from '../interpolation.js'

export const en = {
  toolbar: {
    runtimeControls: 'Game runtime controls',
    runtimeIdentity: interpolated(
      ['engine', 'version'],
      (engine, version) => `${engine} ${version}`,
    ),
    processState: interpolated(['state'], (state) => `State: ${state}`),
    stopTitle: 'Stop the game',
    finishStopTitle: 'Finish stopping and clean up',
    pauseTitle: 'Pause simulation',
    resumeTitle: 'Resume simulation',
  },
  pane: {
    title: 'Toqraq',
    previewLabel: 'Game preview',
    nativeConnecting: 'Connecting the native game window…',
    nativeActive: 'Native game window attached',
    previewFailed: 'The game preview failed; stop and start the game to retry',
    nativeRetrying: 'Native game window connection failed; retrying automatically…',
    previewUnavailable: 'This game preview cannot be shown in the pane',
  },
  setup: {
    headline: {
      checking: 'Checking setup…',
      workspaceMissing: 'Open a game workspace in Hermes',
      session: 'Start a Hermes conversation',
      sessionUnavailable: 'Hermes conversation unavailable',
      setupUnavailable: 'Toqraq setup check unavailable',
      engineUnavailable: 'No game project format is available',
      runtimeUnavailable: 'This project has no available engine runtime',
      engineChoice: 'Choose the detected game engine',
      versionChoice: 'Choose an exact engine version',
      host: 'This host cannot present the game preview',
      hostUnavailable: 'Native display is unavailable',
      projectInvalid: 'This is not a valid game project',
      projectMissing: 'Choose a game project',
      install: 'Install the required engine',
      ready: 'Ready to start',
    },
    description: {
      checking: 'Reading project, host, and managed component state',
      workspaceMissing: 'Choose or open a game project from Hermes Projects to continue',
      session: 'The game belongs to the active Hermes conversation',
      sessionUnavailable: 'Resolve the Hermes error, then send a message to start a conversation',
      setupUnavailable: 'Hermes backend did not answer after bounded retries',
      engineUnavailable:
        'This Toqraq build cannot recognize a game-engine project format',
      runtimeUnavailable:
        'The project format was recognized, but this Toqraq build offers no certified runtime for it',
      engineChoice: 'Several supported project formats matched this workspace',
      versionChoice: 'Several certified versions match; select one for this workspace',
      host: 'The selected preview mode is not supported on this host',
      hostUnavailable:
        'Open Hermes Plugins, repair or reinstall Toqraq, then restart Hermes Desktop',
      projectInvalid: 'Open a supported engine project as the active Hermes workspace',
      projectMissing: 'Open a game project as the active Hermes workspace',
      install: 'Review the exact managed release below before starting its preparation',
      ready: 'Press Start to launch the selected managed engine',
    },
    item: {
      session: 'Conversation',
      host: 'Display',
      project: 'Project',
      engine: 'Engine',
      runtime: 'Engine runtime',
    },
    state: {
      session: { checking: 'checking', ready: 'ready', needed: 'needed', unavailable: 'not running' },
      host: {
        checking: 'checking',
        ready: 'ready',
        unavailable: 'setup failed',
        unsupported: 'unsupported',
      },
      project: {
        checking: 'checking',
        unchecked: 'not inspected',
        missing: 'not selected',
        invalid: 'invalid',
        not_detected: 'not detected',
        ambiguous: 'choice required',
        ready: 'ready',
      },
      runtime: {
        checking: 'checking',
        unavailable: 'unavailable',
        choice: 'choice required',
        required: 'installation required',
        ready: 'ready',
      },
    },
    action: {
      start: 'Start game',
      starting: 'Starting…',
      retry: 'Retry setup check',
      retrying: 'Retrying…',
    },
  },
  component: {
    heading: 'Managed runtime components',
    headingRequired: 'Required managed releases',
    headingReady: 'Managed releases',
    loading: 'Reading certified component releases…',
    planUnavailable:
      'The exact certified component plan is unavailable. Update or reinstall Toqraq and retry.',
    packageLink: 'Package source',
    requiredMarker: 'license acceptance required',
    authenticationRequired: 'Vendor authentication required',
    authenticationNotRequired: 'No authentication required',
    removeBlocked: 'Stop the running game before removing this component.',
    progressLabel: 'Component operation progress',
    sizeValue: interpolated(
      ['packageBytes', 'installedBytes'],
      (packageBytes, installedBytes) =>
        `Download ${packageBytes} bytes; installed ${installedBytes} bytes`,
    ),
    progressValue: interpolated(
      ['completedBytes', 'totalBytes'],
      (completedBytes, totalBytes) => `${completedBytes} / ${totalBytes} bytes`,
    ),
    statePhase: interpolated(['state', 'phase'], (state, phase) => `${state} / ${phase}`),
    detail: {
      target: 'Target',
      size: 'Size',
      source: 'Source',
      license: 'License',
      authentication: 'Account',
    },
    readiness: {
      missing: 'not installed',
      invalid: 'repair required',
      ready: 'ready',
    },
    state: {
      queued: 'queued',
      running: 'running',
      cancelling: 'cancelling',
      ready: 'complete',
      failed: 'failed',
      cancelled: 'cancelled',
    },
    phase: {
      checking: 'checking',
      downloading: 'downloading',
      installing: 'installing',
      verifying: 'verifying',
      removing: 'removing',
      ready: 'ready',
    },
    action: {
      prepare: 'Install component',
      repair: 'Repair component',
      acceptAndPrepare: 'Accept license and install',
      acceptAndRepair: 'Accept license and repair',
      remove: 'Remove',
      cancel: 'Cancel',
      retry: 'Retry',
      refreshing: 'Refreshing…',
    },
  },
  notify: {
    needSession: 'Resolve the Hermes error and start a working conversation first',
    needProject: 'Open a game workspace in Hermes first',
    componentRequired: 'Install the required managed engine before starting the game',
    startFailed: 'Failed to start the game',
    stopFailed: 'Failed to stop the game',
    pauseFailed: 'Pause failed',
    displayFailed: 'Game display connection failed',
    loadFailed: 'Failed to load this session’s game',
    projectInvalid: 'Open a valid supported game project in Hermes',
    unsupportedHost: 'The selected game preview is unavailable on this host',
    displayUnavailable:
      'Open Hermes Plugins, repair or reinstall Toqraq, then restart Hermes Desktop',
    sessionEnded: 'Game session ended',
    sessionCrashed: interpolated(
      ['exitCode'],
      (exitCode) => `Game crashed (exit code ${exitCode})`,
    ),
  },
  errors: {
    platform: {
      unsupported: 'This feature is unavailable on this operating system.',
      operation_failed: 'The operating system could not update the game preview. Retry the action.',
    },
    engine: {
      not_found: 'The selected game engine is unavailable. Choose an offered engine.',
      choice_required: 'Several engine project formats matched. Choose the intended engine.',
      unavailable:
        'This Toqraq build currently offers no certified game engine. Update Toqraq when a supported engine release is available.',
    },
    runtime: {
      release_not_found:
        'The selected engine build is not certified by this Toqraq version. Choose an offered version.',
      version_choice_required:
        'Several certified engine versions are available. Choose the version for this workspace.',
      not_installed: 'The managed engine is not installed. Install it in Toqraq and retry.',
      launch_failed: 'The engine could not start the game. Review diagnostics and retry.',
      termination_failed: 'The game process could not be stopped. Retry before ending the session.',
    },
    component: {
      release_invalid:
        'This plugin contains an invalid component record. Update or reinstall Toqraq and retry.',
      release_not_found:
        'The selected component version is not offered by this Toqraq build. Choose an available version.',
      job_not_found:
        'This component operation is no longer available. Refresh the component list and retry.',
      operation_conflict:
        'Another operation is already changing this component. Wait for it to finish or cancel it.',
      job_limit:
        'Too many component operations are active. Wait for one to finish and retry.',
      storage_unavailable:
        'Managed component storage is unavailable or has insufficient space. Free space and retry.',
      download_failed:
        'The component package could not be downloaded and verified. Check the network and retry.',
      install_failed:
        'The verified package could not be installed safely. Retry or update Toqraq.',
      publication_failed:
        'The verified component could not be made ready in managed storage. Retry the operation.',
      operation_timeout:
        'The component operation did not obtain or release ownership before its deadline. Retry shortly.',
      operation_failed:
        'Toqraq could not complete the local component operation. Retry and use the trace ID for support.',
      in_use:
        'This component is being used by a running game. Stop the owning game before removing it.',
    },
    project: {
      invalid: 'The selected directory is not a valid game project. Check the project and retry.',
    },
    session: {
      not_found: 'This Hermes session does not own a running game.',
      invalid_state: 'The game is not in a state that permits this action.',
      cleanup_failed: 'Some game resources could not be released. Retry before ending the session.',
    },
    perception: {
      capability_unavailable: 'The running engine does not provide this game-development capability.',
      stale: 'This game observation is no longer current. Read the latest state and retry.',
      object_not_found: 'The selected runtime object is no longer available. Read the hierarchy again.',
      frame_unavailable: 'The running game cannot provide a frame in its current state. Retry after it is ready.',
    },
    simulation: {
      invalid_state: 'The simulation is not in a state that permits this control operation.',
    },
    input: {
      rejected: 'The running game rejected this input for its current state. Refresh the game state and retry.',
    },
    preview: {
      attach_failed: 'The game preview could not be attached. Retry the preview connection.',
      host_window_not_found: 'The Hermes window for this preview could not be found.',
      game_window_not_found: 'The game did not create a preview window before the deadline.',
    },
    bridge: {
      unavailable: 'The game connection is unavailable. Keep the game running and retry.',
      protocol_invalid: 'The game or request returned data that Toqraq could not safely use.',
    },
    request: {
      invalid: 'Some request fields are invalid. Check the values and retry.',
      cancelled: 'The operation was cancelled.',
    },
    internal: {
      unexpected: 'Toqraq encountered an unexpected failure. Retry and use the trace ID for support.',
    },
  },
  failure: {
    transportUnavailable: 'Hermes could not reach the Toqraq backend. Check the plugin and retry.',
    withTraceId: interpolated(
      ['message', 'traceId'],
      (message, traceId) => `${message} Trace ID: ${traceId}`,
    ),
  },
  status: {
    idle: 'idle',
    running: 'running',
    paused: 'paused',
    stopping: 'stopping',
    crashed: 'crashed',
    unavailable: 'unavailable',
    title: 'Toqraq game engine bridge',
    value: interpolated(['state'], (state) => `Toqraq: ${state}`),
  },
  palette: { stop: 'Toqraq: Stop Game' },
} satisfies PluginMessages
