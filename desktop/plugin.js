// src/renderer/i18n/interpolation.ts
function interpolated(parameters, render) {
  Object.defineProperty(render, "i18nParameters", { value: Object.freeze([...parameters]) });
  return render;
}

// src/renderer/i18n/locales/en.ts
var en = {
  toolbar: {
    runtimeControls: "Game runtime controls",
    runtimeIdentity: interpolated(
      ["engine", "version"],
      (engine, version) => `${engine} ${version}`
    ),
    processState: interpolated(["state"], (state) => `State: ${state}`),
    stopTitle: "Stop the game",
    finishStopTitle: "Finish stopping and clean up",
    pauseTitle: "Pause simulation",
    resumeTitle: "Resume simulation"
  },
  pane: {
    title: "Toqraq",
    previewLabel: "Game preview",
    nativeConnecting: "Connecting the native game window\u2026",
    nativeActive: "Native game window attached",
    previewFailed: "The game preview failed; stop and start the game to retry",
    nativeRetrying: "Native game window connection failed; retrying automatically\u2026",
    previewUnavailable: "This game preview cannot be shown in the pane"
  },
  setup: {
    headline: {
      checking: "Checking setup\u2026",
      workspaceMissing: "Open a game workspace in Hermes",
      session: "Start a Hermes conversation",
      sessionUnavailable: "Hermes conversation unavailable",
      setupUnavailable: "Toqraq setup check unavailable",
      engineUnavailable: "No game project format is available",
      runtimeUnavailable: "This project has no available engine runtime",
      engineChoice: "Choose the detected game engine",
      versionChoice: "Choose an exact engine version",
      host: "This host cannot present the game preview",
      hostUnavailable: "Native display is unavailable",
      projectInvalid: "This is not a valid game project",
      projectMissing: "Choose a game project",
      install: "Install the required engine",
      ready: "Ready to start"
    },
    description: {
      checking: "Reading project, host, and managed component state",
      workspaceMissing: "Choose or open a game project from Hermes Projects to continue",
      session: "The game belongs to the active Hermes conversation",
      sessionUnavailable: "Resolve the Hermes error, then send a message to start a conversation",
      setupUnavailable: "Hermes backend did not answer after bounded retries",
      engineUnavailable: "This Toqraq build cannot recognize a game-engine project format",
      runtimeUnavailable: "The project format was recognized, but this Toqraq build offers no certified runtime for it",
      engineChoice: "Several supported project formats matched this workspace",
      versionChoice: "Several certified versions match; select one for this workspace",
      host: "The selected preview mode is not supported on this host",
      hostUnavailable: "Open Hermes Plugins, repair or reinstall Toqraq, then restart Hermes Desktop",
      projectInvalid: "Open a supported engine project as the active Hermes workspace",
      projectMissing: "Open a game project as the active Hermes workspace",
      install: "Review the exact managed release below before starting its preparation",
      ready: "Press Start to launch the selected managed engine"
    },
    item: {
      session: "Conversation",
      host: "Display",
      project: "Project",
      engine: "Engine",
      runtime: "Engine runtime"
    },
    state: {
      session: { checking: "checking", ready: "ready", needed: "needed", unavailable: "not running" },
      host: {
        checking: "checking",
        ready: "ready",
        unavailable: "setup failed",
        unsupported: "unsupported"
      },
      project: {
        checking: "checking",
        unchecked: "not inspected",
        missing: "not selected",
        invalid: "invalid",
        not_detected: "not detected",
        ambiguous: "choice required",
        ready: "ready"
      },
      runtime: {
        checking: "checking",
        unavailable: "unavailable",
        choice: "choice required",
        required: "installation required",
        ready: "ready"
      }
    },
    action: {
      start: "Start game",
      starting: "Starting\u2026",
      retry: "Retry setup check",
      retrying: "Retrying\u2026"
    }
  },
  component: {
    heading: "Managed runtime components",
    headingRequired: "Required managed releases",
    headingReady: "Managed releases",
    loading: "Reading certified component releases\u2026",
    planUnavailable: "The exact certified component plan is unavailable. Update or reinstall Toqraq and retry.",
    packageLink: "Package source",
    requiredMarker: "license acceptance required",
    authenticationRequired: "Vendor authentication required",
    authenticationNotRequired: "No authentication required",
    removeBlocked: "Stop the running game before removing this component.",
    progressLabel: "Component operation progress",
    sizeValue: interpolated(
      ["packageBytes", "installedBytes"],
      (packageBytes, installedBytes) => `Download ${packageBytes} bytes; installed ${installedBytes} bytes`
    ),
    progressValue: interpolated(
      ["completedBytes", "totalBytes"],
      (completedBytes, totalBytes) => `${completedBytes} / ${totalBytes} bytes`
    ),
    statePhase: interpolated(["state", "phase"], (state, phase) => `${state} / ${phase}`),
    detail: {
      target: "Target",
      size: "Size",
      source: "Source",
      license: "License",
      authentication: "Account"
    },
    readiness: {
      missing: "not installed",
      invalid: "repair required",
      ready: "ready"
    },
    state: {
      queued: "queued",
      running: "running",
      cancelling: "cancelling",
      ready: "complete",
      failed: "failed",
      cancelled: "cancelled"
    },
    phase: {
      checking: "checking",
      downloading: "downloading",
      installing: "installing",
      verifying: "verifying",
      removing: "removing",
      ready: "ready"
    },
    action: {
      prepare: "Install component",
      repair: "Repair component",
      acceptAndPrepare: "Accept license and install",
      acceptAndRepair: "Accept license and repair",
      remove: "Remove",
      cancel: "Cancel",
      retry: "Retry",
      refreshing: "Refreshing\u2026"
    }
  },
  notify: {
    needSession: "Resolve the Hermes error and start a working conversation first",
    needProject: "Open a game workspace in Hermes first",
    componentRequired: "Install the required managed engine before starting the game",
    startFailed: "Failed to start the game",
    stopFailed: "Failed to stop the game",
    pauseFailed: "Pause failed",
    displayFailed: "Game display connection failed",
    loadFailed: "Failed to load this session\u2019s game",
    projectInvalid: "Open a valid supported game project in Hermes",
    unsupportedHost: "The selected game preview is unavailable on this host",
    displayUnavailable: "Open Hermes Plugins, repair or reinstall Toqraq, then restart Hermes Desktop",
    sessionEnded: "Game session ended",
    sessionCrashed: interpolated(
      ["exitCode"],
      (exitCode) => `Game crashed (exit code ${exitCode})`
    )
  },
  errors: {
    platform: {
      unsupported: "This feature is unavailable on this operating system.",
      operation_failed: "The operating system could not update the game preview. Retry the action."
    },
    engine: {
      not_found: "The selected game engine is unavailable. Choose an offered engine.",
      choice_required: "Several engine project formats matched. Choose the intended engine.",
      unavailable: "This Toqraq build currently offers no certified game engine. Update Toqraq when a supported engine release is available."
    },
    runtime: {
      release_not_found: "The selected engine build is not certified by this Toqraq version. Choose an offered version.",
      version_choice_required: "Several certified engine versions are available. Choose the version for this workspace.",
      not_installed: "The managed engine is not installed. Install it in Toqraq and retry.",
      launch_failed: "The engine could not start the game. Review diagnostics and retry.",
      termination_failed: "The game process could not be stopped. Retry before ending the session."
    },
    component: {
      release_invalid: "This plugin contains an invalid component record. Update or reinstall Toqraq and retry.",
      release_not_found: "The selected component version is not offered by this Toqraq build. Choose an available version.",
      job_not_found: "This component operation is no longer available. Refresh the component list and retry.",
      operation_conflict: "Another operation is already changing this component. Wait for it to finish or cancel it.",
      job_limit: "Too many component operations are active. Wait for one to finish and retry.",
      storage_unavailable: "Managed component storage is unavailable or has insufficient space. Free space and retry.",
      download_failed: "The component package could not be downloaded and verified. Check the network and retry.",
      install_failed: "The verified package could not be installed safely. Retry or update Toqraq.",
      publication_failed: "The verified component could not be made ready in managed storage. Retry the operation.",
      operation_timeout: "The component operation did not obtain or release ownership before its deadline. Retry shortly.",
      operation_failed: "Toqraq could not complete the local component operation. Retry and use the trace ID for support.",
      in_use: "This component is being used by a running game. Stop the owning game before removing it."
    },
    project: {
      invalid: "The selected directory is not a valid game project. Check the project and retry."
    },
    session: {
      not_found: "This Hermes session does not own a running game.",
      invalid_state: "The game is not in a state that permits this action.",
      cleanup_failed: "Some game resources could not be released. Retry before ending the session."
    },
    perception: {
      capability_unavailable: "The running engine does not provide this game-development capability.",
      stale: "This game observation is no longer current. Read the latest state and retry.",
      object_not_found: "The selected runtime object is no longer available. Read the hierarchy again.",
      frame_unavailable: "The running game cannot provide a frame in its current state. Retry after it is ready."
    },
    simulation: {
      invalid_state: "The simulation is not in a state that permits this control operation."
    },
    input: {
      rejected: "The running game rejected this input for its current state. Refresh the game state and retry."
    },
    preview: {
      attach_failed: "The game preview could not be attached. Retry the preview connection.",
      host_window_not_found: "The Hermes window for this preview could not be found.",
      game_window_not_found: "The game did not create a preview window before the deadline."
    },
    bridge: {
      unavailable: "The game connection is unavailable. Keep the game running and retry.",
      protocol_invalid: "The game or request returned data that Toqraq could not safely use."
    },
    request: {
      invalid: "Some request fields are invalid. Check the values and retry.",
      cancelled: "The operation was cancelled."
    },
    internal: {
      unexpected: "Toqraq encountered an unexpected failure. Retry and use the trace ID for support."
    }
  },
  failure: {
    transportUnavailable: "Hermes could not reach the Toqraq backend. Check the plugin and retry.",
    withTraceId: interpolated(
      ["message", "traceId"],
      (message, traceId) => `${message} Trace ID: ${traceId}`
    )
  },
  status: {
    idle: "idle",
    running: "running",
    paused: "paused",
    stopping: "stopping",
    crashed: "crashed",
    unavailable: "unavailable",
    title: "Toqraq game engine bridge",
    value: interpolated(["state"], (state) => `Toqraq: ${state}`)
  },
  palette: { stop: "Toqraq: Stop Game" }
};

// src/renderer/i18n/locales/zh.ts
var zh = {
  toolbar: {
    runtimeControls: "\u6E38\u620F\u8FD0\u884C\u63A7\u5236",
    runtimeIdentity: interpolated(
      ["engine", "version"],
      (engine, version) => `${engine} ${version}`
    ),
    processState: interpolated(["state"], (state) => `\u72B6\u6001\uFF1A${state}`),
    stopTitle: "\u505C\u6B62\u6E38\u620F",
    finishStopTitle: "\u5B8C\u6210\u505C\u6B62\u4E0E\u6E05\u7406",
    pauseTitle: "\u6682\u505C\u6A21\u62DF",
    resumeTitle: "\u7EE7\u7EED\u6A21\u62DF"
  },
  pane: {
    title: "Toqraq",
    previewLabel: "\u6E38\u620F\u9884\u89C8",
    nativeConnecting: "\u6B63\u5728\u8FDE\u63A5\u539F\u751F\u6E38\u620F\u7A97\u53E3\u2026",
    nativeActive: "\u539F\u751F\u6E38\u620F\u7A97\u53E3\u5DF2\u9644\u7740",
    previewFailed: "\u6E38\u620F\u9884\u89C8\u5DF2\u5931\u8D25\uFF0C\u8BF7\u505C\u6B62\u5E76\u91CD\u65B0\u542F\u52A8\u6E38\u620F\u540E\u91CD\u8BD5",
    nativeRetrying: "\u539F\u751F\u6E38\u620F\u7A97\u53E3\u8FDE\u63A5\u5931\u8D25\uFF0C\u6B63\u5728\u81EA\u52A8\u91CD\u8BD5\u2026",
    previewUnavailable: "\u5F53\u524D\u6E38\u620F\u9884\u89C8\u65E0\u6CD5\u5728\u9762\u677F\u4E2D\u663E\u793A"
  },
  setup: {
    headline: {
      checking: "\u6B63\u5728\u68C0\u67E5\u73AF\u5883\u2026",
      workspaceMissing: "\u8BF7\u5728 Hermes \u4E2D\u6253\u5F00\u6E38\u620F\u5DE5\u4F5C\u533A",
      session: "\u8BF7\u5148\u5F00\u59CB\u4E00\u4E2A Hermes \u4F1A\u8BDD",
      sessionUnavailable: "Hermes \u4F1A\u8BDD\u4E0D\u53EF\u7528",
      setupUnavailable: "Toqraq \u73AF\u5883\u68C0\u67E5\u4E0D\u53EF\u7528",
      engineUnavailable: "\u6CA1\u6709\u53EF\u8BC6\u522B\u7684\u6E38\u620F\u9879\u76EE\u683C\u5F0F",
      runtimeUnavailable: "\u6B64\u9879\u76EE\u6CA1\u6709\u53EF\u7528\u7684\u5F15\u64CE\u8FD0\u884C\u65F6",
      engineChoice: "\u8BF7\u9009\u62E9\u68C0\u6D4B\u5230\u7684\u6E38\u620F\u5F15\u64CE",
      versionChoice: "\u8BF7\u9009\u62E9\u51C6\u786E\u7684\u5F15\u64CE\u7248\u672C",
      host: "\u5F53\u524D\u4E3B\u673A\u65E0\u6CD5\u663E\u793A\u6E38\u620F\u9884\u89C8",
      hostUnavailable: "\u539F\u751F\u753B\u9762\u4E0D\u53EF\u7528",
      projectInvalid: "\u8FD9\u4E0D\u662F\u6709\u6548\u7684\u6E38\u620F\u9879\u76EE",
      projectMissing: "\u8BF7\u9009\u62E9\u6E38\u620F\u9879\u76EE",
      install: "\u5B89\u88C5\u6240\u9700\u5F15\u64CE",
      ready: "\u53EF\u4EE5\u542F\u52A8"
    },
    description: {
      checking: "\u6B63\u5728\u8BFB\u53D6\u9879\u76EE\u3001\u4E3B\u673A\u548C\u6258\u7BA1\u7EC4\u4EF6\u72B6\u6001",
      workspaceMissing: "\u8BF7\u4ECE Hermes \u9879\u76EE\u5217\u8868\u4E2D\u9009\u62E9\u6216\u6253\u5F00\u6E38\u620F\u9879\u76EE\u540E\u7EE7\u7EED",
      session: "\u6E38\u620F\u5C06\u5F52\u5C5E\u4E8E\u5F53\u524D Hermes \u4F1A\u8BDD",
      sessionUnavailable: "\u8BF7\u5148\u89E3\u51B3 Hermes \u9519\u8BEF\uFF0C\u518D\u53D1\u9001\u6D88\u606F\u542F\u52A8\u4F1A\u8BDD",
      setupUnavailable: "Hermes \u540E\u7AEF\u5728\u6709\u9650\u6B21\u6570\u7684\u91CD\u8BD5\u540E\u4ECD\u672A\u54CD\u5E94",
      engineUnavailable: "\u5F53\u524D Toqraq \u7248\u672C\u65E0\u6CD5\u8BC6\u522B\u4EFB\u4F55\u6E38\u620F\u5F15\u64CE\u9879\u76EE\u683C\u5F0F",
      runtimeUnavailable: "\u5DF2\u8BC6\u522B\u9879\u76EE\u683C\u5F0F\uFF0C\u4F46\u5F53\u524D Toqraq \u7248\u672C\u5C1A\u672A\u63D0\u4F9B\u5BF9\u5E94\u7684\u5DF2\u8BA4\u8BC1\u8FD0\u884C\u65F6",
      engineChoice: "\u5F53\u524D\u5DE5\u4F5C\u533A\u5339\u914D\u4E86\u591A\u79CD\u53D7\u652F\u6301\u7684\u9879\u76EE\u683C\u5F0F",
      versionChoice: "\u6709\u591A\u4E2A\u5DF2\u8BA4\u8BC1\u7248\u672C\u53EF\u7528\uFF0C\u8BF7\u4E3A\u5F53\u524D\u5DE5\u4F5C\u533A\u9009\u62E9\u4E00\u4E2A\u7248\u672C",
      host: "\u5F53\u524D\u4E3B\u673A\u4E0D\u652F\u6301\u6240\u9009\u7684\u6E38\u620F\u9884\u89C8\u65B9\u5F0F",
      hostUnavailable: "\u8BF7\u5728 Hermes \u63D2\u4EF6\u7BA1\u7406\u4E2D\u4FEE\u590D\u6216\u91CD\u65B0\u5B89\u88C5 Toqraq\uFF0C\u7136\u540E\u91CD\u542F Hermes Desktop",
      projectInvalid: "\u8BF7\u5C06\u53D7\u652F\u6301\u7684\u5F15\u64CE\u9879\u76EE\u4F5C\u4E3A\u5F53\u524D Hermes \u5DE5\u4F5C\u533A\u6253\u5F00",
      projectMissing: "\u8BF7\u5C06\u6E38\u620F\u9879\u76EE\u4F5C\u4E3A\u5F53\u524D Hermes \u5DE5\u4F5C\u533A\u6253\u5F00",
      install: "\u5F00\u59CB\u51C6\u5907\u524D\uFF0C\u8BF7\u5148\u68C0\u67E5\u4E0B\u65B9\u7CBE\u786E\u7684\u6258\u7BA1\u7248\u672C\u4FE1\u606F",
      ready: "\u70B9\u51FB\u542F\u52A8\u4EE5\u8FD0\u884C\u6240\u9009\u6258\u7BA1\u5F15\u64CE"
    },
    item: {
      session: "\u4F1A\u8BDD",
      host: "\u753B\u9762",
      project: "\u9879\u76EE",
      engine: "\u5F15\u64CE",
      runtime: "\u5F15\u64CE\u8FD0\u884C\u65F6"
    },
    state: {
      session: { checking: "\u68C0\u67E5\u4E2D", ready: "\u5DF2\u5C31\u7EEA", needed: "\u5C1A\u672A\u5F00\u59CB", unavailable: "\u672A\u8FD0\u884C" },
      host: { checking: "\u68C0\u67E5\u4E2D", ready: "\u5DF2\u5C31\u7EEA", unavailable: "\u8BBE\u7F6E\u5931\u8D25", unsupported: "\u4E0D\u652F\u6301" },
      project: {
        checking: "\u68C0\u67E5\u4E2D",
        unchecked: "\u5C1A\u672A\u68C0\u67E5",
        missing: "\u5C1A\u672A\u9009\u62E9",
        invalid: "\u65E0\u6548",
        not_detected: "\u672A\u68C0\u6D4B\u5230",
        ambiguous: "\u9700\u8981\u9009\u62E9",
        ready: "\u5DF2\u5C31\u7EEA"
      },
      runtime: {
        checking: "\u68C0\u67E5\u4E2D",
        unavailable: "\u4E0D\u53EF\u7528",
        choice: "\u9700\u8981\u9009\u62E9",
        required: "\u9700\u8981\u5B89\u88C5",
        ready: "\u5DF2\u5C31\u7EEA"
      }
    },
    action: {
      start: "\u542F\u52A8\u6E38\u620F",
      starting: "\u6B63\u5728\u542F\u52A8\u2026",
      retry: "\u91CD\u8BD5\u73AF\u5883\u68C0\u67E5",
      retrying: "\u6B63\u5728\u91CD\u8BD5\u2026"
    }
  },
  component: {
    heading: "\u6258\u7BA1\u8FD0\u884C\u7EC4\u4EF6",
    headingRequired: "\u6240\u9700\u6258\u7BA1\u7248\u672C",
    headingReady: "\u6258\u7BA1\u7248\u672C",
    loading: "\u6B63\u5728\u8BFB\u53D6\u5DF2\u8BA4\u8BC1\u7684\u7EC4\u4EF6\u7248\u672C\u2026",
    planUnavailable: "\u7CBE\u786E\u8BA4\u8BC1\u7684\u7EC4\u4EF6\u8BA1\u5212\u4E0D\u53EF\u7528\uFF0C\u8BF7\u66F4\u65B0\u6216\u91CD\u65B0\u5B89\u88C5 Toqraq \u540E\u91CD\u8BD5\u3002",
    packageLink: "\u7EC4\u4EF6\u5305\u6765\u6E90",
    requiredMarker: "\u9700\u8981\u63A5\u53D7\u8BB8\u53EF",
    authenticationRequired: "\u9700\u8981\u4F9B\u5E94\u5546\u8D26\u53F7\u8BA4\u8BC1",
    authenticationNotRequired: "\u65E0\u9700\u8D26\u53F7\u8BA4\u8BC1",
    removeBlocked: "\u8BF7\u5148\u505C\u6B62\u6B63\u5728\u8FD0\u884C\u7684\u6E38\u620F\uFF0C\u518D\u79FB\u9664\u6B64\u7EC4\u4EF6\u3002",
    progressLabel: "\u7EC4\u4EF6\u64CD\u4F5C\u8FDB\u5EA6",
    sizeValue: interpolated(
      ["packageBytes", "installedBytes"],
      (packageBytes, installedBytes) => `\u4E0B\u8F7D ${packageBytes} \u5B57\u8282\uFF1B\u5B89\u88C5\u540E ${installedBytes} \u5B57\u8282`
    ),
    progressValue: interpolated(
      ["completedBytes", "totalBytes"],
      (completedBytes, totalBytes) => `${completedBytes} / ${totalBytes} \u5B57\u8282`
    ),
    statePhase: interpolated(["state", "phase"], (state, phase) => `${state} / ${phase}`),
    detail: {
      target: "\u76EE\u6807\u5E73\u53F0",
      size: "\u5927\u5C0F",
      source: "\u6765\u6E90",
      license: "\u8BB8\u53EF\u8BC1",
      authentication: "\u8D26\u53F7"
    },
    readiness: {
      missing: "\u5C1A\u672A\u5B89\u88C5",
      invalid: "\u9700\u8981\u4FEE\u590D",
      ready: "\u5DF2\u5C31\u7EEA"
    },
    state: {
      queued: "\u7B49\u5F85\u4E2D",
      running: "\u8FDB\u884C\u4E2D",
      cancelling: "\u6B63\u5728\u53D6\u6D88",
      ready: "\u5DF2\u5B8C\u6210",
      failed: "\u5931\u8D25",
      cancelled: "\u5DF2\u53D6\u6D88"
    },
    phase: {
      checking: "\u68C0\u67E5\u4E2D",
      downloading: "\u4E0B\u8F7D\u4E2D",
      installing: "\u5B89\u88C5\u4E2D",
      verifying: "\u6821\u9A8C\u4E2D",
      removing: "\u79FB\u9664\u4E2D",
      ready: "\u5DF2\u5C31\u7EEA"
    },
    action: {
      prepare: "\u5B89\u88C5\u7EC4\u4EF6",
      repair: "\u4FEE\u590D\u7EC4\u4EF6",
      acceptAndPrepare: "\u63A5\u53D7\u8BB8\u53EF\u5E76\u5B89\u88C5",
      acceptAndRepair: "\u63A5\u53D7\u8BB8\u53EF\u5E76\u4FEE\u590D",
      remove: "\u79FB\u9664",
      cancel: "\u53D6\u6D88",
      retry: "\u91CD\u8BD5",
      refreshing: "\u6B63\u5728\u5237\u65B0\u2026"
    }
  },
  notify: {
    needSession: "\u8BF7\u5148\u89E3\u51B3 Hermes \u9519\u8BEF\u5E76\u542F\u52A8\u4E00\u4E2A\u53EF\u7528\u4F1A\u8BDD",
    needProject: "\u8BF7\u5148\u5728 Hermes \u4E2D\u6253\u5F00\u6E38\u620F\u5DE5\u4F5C\u533A",
    componentRequired: "\u8BF7\u5148\u5B89\u88C5\u6240\u9700\u6258\u7BA1\u5F15\u64CE\uFF0C\u518D\u542F\u52A8\u6E38\u620F",
    startFailed: "\u542F\u52A8\u6E38\u620F\u5931\u8D25",
    stopFailed: "\u505C\u6B62\u6E38\u620F\u5931\u8D25",
    pauseFailed: "\u6682\u505C\u64CD\u4F5C\u5931\u8D25",
    displayFailed: "\u8FDE\u63A5\u6E38\u620F\u753B\u9762\u5931\u8D25",
    loadFailed: "\u8BFB\u53D6\u5F53\u524D\u4F1A\u8BDD\u7684\u6E38\u620F\u5931\u8D25",
    projectInvalid: "\u8BF7\u5728 Hermes \u4E2D\u6253\u5F00\u6709\u6548\u4E14\u53D7\u652F\u6301\u7684\u6E38\u620F\u9879\u76EE",
    unsupportedHost: "\u5F53\u524D\u4E3B\u673A\u65E0\u6CD5\u4F7F\u7528\u6240\u9009\u6E38\u620F\u9884\u89C8",
    displayUnavailable: "\u8BF7\u5728 Hermes \u63D2\u4EF6\u7BA1\u7406\u4E2D\u4FEE\u590D\u6216\u91CD\u65B0\u5B89\u88C5 Toqraq\uFF0C\u7136\u540E\u91CD\u542F Hermes Desktop",
    sessionEnded: "\u6E38\u620F\u4F1A\u8BDD\u5DF2\u7ED3\u675F",
    sessionCrashed: interpolated(["exitCode"], (exitCode) => `\u6E38\u620F\u5DF2\u5D29\u6E83\uFF08\u9000\u51FA\u7801 ${exitCode}\uFF09`)
  },
  errors: {
    platform: {
      unsupported: "\u5F53\u524D\u64CD\u4F5C\u7CFB\u7EDF\u4E0D\u652F\u6301\u6B64\u529F\u80FD\u3002",
      operation_failed: "\u64CD\u4F5C\u7CFB\u7EDF\u65E0\u6CD5\u66F4\u65B0\u6E38\u620F\u9884\u89C8\uFF0C\u8BF7\u91CD\u8BD5\u3002"
    },
    engine: {
      not_found: "\u6240\u9009\u6E38\u620F\u5F15\u64CE\u4E0D\u53EF\u7528\uFF0C\u8BF7\u9009\u62E9\u5F53\u524D\u63D0\u4F9B\u7684\u5F15\u64CE\u3002",
      choice_required: "\u68C0\u6D4B\u5230\u591A\u79CD\u6E38\u620F\u5F15\u64CE\u9879\u76EE\u683C\u5F0F\uFF0C\u8BF7\u9009\u62E9\u8981\u4F7F\u7528\u7684\u5F15\u64CE\u3002",
      unavailable: "\u5F53\u524D Toqraq \u7248\u672C\u5C1A\u672A\u63D0\u4F9B\u5DF2\u8BA4\u8BC1\u7684\u6E38\u620F\u5F15\u64CE\u3002\u8BF7\u5728\u652F\u6301\u7684\u5F15\u64CE\u7248\u672C\u53D1\u5E03\u540E\u66F4\u65B0 Toqraq\u3002"
    },
    runtime: {
      release_not_found: "\u5F53\u524D Toqraq \u7248\u672C\u672A\u8BA4\u8BC1\u6240\u9009\u5F15\u64CE\u6784\u5EFA\uFF0C\u8BF7\u9009\u62E9\u53EF\u7528\u7248\u672C\u3002",
      version_choice_required: "\u6709\u591A\u4E2A\u5DF2\u8BA4\u8BC1\u7684\u5F15\u64CE\u7248\u672C\u53EF\u7528\uFF0C\u8BF7\u4E3A\u5F53\u524D\u5DE5\u4F5C\u533A\u9009\u62E9\u4E00\u4E2A\u7248\u672C\u3002",
      not_installed: "\u6258\u7BA1\u5F15\u64CE\u5C1A\u672A\u5B89\u88C5\uFF0C\u8BF7\u5728 Toqraq \u4E2D\u5B89\u88C5\u540E\u91CD\u8BD5\u3002",
      launch_failed: "\u5F15\u64CE\u65E0\u6CD5\u542F\u52A8\u6E38\u620F\uFF0C\u8BF7\u67E5\u770B\u8BCA\u65AD\u4FE1\u606F\u540E\u91CD\u8BD5\u3002",
      termination_failed: "\u65E0\u6CD5\u505C\u6B62\u6E38\u620F\u8FDB\u7A0B\uFF0C\u8BF7\u5728\u7ED3\u675F\u4F1A\u8BDD\u524D\u91CD\u8BD5\u3002"
    },
    component: {
      release_invalid: "\u63D2\u4EF6\u4E2D\u7684\u7EC4\u4EF6\u8BB0\u5F55\u65E0\u6548\uFF0C\u8BF7\u66F4\u65B0\u6216\u91CD\u65B0\u5B89\u88C5 Toqraq \u540E\u91CD\u8BD5\u3002",
      release_not_found: "\u5F53\u524D Toqraq \u7248\u672C\u4E0D\u63D0\u4F9B\u6240\u9009\u7EC4\u4EF6\u7248\u672C\uFF0C\u8BF7\u9009\u62E9\u53EF\u7528\u7248\u672C\u3002",
      job_not_found: "\u8BE5\u7EC4\u4EF6\u64CD\u4F5C\u5DF2\u4E0D\u53EF\u7528\uFF0C\u8BF7\u5237\u65B0\u7EC4\u4EF6\u5217\u8868\u540E\u91CD\u8BD5\u3002",
      operation_conflict: "\u5DF2\u6709\u64CD\u4F5C\u6B63\u5728\u4FEE\u6539\u6B64\u7EC4\u4EF6\uFF0C\u8BF7\u7B49\u5F85\u5B8C\u6210\u6216\u5148\u53D6\u6D88\u8BE5\u64CD\u4F5C\u3002",
      job_limit: "\u5F53\u524D\u6D3B\u52A8\u7684\u7EC4\u4EF6\u64CD\u4F5C\u8FC7\u591A\uFF0C\u8BF7\u7B49\u5F85\u5176\u4E2D\u4E00\u4E2A\u5B8C\u6210\u540E\u91CD\u8BD5\u3002",
      storage_unavailable: "\u6258\u7BA1\u7EC4\u4EF6\u5B58\u50A8\u4E0D\u53EF\u7528\u6216\u7A7A\u95F4\u4E0D\u8DB3\uFF0C\u8BF7\u91CA\u653E\u7A7A\u95F4\u540E\u91CD\u8BD5\u3002",
      download_failed: "\u65E0\u6CD5\u4E0B\u8F7D\u5E76\u6821\u9A8C\u7EC4\u4EF6\u5305\uFF0C\u8BF7\u68C0\u67E5\u7F51\u7EDC\u540E\u91CD\u8BD5\u3002",
      install_failed: "\u65E0\u6CD5\u5B89\u5168\u5B89\u88C5\u5DF2\u6821\u9A8C\u7684\u7EC4\u4EF6\u5305\uFF0C\u8BF7\u91CD\u8BD5\u6216\u66F4\u65B0 Toqraq\u3002",
      publication_failed: "\u65E0\u6CD5\u5728\u6258\u7BA1\u5B58\u50A8\u4E2D\u542F\u7528\u5DF2\u6821\u9A8C\u7EC4\u4EF6\uFF0C\u8BF7\u91CD\u8BD5\u3002",
      operation_timeout: "\u7EC4\u4EF6\u64CD\u4F5C\u672A\u80FD\u5728\u65F6\u9650\u5185\u53D6\u5F97\u6216\u91CA\u653E\u6240\u6709\u6743\uFF0C\u8BF7\u7A0D\u540E\u91CD\u8BD5\u3002",
      operation_failed: "Toqraq \u65E0\u6CD5\u5B8C\u6210\u672C\u5730\u7EC4\u4EF6\u64CD\u4F5C\uFF0C\u8BF7\u91CD\u8BD5\uFF1B\u5982\u9700\u652F\u6301\u8BF7\u63D0\u4F9B\u8FFD\u8E2A ID\u3002",
      in_use: "\u8FD0\u884C\u4E2D\u7684\u6E38\u620F\u6B63\u5728\u4F7F\u7528\u6B64\u7EC4\u4EF6\uFF0C\u8BF7\u5148\u505C\u6B62\u5BF9\u5E94\u6E38\u620F\u518D\u79FB\u9664\u3002"
    },
    project: {
      invalid: "\u6240\u9009\u76EE\u5F55\u4E0D\u662F\u6709\u6548\u7684\u6E38\u620F\u9879\u76EE\uFF0C\u8BF7\u68C0\u67E5\u9879\u76EE\u540E\u91CD\u8BD5\u3002"
    },
    session: {
      not_found: "\u5F53\u524D Hermes \u4F1A\u8BDD\u6CA1\u6709\u6B63\u5728\u8FD0\u884C\u7684\u6E38\u620F\u3002",
      invalid_state: "\u6E38\u620F\u5F53\u524D\u72B6\u6001\u4E0D\u5141\u8BB8\u6267\u884C\u6B64\u64CD\u4F5C\u3002",
      cleanup_failed: "\u90E8\u5206\u6E38\u620F\u8D44\u6E90\u672A\u80FD\u91CA\u653E\uFF0C\u8BF7\u5728\u7ED3\u675F\u4F1A\u8BDD\u524D\u91CD\u8BD5\u3002"
    },
    perception: {
      capability_unavailable: "\u5F53\u524D\u8FD0\u884C\u7684\u5F15\u64CE\u4E0D\u63D0\u4F9B\u6B64\u9879\u6E38\u620F\u5F00\u53D1\u80FD\u529B\u3002",
      stale: "\u5F53\u524D\u6E38\u620F\u89C2\u5BDF\u7ED3\u679C\u5DF2\u7ECF\u8FC7\u671F\uFF0C\u8BF7\u8BFB\u53D6\u6700\u65B0\u72B6\u6001\u540E\u91CD\u8BD5\u3002",
      object_not_found: "\u6240\u9009\u8FD0\u884C\u65F6\u5BF9\u8C61\u5DF2\u4E0D\u53EF\u7528\uFF0C\u8BF7\u91CD\u65B0\u8BFB\u53D6\u5C42\u7EA7\u7ED3\u6784\u3002",
      frame_unavailable: "\u6E38\u620F\u5F53\u524D\u72B6\u6001\u65E0\u6CD5\u63D0\u4F9B\u753B\u9762\uFF0C\u8BF7\u7B49\u5F85\u5C31\u7EEA\u540E\u91CD\u8BD5\u3002"
    },
    simulation: {
      invalid_state: "\u6A21\u62DF\u5668\u5F53\u524D\u72B6\u6001\u4E0D\u5141\u8BB8\u6267\u884C\u6B64\u63A7\u5236\u64CD\u4F5C\u3002"
    },
    input: {
      rejected: "\u6E38\u620F\u5F53\u524D\u72B6\u6001\u62D2\u7EDD\u4E86\u6B64\u8F93\u5165\uFF0C\u8BF7\u5237\u65B0\u6E38\u620F\u72B6\u6001\u540E\u91CD\u8BD5\u3002"
    },
    preview: {
      attach_failed: "\u65E0\u6CD5\u9644\u7740\u6E38\u620F\u9884\u89C8\uFF0C\u8BF7\u91CD\u65B0\u8FDE\u63A5\u9884\u89C8\u3002",
      host_window_not_found: "\u627E\u4E0D\u5230\u627F\u8F7D\u6B64\u9884\u89C8\u7684 Hermes \u7A97\u53E3\u3002",
      game_window_not_found: "\u6E38\u620F\u672A\u80FD\u5728\u65F6\u9650\u5185\u521B\u5EFA\u9884\u89C8\u7A97\u53E3\u3002"
    },
    bridge: {
      unavailable: "\u6E38\u620F\u8FDE\u63A5\u4E0D\u53EF\u7528\uFF0C\u8BF7\u4FDD\u6301\u6E38\u620F\u8FD0\u884C\u5E76\u91CD\u8BD5\u3002",
      protocol_invalid: "\u6E38\u620F\u6216\u8BF7\u6C42\u8FD4\u56DE\u4E86 Toqraq \u65E0\u6CD5\u5B89\u5168\u4F7F\u7528\u7684\u6570\u636E\u3002"
    },
    request: {
      invalid: "\u90E8\u5206\u8BF7\u6C42\u5B57\u6BB5\u65E0\u6548\uFF0C\u8BF7\u68C0\u67E5\u8F93\u5165\u540E\u91CD\u8BD5\u3002",
      cancelled: "\u64CD\u4F5C\u5DF2\u53D6\u6D88\u3002"
    },
    internal: {
      unexpected: "Toqraq \u9047\u5230\u610F\u5916\u6545\u969C\uFF0C\u8BF7\u91CD\u8BD5\uFF1B\u5982\u9700\u652F\u6301\u8BF7\u63D0\u4F9B\u8FFD\u8E2A ID\u3002"
    }
  },
  failure: {
    transportUnavailable: "Hermes \u65E0\u6CD5\u8FDE\u63A5 Toqraq \u540E\u7AEF\uFF0C\u8BF7\u68C0\u67E5\u63D2\u4EF6\u540E\u91CD\u8BD5\u3002",
    withTraceId: interpolated(
      ["message", "traceId"],
      (message, traceId) => `${message} \u8FFD\u8E2A ID\uFF1A${traceId}`
    )
  },
  status: {
    idle: "\u7A7A\u95F2",
    running: "\u8FD0\u884C\u4E2D",
    paused: "\u5DF2\u6682\u505C",
    stopping: "\u6B63\u5728\u505C\u6B62",
    crashed: "\u5DF2\u5D29\u6E83",
    unavailable: "\u4E0D\u53EF\u7528",
    title: "Toqraq \u6E38\u620F\u5F15\u64CE\u6865\u63A5",
    value: interpolated(["state"], (state) => `Toqraq\uFF1A${state}`)
  },
  palette: { stop: "Toqraq\uFF1A\u505C\u6B62\u6E38\u620F" }
};

// src/renderer/i18n/messages.ts
var bundles = Object.freeze({ en, zh });

// src/renderer/contributions/main.ts
import { jsx as jsx9 } from "react/jsx-runtime";
import {
  atom,
  host as host4,
  PANES_AREA,
  PALETTE_AREA,
  queryClient as queryClient2,
  STATUSBAR_AREAS
} from "@hermes/plugin-sdk";

// src/renderer/contracts/runtimeRules.ts
var BridgeIdentityResultRules = Object.freeze({
  requiredKeys: Object.freeze(["id", "protocol", "capabilities"]),
  optionalKeys: Object.freeze([]),
  "capabilities": Object.freeze({ kind: "array", maximumItems: 64, items: Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 128, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$", "u") }) }),
  "id": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 128, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$", "u") }),
  "protocol": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 128, pattern: /* @__PURE__ */ new RegExp("^[A-Za-z0-9][A-Za-z0-9._+-]*$", "u") })
});
var ComponentActiveJobsResultRules = Object.freeze({
  requiredKeys: Object.freeze(["jobs"]),
  optionalKeys: Object.freeze([]),
  "jobs": Object.freeze({ kind: "array", maximumItems: 64 })
});
var ComponentJobResultRules = Object.freeze({
  requiredKeys: Object.freeze(["operation_id", "release_id", "component_id", "action", "state", "phase", "completed_bytes", "total_bytes", "revision"]),
  optionalKeys: Object.freeze(["error"]),
  "action": Object.freeze({ values: Object.freeze(["prepare", "remove"]) }),
  "completed_bytes": Object.freeze({ kind: "integer", minimum: 0, maximum: 9007199254740991 }),
  "component_id": Object.freeze({ kind: "string", minimumLength: 3, maximumLength: 128, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$", "u") }),
  "operation_id": Object.freeze({ kind: "string", minimumLength: 36, maximumLength: 36, pattern: /* @__PURE__ */ new RegExp("^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", "u") }),
  "phase": Object.freeze({ values: Object.freeze(["checking", "downloading", "installing", "verifying", "removing", "ready"]) }),
  "release_id": Object.freeze({ kind: "string", minimumLength: 64, maximumLength: 64, pattern: /* @__PURE__ */ new RegExp("^[0-9a-f]{64}$", "u") }),
  "revision": Object.freeze({ kind: "integer", maximum: 9007199254740991, exclusiveMinimum: 0 }),
  "state": Object.freeze({ values: Object.freeze(["queued", "running", "cancelling", "ready", "failed", "cancelled"]) }),
  "total_bytes": Object.freeze({ kind: "integer", minimum: 0, maximum: 9007199254740991 })
});
var ComponentLicenseResultRules = Object.freeze({
  requiredKeys: Object.freeze(["identifier", "name", "url", "acceptance_required"]),
  optionalKeys: Object.freeze([]),
  "identifier": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 128 }),
  "name": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 256 }),
  "url": Object.freeze({ kind: "string", minimumLength: 9, maximumLength: 2048, pattern: /* @__PURE__ */ new RegExp("^https://[^\\s]+$", "u") })
});
var ComponentListResultRules = Object.freeze({
  requiredKeys: Object.freeze(["releases"]),
  optionalKeys: Object.freeze([]),
  "releases": Object.freeze({ kind: "array", maximumItems: 512 })
});
var ComponentReleaseResultRules = Object.freeze({
  requiredKeys: Object.freeze(["release_id", "component_id", "kind", "label", "version", "build_id", "platform", "architecture", "package_bytes", "installed_bytes", "package_sha256", "source", "license", "authentication_required", "capabilities", "readiness", "in_use"]),
  optionalKeys: Object.freeze([]),
  "architecture": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 32, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9_-]*$", "u") }),
  "build_id": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 128 }),
  "capabilities": Object.freeze({ kind: "array", maximumItems: 64, items: Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 128, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$", "u") }) }),
  "component_id": Object.freeze({ kind: "string", minimumLength: 3, maximumLength: 128, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$", "u") }),
  "installed_bytes": Object.freeze({ kind: "integer", maximum: 9007199254740991, exclusiveMinimum: 0 }),
  "kind": Object.freeze({ values: Object.freeze(["engine", "bridge", "tool", "model"]) }),
  "label": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 256 }),
  "package_bytes": Object.freeze({ kind: "integer", maximum: 9007199254740991, exclusiveMinimum: 0 }),
  "package_sha256": Object.freeze({ kind: "string", minimumLength: 64, maximumLength: 64, pattern: /* @__PURE__ */ new RegExp("^[0-9a-f]{64}$", "u") }),
  "platform": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 32, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9_-]*$", "u") }),
  "readiness": Object.freeze({ values: Object.freeze(["missing", "invalid", "ready"]) }),
  "release_id": Object.freeze({ kind: "string", minimumLength: 64, maximumLength: 64, pattern: /* @__PURE__ */ new RegExp("^[0-9a-f]{64}$", "u") }),
  "version": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 128 })
});
var ComponentSourceResultRules = Object.freeze({
  requiredKeys: Object.freeze(["publisher", "package_url", "provenance_url"]),
  optionalKeys: Object.freeze([]),
  "package_url": Object.freeze({ kind: "string", minimumLength: 9, maximumLength: 2048, pattern: /* @__PURE__ */ new RegExp("^https://[^\\s]+$", "u") }),
  "provenance_url": Object.freeze({ kind: "string", minimumLength: 9, maximumLength: 2048, pattern: /* @__PURE__ */ new RegExp("^https://[^\\s]+$", "u") }),
  "publisher": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 256 })
});
var EngineChoiceResultRules = Object.freeze({
  requiredKeys: Object.freeze(["id", "declared_version", "confidence"]),
  optionalKeys: Object.freeze([]),
  "confidence": Object.freeze({ kind: "integer", minimum: 1, maximum: 100 }),
  "declared_version": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 64 }),
  "id": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 64, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$", "u") })
});
var EngineSetupResultRules = Object.freeze({
  requiredKeys: Object.freeze(["id", "runtime", "available_versions", "required_component_release_ids", "runtime_install_required"]),
  optionalKeys: Object.freeze([]),
  "available_versions": Object.freeze({ kind: "array", maximumItems: 128, items: Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 64 }) }),
  "id": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 64, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$", "u") }),
  "required_component_release_ids": Object.freeze({ kind: "array", maximumItems: 32, items: Object.freeze({ kind: "string", minimumLength: 64, maximumLength: 64, pattern: /* @__PURE__ */ new RegExp("^[0-9a-f]{64}$", "u") }) })
});
var ErrorEnvelopeRules = Object.freeze({
  requiredKeys: Object.freeze(["error"]),
  optionalKeys: Object.freeze([])
});
var FeatureReadinessResultRules = Object.freeze({
  requiredKeys: Object.freeze(["state"]),
  optionalKeys: Object.freeze(["error"]),
  "state": Object.freeze({ values: Object.freeze(["unavailable", "connecting", "ready", "failed"]) })
});
var HostSetupResultRules = Object.freeze({
  requiredKeys: Object.freeze(["platform", "native_display"]),
  optionalKeys: Object.freeze([]),
  "platform": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 32, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9_-]*$", "u") })
});
var PreviewOperationResultRules = Object.freeze({
  requiredKeys: Object.freeze(["ok"]),
  optionalKeys: Object.freeze([])
});
var PreviewReadinessResultRules = Object.freeze({
  requiredKeys: Object.freeze(["state"]),
  optionalKeys: Object.freeze(["error", "surface"]),
  "state": Object.freeze({ values: Object.freeze(["unavailable", "connecting", "ready", "failed"]) })
});
var PreviewSurfaceResultRules = Object.freeze({
  requiredKeys: Object.freeze(["kind", "viewport_size"]),
  optionalKeys: Object.freeze([]),
  "kind": Object.freeze({ values: Object.freeze(["native_window", "web"]) })
});
var ProjectSetupResultRules = Object.freeze({
  requiredKeys: Object.freeze(["path", "state", "viewport_size", "probed_engine_ids"]),
  optionalKeys: Object.freeze([]),
  "path": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 32767 }),
  "probed_engine_ids": Object.freeze({ kind: "array", maximumItems: 16, items: Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 64, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$", "u") }) }),
  "state": Object.freeze({ values: Object.freeze(["unchecked", "missing", "invalid", "not_detected", "ambiguous", "ready"]) })
});
var PublicErrorRules = Object.freeze({
  requiredKeys: Object.freeze(["code", "category", "parameters", "details", "trace_id"]),
  optionalKeys: Object.freeze([]),
  "category": Object.freeze({ values: Object.freeze(["invalid", "unauthenticated", "forbidden", "not_found", "conflict", "unavailable", "timeout", "upstream", "internal"]) }),
  "code": Object.freeze({ kind: "string", minimumLength: 3, maximumLength: 96, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9]*(?:\\.[a-z][a-z0-9_]*)+$", "u") }),
  "trace_id": Object.freeze({ kind: "string", minimumLength: 36, maximumLength: 36, pattern: /* @__PURE__ */ new RegExp("^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", "u") }),
  errorJson: Object.freeze({ "maximumDepth": 4, "maximumFields": 32, "maximumKeyLength": 64, "maximumNodes": 128, "maximumSafeInteger": 9007199254740991, "maximumSequenceItems": 32, "maximumStringLength": 512 })
});
var RuntimeIdentityResultRules = Object.freeze({
  requiredKeys: Object.freeze(["engine", "version", "build_id", "distribution_id", "platform", "architecture"]),
  optionalKeys: Object.freeze([]),
  "architecture": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 128, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$", "u") }),
  "build_id": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 128, pattern: /* @__PURE__ */ new RegExp("^[A-Za-z0-9][A-Za-z0-9._+-]*$", "u") }),
  "distribution_id": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 128, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$", "u") }),
  "engine": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 64, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$", "u") }),
  "platform": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 128, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$", "u") }),
  "version": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 128, pattern: /* @__PURE__ */ new RegExp("^[A-Za-z0-9][A-Za-z0-9._+-]*$", "u") })
});
var SelectedRuntimeResultRules = Object.freeze({
  requiredKeys: Object.freeze(["version"]),
  optionalKeys: Object.freeze([]),
  "version": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 64 })
});
var SessionFailedEventRules = Object.freeze({
  requiredKeys: Object.freeze(["session_id", "sequence", "timestamp", "type", "payload"]),
  optionalKeys: Object.freeze([]),
  "sequence": Object.freeze({ kind: "integer", maximum: 9007199254740991, exclusiveMinimum: 0 }),
  "session_id": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 512 }),
  "timestamp": Object.freeze({ kind: "number", minimum: 0, maximum: 1e11 }),
  "type": Object.freeze({ values: Object.freeze(["session.failed"]) })
});
var SessionFailurePayloadRules = Object.freeze({
  requiredKeys: Object.freeze(["session", "error"]),
  optionalKeys: Object.freeze([])
});
var SessionResultRules = Object.freeze({
  requiredKeys: Object.freeze(["id", "run_revision", "runtime", "project_dir", "root_pid", "process_state", "alive", "exit_code", "started_at", "bridge", "capabilities", "preview", "perception", "control"]),
  optionalKeys: Object.freeze([]),
  "capabilities": Object.freeze({ kind: "array", maximumItems: 64, items: Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 128, pattern: /* @__PURE__ */ new RegExp("^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$", "u") }) }),
  "exit_code": Object.freeze({ kind: "integer", minimum: -9007199254740991, maximum: 9007199254740991 }),
  "id": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 512 }),
  "process_state": Object.freeze({ values: Object.freeze(["running", "paused", "stopping", "ended", "crashed"]) }),
  "project_dir": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 32767 }),
  "root_pid": Object.freeze({ kind: "integer", maximum: 9007199254740991, exclusiveMinimum: 0 }),
  "run_revision": Object.freeze({ kind: "integer", maximum: 9007199254740991, exclusiveMinimum: 0 }),
  "started_at": Object.freeze({ kind: "number", minimum: 0, maximum: 1e11 })
});
var SessionStateEventRules = Object.freeze({
  requiredKeys: Object.freeze(["session_id", "sequence", "timestamp", "type", "payload"]),
  optionalKeys: Object.freeze([]),
  "sequence": Object.freeze({ kind: "integer", maximum: 9007199254740991, exclusiveMinimum: 0 }),
  "session_id": Object.freeze({ kind: "string", minimumLength: 1, maximumLength: 512 }),
  "timestamp": Object.freeze({ kind: "number", minimum: 0, maximum: 1e11 }),
  "type": Object.freeze({ values: Object.freeze(["session.started", "session.readiness", "session.process_state", "session.stopped"]) })
});
var SetupResultRules = Object.freeze({
  requiredKeys: Object.freeze(["host", "engine", "project", "engine_choices", "action"]),
  optionalKeys: Object.freeze([]),
  "action": Object.freeze({ values: Object.freeze(["engine_unavailable", "runtime_unavailable", "install", "start", "select_project", "select_engine", "select_version", "unsupported_host"]) }),
  "engine_choices": Object.freeze({ kind: "array", maximumItems: 16 })
});
var SizeValueRules = Object.freeze({
  requiredKeys: Object.freeze(["width", "height"]),
  optionalKeys: Object.freeze([]),
  "height": Object.freeze({ kind: "integer", maximum: 32768, exclusiveMinimum: 0 }),
  "width": Object.freeze({ kind: "integer", maximum: 32768, exclusiveMinimum: 0 })
});

// src/renderer/bridge/safeData.ts
var CONTROL_CHARACTER = /\p{C}/u;
function dataRecord(value) {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  try {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) return null;
    if (Object.getOwnPropertySymbols(value).length !== 0) return null;
    const descriptors = Object.getOwnPropertyDescriptors(value);
    const result = /* @__PURE__ */ Object.create(null);
    for (const [key, descriptor] of Object.entries(descriptors)) {
      if (!safeKey(key) || !Object.hasOwn(descriptor, "value")) return null;
      result[key] = descriptor.value;
    }
    return Object.freeze(result);
  } catch {
    return null;
  }
}
function dataArray(value, maximumItems) {
  if (!Array.isArray(value)) return null;
  try {
    const lengthDescriptor = Object.getOwnPropertyDescriptor(value, "length");
    if (!lengthDescriptor || !Object.hasOwn(lengthDescriptor, "value")) return null;
    const length = lengthDescriptor.value;
    if (typeof length !== "number" || !Number.isSafeInteger(length) || length < 0 || length > maximumItems) {
      return null;
    }
    const descriptors = Object.getOwnPropertyDescriptors(value);
    const keys = Object.keys(descriptors).filter((key) => key !== "length");
    if (keys.length !== length || Object.getOwnPropertySymbols(value).length !== 0) return null;
    const result = [];
    for (let index = 0; index < length; index += 1) {
      const descriptor = descriptors[String(index)];
      if (!descriptor || !descriptor.enumerable || !Object.hasOwn(descriptor, "value")) return null;
      result.push(descriptor.value);
    }
    return Object.freeze(result);
  } catch {
    return null;
  }
}
function recordValue(value, rule, name) {
  const source = dataRecord(value);
  if (!source) invalid(name);
  const keys = Object.keys(source);
  if (rule.requiredKeys.some((key) => !Object.hasOwn(source, key)) || keys.some(
    (key) => !rule.requiredKeys.includes(key) && !rule.optionalKeys.includes(key)
  )) {
    invalid(name);
  }
  return source;
}
function hasExactKeys(value, expected) {
  return Object.keys(value).length === expected.length && expected.every((key) => Object.hasOwn(value, key));
}
function safeKey(key) {
  return key.length > 0 && !CONTROL_CHARACTER.test(key) && key !== "__proto__" && key !== "prototype" && key !== "constructor";
}
function codePointLength(value) {
  return Array.from(value).length;
}
function stringValue(value, rule, name) {
  if (typeof value !== "string") invalid(name);
  const length = codePointLength(value);
  if (rule.minimumLength !== void 0 && length < rule.minimumLength || rule.maximumLength !== void 0 && length > rule.maximumLength || rule.pattern !== void 0 && !rule.pattern.test(value)) {
    invalid(name);
  }
  return value;
}
function nullableStringValue(value, rule, name) {
  return value === null ? null : stringValue(value, rule, name);
}
function enumValue(value, rule, name) {
  if (typeof value !== "string") invalid(name);
  const match = rule.values.find((candidate) => candidate === value);
  if (match === void 0) invalid(name);
  return match;
}
function booleanValue(value, name) {
  if (typeof value !== "boolean") invalid(name);
  return value;
}
function numberValue(value, rule, name) {
  if (typeof value !== "number" || !Number.isFinite(value) || !withinBounds(value, rule)) {
    invalid(name);
  }
  return value;
}
function integerValue(value, rule, name) {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || !withinBounds(value, rule)) {
    invalid(name);
  }
  return value;
}
function arrayValue(value, rule, name) {
  const source = dataArray(value, rule.maximumItems);
  if (!source || rule.minimumItems !== void 0 && source.length < rule.minimumItems) {
    invalid(name);
  }
  return source;
}
function stringArrayValue(value, rule, name) {
  return Object.freeze(arrayValue(value, rule, name).map((item) => stringValue(item, rule.items, name)));
}
function decodeSize(value) {
  const source = recordValue(value, SizeValueRules, "size");
  return Object.freeze({
    width: integerValue(source.width, SizeValueRules.width, "width"),
    height: integerValue(source.height, SizeValueRules.height, "height")
  });
}
function invalid(name) {
  throw new TypeError(`invalid Toqraq ${name}`);
}
function withinBounds(value, rule) {
  return !(rule.minimum !== void 0 && value < rule.minimum || rule.maximum !== void 0 && value > rule.maximum || rule.exclusiveMinimum !== void 0 && value <= rule.exclusiveMinimum || rule.exclusiveMaximum !== void 0 && value >= rule.exclusiveMaximum);
}

// src/renderer/bridge/errorBoundary.ts
var ERROR_JSON = PublicErrorRules.errorJson;
var ToqraqApiError = class extends Error {
  code;
  category;
  parameters;
  details;
  traceId;
  constructor(failure, message) {
    super(message);
    this.name = "ToqraqApiError";
    this.code = failure.code;
    this.category = failure.category;
    this.parameters = failure.parameters;
    this.details = failure.details;
    this.traceId = failure.trace_id;
  }
};
function unwrap(value, translate) {
  const envelope = dataRecord(value);
  if (!envelope) {
    try {
      if (typeof value === "object" && value !== null && Object.hasOwn(value, "error")) {
        throw transportError(translate);
      }
    } catch (error) {
      if (error instanceof ToqraqApiError) throw error;
      throw transportError(translate);
    }
    return value;
  }
  if (!Object.hasOwn(envelope, "error")) return value;
  if (!hasExactKeys(envelope, ErrorEnvelopeRules.requiredKeys)) throw transportError(translate);
  const failure = decodePublicError(envelope.error);
  if (!failure) throw transportError(translate);
  throw new ToqraqApiError(failure, localizePublicError(translate, failure));
}
function normalizeThrown(ctx, error) {
  if (error instanceof ToqraqApiError) return error;
  const translate = ctx.i18n.t;
  const candidate = dataRecord(error);
  const response = dataRecord(candidate?.response);
  const body = candidate?.body ?? candidate?.data ?? response?.data;
  try {
    unwrap(body, translate);
  } catch (nested) {
    if (nested instanceof ToqraqApiError) return nested;
  }
  return transportError(translate);
}
function decodePublicError(value) {
  try {
    return decodePublicErrorValue(value);
  } catch {
    return null;
  }
}
function decodePublicErrorValue(value) {
  const source = recordValue(value, PublicErrorRules, "public error");
  const code = stringValue(source.code, PublicErrorRules.code, "error code");
  const category = enumValue(source.category, PublicErrorRules.category, "error category");
  const traceId = stringValue(source.trace_id, PublicErrorRules.trace_id, "trace id");
  const parameters = decodeFields(source.parameters, { remaining: ERROR_JSON.maximumNodes });
  const details = decodeFields(source.details, { remaining: ERROR_JSON.maximumNodes });
  if (!parameters || !details) return null;
  return Object.freeze({
    code,
    category,
    parameters,
    details,
    trace_id: traceId
  });
}
function decodeFields(value, budget) {
  const source = dataRecord(value);
  if (!source || Object.keys(source).length > ERROR_JSON.maximumFields) return null;
  const result = /* @__PURE__ */ Object.create(null);
  for (const [key, item] of Object.entries(source)) {
    if (!safeKey(key) || codePointLength(key) > ERROR_JSON.maximumKeyLength) return null;
    const decoded = decodeJson(item, 1, budget);
    if (!decoded.ok) return null;
    result[key] = decoded.value;
  }
  return Object.freeze(result);
}
function decodeJson(value, depth, budget) {
  budget.remaining -= 1;
  if (budget.remaining < 0 || depth > ERROR_JSON.maximumDepth) return { ok: false };
  if (value === null || typeof value === "boolean") return { ok: true, value };
  if (typeof value === "number") {
    const safe = Number.isFinite(value) && (!Number.isInteger(value) || Math.abs(value) <= ERROR_JSON.maximumSafeInteger);
    return safe ? { ok: true, value } : { ok: false };
  }
  if (typeof value === "string") {
    return codePointLength(value) <= ERROR_JSON.maximumStringLength ? { ok: true, value } : { ok: false };
  }
  if (Array.isArray(value)) {
    const items = dataArray(value, ERROR_JSON.maximumSequenceItems);
    if (!items) return { ok: false };
    const result2 = [];
    for (const item of items) {
      const decoded = decodeJson(item, depth + 1, budget);
      if (!decoded.ok) return { ok: false };
      result2.push(decoded.value);
    }
    return { ok: true, value: Object.freeze(result2) };
  }
  const source = dataRecord(value);
  if (!source || Object.keys(source).length > ERROR_JSON.maximumFields) return { ok: false };
  const result = /* @__PURE__ */ Object.create(null);
  for (const [key, item] of Object.entries(source)) {
    if (!safeKey(key) || codePointLength(key) > ERROR_JSON.maximumKeyLength) return { ok: false };
    const decoded = decodeJson(item, depth + 1, budget);
    if (!decoded.ok) return { ok: false };
    result[key] = decoded.value;
  }
  return { ok: true, value: Object.freeze(result) };
}
function localizePublicError(translate, failure) {
  return translate("failure.withTraceId", translate(`errors.${failure.code}`), failure.trace_id);
}
function localizeApiError(translate, error) {
  return translate("failure.withTraceId", translate(`errors.${error.code}`), error.traceId);
}
function transportError(translate) {
  const failure = Object.freeze({
    code: "transport.unavailable",
    category: "unavailable",
    parameters: Object.freeze({}),
    details: Object.freeze({ retryable: true }),
    trace_id: globalThis.crypto.randomUUID()
  });
  const message = translate(
    "failure.withTraceId",
    translate("failure.transportUnavailable"),
    failure.trace_id
  );
  return new ToqraqApiError(failure, message);
}

// src/renderer/bridge/sessionDecoders.ts
function decodeOptionalSession(value) {
  return value === null ? null : decodeSession(value);
}
function decodeSession(value) {
  const source = recordValue(value, SessionResultRules, "session result");
  const processState = enumValue(
    source.process_state,
    SessionResultRules.process_state,
    "process state"
  );
  const alive = booleanValue(source.alive, "session alive");
  const exitCode = source.exit_code === null ? null : integerValue(source.exit_code, SessionResultRules.exit_code, "exit code");
  validateProcessState(processState, alive, exitCode);
  const capabilities = decodeCapabilities(
    source.capabilities,
    SessionResultRules.capabilities,
    "session capabilities"
  );
  const bridge = decodeBridge(source.bridge);
  if (bridge.capabilities.some((capability) => !capabilities.includes(capability))) {
    invalid("bridge capability subset");
  }
  return Object.freeze({
    id: stringValue(source.id, SessionResultRules.id, "session id"),
    run_revision: integerValue(
      source.run_revision,
      SessionResultRules.run_revision,
      "run revision"
    ),
    runtime: decodeRuntime(source.runtime),
    project_dir: stringValue(source.project_dir, SessionResultRules.project_dir, "project path"),
    root_pid: integerValue(source.root_pid, SessionResultRules.root_pid, "process id"),
    process_state: processState,
    alive,
    exit_code: exitCode,
    started_at: numberValue(source.started_at, SessionResultRules.started_at, "start timestamp"),
    bridge,
    capabilities,
    preview: decodePreviewReadiness(source.preview),
    perception: decodeReadiness(source.perception, "perception readiness"),
    control: decodeReadiness(source.control, "control readiness")
  });
}
function decodeSessionEvent(value) {
  const candidate = dataRecord(value);
  if (!candidate) invalid("session event");
  if (candidate.type === "session.failed") return decodeFailureEvent(value);
  const source = recordValue(value, SessionStateEventRules, "session event");
  const sessionId = stringValue(
    source.session_id,
    SessionStateEventRules.session_id,
    "event session id"
  );
  const payload = decodeSession(source.payload);
  if (payload.id !== sessionId) invalid("session event owner");
  return Object.freeze({
    session_id: sessionId,
    sequence: integerValue(source.sequence, SessionStateEventRules.sequence, "event sequence"),
    timestamp: numberValue(source.timestamp, SessionStateEventRules.timestamp, "event timestamp"),
    type: enumValue(source.type, SessionStateEventRules.type, "session event type"),
    payload
  });
}
function decodeFailureEvent(value) {
  const source = recordValue(value, SessionFailedEventRules, "failure event");
  const sessionId = stringValue(
    source.session_id,
    SessionFailedEventRules.session_id,
    "event session id"
  );
  const payload = recordValue(
    source.payload,
    SessionFailurePayloadRules,
    "failure event payload"
  );
  const session = decodeSession(payload.session);
  const error = decodePublicError(payload.error);
  if (!error || session.id !== sessionId) invalid("failure event");
  return Object.freeze({
    session_id: sessionId,
    sequence: integerValue(source.sequence, SessionFailedEventRules.sequence, "event sequence"),
    timestamp: numberValue(source.timestamp, SessionFailedEventRules.timestamp, "event timestamp"),
    type: enumValue(source.type, SessionFailedEventRules.type, "session event type"),
    payload: Object.freeze({ session, error })
  });
}
function decodeRuntime(value) {
  const source = recordValue(value, RuntimeIdentityResultRules, "runtime identity");
  return Object.freeze({
    engine: stringValue(source.engine, RuntimeIdentityResultRules.engine, "runtime engine"),
    version: stringValue(source.version, RuntimeIdentityResultRules.version, "runtime version"),
    build_id: stringValue(source.build_id, RuntimeIdentityResultRules.build_id, "runtime build"),
    distribution_id: stringValue(
      source.distribution_id,
      RuntimeIdentityResultRules.distribution_id,
      "runtime distribution"
    ),
    platform: stringValue(
      source.platform,
      RuntimeIdentityResultRules.platform,
      "runtime platform"
    ),
    architecture: stringValue(
      source.architecture,
      RuntimeIdentityResultRules.architecture,
      "runtime architecture"
    )
  });
}
function decodeBridge(value) {
  const source = recordValue(value, BridgeIdentityResultRules, "bridge identity");
  return Object.freeze({
    id: stringValue(source.id, BridgeIdentityResultRules.id, "bridge id"),
    protocol: stringValue(source.protocol, BridgeIdentityResultRules.protocol, "bridge protocol"),
    capabilities: decodeCapabilities(
      source.capabilities,
      BridgeIdentityResultRules.capabilities,
      "bridge capabilities"
    )
  });
}
function decodeCapabilities(value, rule, name) {
  const result = stringArrayValue(value, rule, name);
  if (new Set(result).size !== result.length || !isSorted(result)) invalid(name);
  return result;
}
function decodePreviewReadiness(value) {
  const source = recordValue(value, PreviewReadinessResultRules, "preview readiness");
  const base = decodeReadinessSource(
    source,
    PreviewReadinessResultRules.state,
    "preview readiness"
  );
  const surfaceValue = Object.hasOwn(source, "surface") ? source.surface : null;
  const surface = surfaceValue === null ? null : decodePreviewSurface(surfaceValue);
  if (base.state === "ready" !== (surface !== null)) invalid("preview readiness surface");
  return Object.freeze({ ...base, surface });
}
function decodeReadiness(value, name) {
  const source = recordValue(value, FeatureReadinessResultRules, name);
  return Object.freeze(decodeReadinessSource(source, FeatureReadinessResultRules.state, name));
}
function decodeReadinessSource(source, stateRule, name) {
  const state = enumValue(source.state, stateRule, `${name} state`);
  const errorValue = Object.hasOwn(source, "error") ? source.error : null;
  const error = errorValue === null ? null : decodePublicError(errorValue);
  if (errorValue !== null && error === null) invalid(`${name} error`);
  if (state === "failed" !== (error !== null)) invalid(`${name} error`);
  return { state, error };
}
function decodePreviewSurface(value) {
  const source = recordValue(value, PreviewSurfaceResultRules, "preview surface");
  return Object.freeze({
    kind: enumValue(source.kind, PreviewSurfaceResultRules.kind, "preview surface kind"),
    viewport_size: decodeSize(source.viewport_size)
  });
}
function validateProcessState(state, alive, exitCode) {
  if (state === "running" || state === "paused") {
    if (!alive || exitCode !== null) invalid("live process state");
    return;
  }
  if (state === "ended" || state === "crashed") {
    if (alive || exitCode === null) invalid("terminal process state");
    return;
  }
  if (alive !== (exitCode === null)) invalid("stopping process state");
}
function isSorted(values) {
  for (let index = 1; index < values.length; index += 1) {
    const previous = values[index - 1];
    const current = values[index];
    if (previous === void 0 || current === void 0 || previous > current) return false;
  }
  return true;
}

// src/renderer/bridge/sessionEventClient.ts
function openEvents(ctx, sessionId, onEvent, onError) {
  try {
    return ctx.socket(`/sessions/${encodeURIComponent(sessionId)}/events`, (data) => {
      try {
        void Promise.resolve(onEvent(decodeSessionEvent(unwrap(data, ctx.i18n.t)))).catch(
          (error) => onError?.(normalizeThrown(ctx, error))
        );
      } catch (error) {
        onError?.(normalizeThrown(ctx, error));
      }
    });
  } catch (error) {
    onError?.(normalizeThrown(ctx, error));
    return () => {
    };
  }
}

// src/renderer/bridge/transport.ts
var REQUEST_TIMEOUT_MS = 30 * 1e3;
async function requestDecoded(ctx, path, options, decode) {
  try {
    return decode(unwrap(await ctx.rest(path, options), ctx.i18n.t));
  } catch (error) {
    throw normalizeThrown(ctx, error);
  }
}
async function requestComponentJobSnapshot(ctx, path, options, decode) {
  try {
    const value = await ctx.rest(path, options);
    const source = dataRecord(value);
    const payload = source && Object.hasOwn(source, "operation_id") ? value : unwrap(value, ctx.i18n.t);
    return decode(payload);
  } catch (error) {
    throw normalizeThrown(ctx, error);
  }
}

// src/renderer/bridge/sessionClient.ts
async function startSession(ctx, options) {
  return requestDecoded(
    ctx,
    "/sessions",
    {
      method: "POST",
      timeoutMs: REQUEST_TIMEOUT_MS,
      body: {
        project_dir: options.projectDir,
        ...options.engine ? { engine: options.engine } : {},
        ...options.version ? { version: options.version } : {},
        hermes_session: options.hermesSession
      }
    },
    (value) => ownedSession(value, options.hermesSession)
  );
}
async function stopSession(ctx, sessionId, runRevision) {
  return requestDecoded(
    ctx,
    `/sessions/${encodeURIComponent(sessionId)}`,
    { method: "DELETE", timeoutMs: REQUEST_TIMEOUT_MS, body: { run_revision: runRevision } },
    (value) => ownedSessionRun(value, sessionId, runRevision)
  );
}
async function setPaused(ctx, sessionId, paused) {
  return requestDecoded(
    ctx,
    `/sessions/${encodeURIComponent(sessionId)}/pause`,
    { method: "POST", timeoutMs: REQUEST_TIMEOUT_MS, body: { paused } },
    (value) => ownedSession(value, sessionId)
  );
}
async function getSession(ctx, sessionId) {
  return requestDecoded(
    ctx,
    `/sessions/${encodeURIComponent(sessionId)}`,
    { timeoutMs: REQUEST_TIMEOUT_MS },
    (value) => {
      const session = decodeOptionalSession(value);
      if (session !== null && session.id !== sessionId) invalidSessionIdentity();
      return session;
    }
  );
}
function ownedSession(value, sessionId) {
  const session = decodeSession(value);
  if (session.id !== sessionId) invalidSessionIdentity();
  return session;
}
function ownedSessionRun(value, sessionId, runRevision) {
  const session = ownedSession(value, sessionId);
  if (session.run_revision !== runRevision) invalidSessionIdentity();
  return session;
}
function invalidSessionIdentity() {
  throw new TypeError("invalid Toqraq session identity");
}

// src/renderer/bridge/decoders.ts
function decodeSetup(value) {
  const source = recordValue(value, SetupResultRules, "setup result");
  const host5 = recordValue(source.host, HostSetupResultRules, "setup host");
  const project = recordValue(source.project, ProjectSetupResultRules, "setup project");
  const action = enumValue(source.action, SetupResultRules.action, "setup action");
  const projectState = enumValue(project.state, ProjectSetupResultRules.state, "project state");
  const probedEngineIds = stringArrayValue(
    project.probed_engine_ids,
    ProjectSetupResultRules.probed_engine_ids,
    "probed engine id"
  );
  uniqueStrings(probedEngineIds, "probed engine ids");
  const engineChoices = Object.freeze(
    arrayValue(source.engine_choices, SetupResultRules.engine_choices, "setup engine choices").map(
      decodeSetupEngineChoice
    )
  );
  uniqueStrings(engineChoices.map((choice) => choice.id), "setup engine choices");
  const engine = source.engine === null ? null : decodeSetupEngine(source.engine);
  const result = Object.freeze({
    host: Object.freeze({
      platform: stringValue(host5.platform, HostSetupResultRules.platform, "platform"),
      native_display: booleanValue(host5.native_display, "native display")
    }),
    engine,
    project: Object.freeze({
      path: nullableStringValue(project.path, ProjectSetupResultRules.path, "project path"),
      state: projectState,
      viewport_size: project.viewport_size === null ? null : decodeSize(project.viewport_size),
      probed_engine_ids: probedEngineIds
    }),
    engine_choices: engineChoices,
    action
  });
  validateSetupResult(result);
  return result;
}
function decodeOptionalSetup(value) {
  return value === null ? null : decodeSetup(value);
}
function decodeSetupEngine(value) {
  const engine = recordValue(value, EngineSetupResultRules, "setup engine");
  const availableVersions = stringArrayValue(
    engine.available_versions,
    EngineSetupResultRules.available_versions,
    "runtime version"
  );
  uniqueStrings(availableVersions, "runtime versions");
  const releaseIds = stringArrayValue(
    engine.required_component_release_ids,
    EngineSetupResultRules.required_component_release_ids,
    "component release id"
  );
  uniqueStrings(releaseIds, "component release ids");
  const runtime = engine.runtime === null ? null : Object.freeze({
    version: stringValue(
      recordValue(engine.runtime, SelectedRuntimeResultRules, "selected runtime").version,
      SelectedRuntimeResultRules.version,
      "runtime version"
    )
  });
  const installRequired = booleanValue(
    engine.runtime_install_required,
    "runtime install requirement"
  );
  if (runtime === null && releaseIds.length > 0) invalid("unselected runtime components");
  if (runtime !== null && releaseIds.length === 0) invalid("selected runtime components");
  if (installRequired && runtime === null) invalid("runtime install requirement");
  if (runtime !== null && availableVersions.length > 0) invalid("selected runtime versions");
  return Object.freeze({
    id: stringValue(engine.id, EngineSetupResultRules.id, "engine id"),
    runtime,
    available_versions: availableVersions,
    required_component_release_ids: releaseIds,
    runtime_install_required: installRequired
  });
}
function decodeSetupEngineChoice(value) {
  const choice = recordValue(value, EngineChoiceResultRules, "setup engine choice");
  return Object.freeze({
    id: stringValue(choice.id, EngineChoiceResultRules.id, "engine id"),
    declared_version: nullableStringValue(
      choice.declared_version,
      EngineChoiceResultRules.declared_version,
      "engine version"
    ),
    confidence: integerValue(
      choice.confidence,
      EngineChoiceResultRules.confidence,
      "engine confidence"
    )
  });
}
function uniqueStrings(values, name) {
  if (new Set(values).size !== values.length) invalid(name);
}
function validateSetupResult(result) {
  const action = result.action;
  const project = result.project;
  const engine = result.engine;
  const choices = result.engine_choices;
  validateProjectProbeEvidence(project);
  if (action === "engine_unavailable") {
    if (engine !== null || choices.length !== 0 || project.state !== "unchecked") {
      invalid("engine unavailable setup state");
    }
    return;
  }
  if (action === "select_project") {
    if (engine !== null || choices.length !== 0 || !(/* @__PURE__ */ new Set(["missing", "invalid", "not_detected"])).has(project.state)) {
      invalid("project selection setup state");
    }
    return;
  }
  if (action === "select_engine") {
    if (engine !== null || choices.length < 2 || project.state !== "ambiguous") {
      invalid("engine selection setup state");
    }
    if (!sameStrings(choices.map((choice) => choice.id), project.probed_engine_ids)) {
      invalid("engine choices and project probes");
    }
    return;
  }
  if (engine === null || choices.length !== 0 || project.state !== "ready") {
    invalid("runtime setup state");
  }
  const selected = engine;
  if (!sameStrings(project.probed_engine_ids, [selected.id])) {
    invalid("selected engine and project probe");
  }
  if (action === "runtime_unavailable" || action === "unsupported_host") {
    if (selected.runtime !== null || selected.available_versions.length !== 0 || selected.required_component_release_ids.length !== 0 || selected.runtime_install_required) {
      invalid("runtime unavailable setup state");
    }
    return;
  }
  if (action === "select_version") {
    if (selected.runtime !== null || selected.available_versions.length === 0) {
      invalid("version selection setup state");
    }
    return;
  }
  if (action === "install" || action === "start") {
    if (selected.runtime === null || selected.runtime_install_required !== (action === "install")) {
      invalid("launch setup state");
    }
    return;
  }
  invalid("setup action");
}
function validateProjectProbeEvidence(project) {
  const count = project.probed_engine_ids.length;
  if (project.state === "missing" && project.path !== null) {
    invalid("missing project path");
  }
  if (project.state !== "missing" && project.state !== "unchecked" && project.path === null) {
    invalid("checked project path");
  }
  if (project.state !== "ready" && project.viewport_size !== null) {
    invalid("project viewport state");
  }
  if ((project.state === "unchecked" || project.state === "missing" || project.state === "invalid") && count !== 0) {
    invalid("unprobed project engine evidence");
  }
  if (project.state === "not_detected" && count < 1) {
    invalid("undetected project engine evidence");
  }
  if (project.state === "ambiguous" && count < 2) {
    invalid("ambiguous project engine evidence");
  }
  if (project.state === "ready" && count !== 1) {
    invalid("ready project engine evidence");
  }
}
function sameStrings(left, right) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

// src/renderer/bridge/setupClient.ts
async function checkSetup(ctx, options = {}) {
  return requestDecoded(
    ctx,
    "/setup",
    { method: "POST", timeoutMs: REQUEST_TIMEOUT_MS, body: setupBody(options) },
    decodeSetup
  );
}
async function syncWorkspaceContext(ctx, sessionId, options = {}) {
  return requestDecoded(
    ctx,
    `/workspace-context/${encodeURIComponent(sessionId)}`,
    { method: "PUT", timeoutMs: REQUEST_TIMEOUT_MS, body: setupBody(options) },
    decodeOptionalSetup
  );
}
function setupBody(options) {
  return {
    ...options.projectDir ? { project_dir: options.projectDir } : {},
    ...options.engine ? { engine: options.engine } : {},
    ...options.version ? { version: options.version } : {}
  };
}

// src/renderer/state/queryPolicy.ts
var HERMES_SESSION_ERROR_REFRESH_INTERVAL_MS = 3e3;
var COMPONENT_QUERY_RETRY_COUNT = 2;
var SETUP_QUERY_RETRY_COUNT = 2;
var SETUP_QUERY_RETRY_DELAY_MS = 1e3;

// src/renderer/state/queryKeys.ts
var COMPONENT_CATALOG_KEY = Object.freeze(["toqraq", "components"]);
var WORKSPACE_SETUP_ROOT = Object.freeze(["toqraq", "setup"]);
function hermesSessionQueryKey(sessionId) {
  return Object.freeze(["toqraq", "hermes-session", sessionId]);
}
function componentCatalogQueryKey() {
  return COMPONENT_CATALOG_KEY;
}
function activeComponentJobsQueryKey(planKey) {
  return Object.freeze(["toqraq", "component-jobs", "active", planKey]);
}
function componentJobQueryKey(operationId) {
  return Object.freeze(["toqraq", "component-job", operationId]);
}
function workspaceSetupQueryRoot() {
  return WORKSPACE_SETUP_ROOT;
}
function workspaceSetupQueryKey(ownerId, workspaceDir) {
  return Object.freeze(["toqraq", "setup", ownerId, workspaceDir]);
}

// src/renderer/state/hermesSessionReadiness.ts
function projectOwnedHermesSession(activeSessionId, gatewayOpen, statusRead) {
  if (!activeSessionId) {
    return Object.freeze({ sessionId: null, status: "needed" });
  }
  if (!gatewayOpen || statusRead === "pending") {
    return Object.freeze({ sessionId: null, status: "checking" });
  }
  if (statusRead === "error") {
    return Object.freeze({ sessionId: null, status: "unavailable" });
  }
  return Object.freeze({ sessionId: activeSessionId, status: "ready" });
}

// src/renderer/state/sessionOperations.ts
var SessionOperations = class {
  #selected = null;
  #active = /* @__PURE__ */ new Map();
  #nextSequence = 1;
  #disposed = false;
  select(sessionId) {
    if (this.#disposed) return false;
    if (this.#selected === sessionId) return false;
    this.#selected = sessionId;
    return true;
  }
  begin(sessionId) {
    if (this.#disposed || !sessionId || this.#active.has(sessionId)) return null;
    const token = Object.freeze({ owner: sessionId, sequence: this.#nextSequence });
    this.#nextSequence += 1;
    this.#active.set(sessionId, token);
    return token;
  }
  owns(token) {
    return !this.#disposed && this.#active.get(token.owner) === token;
  }
  finish(token) {
    if (!this.owns(token)) return false;
    this.#active.delete(token.owner);
    return true;
  }
  accepts(sessionId) {
    return !this.#disposed && this.#selected === sessionId;
  }
  busy() {
    return !this.#disposed && this.#selected !== null && this.#active.has(this.#selected);
  }
  dispose() {
    if (this.#disposed) return;
    this.#disposed = true;
    this.#selected = null;
    this.#active.clear();
  }
};

// src/renderer/state/sessionSnapshotOrder.ts
function canApplySessionSnapshot(current, incoming) {
  return current === null || current.id !== incoming.id || current.run_revision <= incoming.run_revision;
}
function canClearSessionRun(current, sessionId, terminalRunRevision) {
  return current !== null && current.id === sessionId && current.run_revision <= terminalRunRevision;
}

// src/renderer/state/rendererSessionStore.ts
var RendererSessionStore = class {
  gameState;
  busyState;
  #operations = new SessionOperations();
  #disposed = false;
  constructor(createAtom) {
    this.gameState = createAtom(initialGameState());
    this.busyState = createAtom(false);
  }
  get active() {
    return !this.#disposed;
  }
  applyHermesReadiness(readiness) {
    if (this.#disposed) return false;
    const current = this.gameState.get();
    const sameOwner = readiness.sessionId !== null && current.readiness.sessionId === readiness.sessionId;
    this.#operations.select(readiness.sessionId);
    const next = gameState(
      readiness,
      sameOwner ? current.sessionRead : initialReadStatus(readiness),
      sameOwner ? current.session : null
    );
    if (sameGameState(current, next)) return false;
    this.gameState.set(next);
    this.#projectBusyState();
    return true;
  }
  applySessionReadStatus(sessionId, status) {
    if (this.#disposed) return false;
    const current = this.gameState.get();
    if (current.readiness.sessionId !== sessionId || current.sessionRead === status) {
      return false;
    }
    this.gameState.set(gameState(current.readiness, status, current.session));
    return true;
  }
  beginSessionOperation(sessionId) {
    if (this.#disposed) return null;
    const token = this.#operations.begin(sessionId);
    this.#projectBusyState();
    return token;
  }
  ownsSelectedSessionOperation(token) {
    return !this.#disposed && this.#operations.owns(token) && this.#operations.accepts(token.owner);
  }
  finishSessionOperation(token) {
    if (this.#disposed) return false;
    const finished = this.#operations.finish(token);
    this.#projectBusyState();
    return finished;
  }
  currentSession() {
    return this.#disposed ? null : this.gameState.get().session;
  }
  currentGame() {
    return this.gameState.get();
  }
  /** Apply one snapshot unless this incarnation already knows a newer run. */
  applySessionSnapshot(session) {
    if (this.#disposed || !this.#operations.accepts(session.id)) return false;
    const current = this.gameState.get();
    if (!canApplySessionSnapshot(current.session, session)) return false;
    this.gameState.set(gameState(current.readiness, current.sessionRead, session));
    return true;
  }
  /** Clear only the run named by a terminal result or a newer replacement. */
  clearSessionRun(sessionId, runRevision) {
    if (this.#disposed || !this.#operations.accepts(sessionId)) return false;
    const current = this.gameState.get();
    if (!canClearSessionRun(current.session, sessionId, runRevision)) return false;
    this.gameState.set(gameState(current.readiness, current.sessionRead, null));
    return true;
  }
  dispose() {
    if (this.#disposed) return;
    this.#disposed = true;
    this.#operations.dispose();
    this.gameState.set(initialGameState());
    this.busyState.set(false);
  }
  #projectBusyState() {
    this.busyState.set(this.#operations.busy());
  }
};
function initialGameState() {
  return gameState(projectOwnedHermesSession(null, false, "pending"), "ready", null);
}
function initialReadStatus(readiness) {
  if (readiness.status === "unavailable") return "unavailable";
  return readiness.status === "ready" || readiness.status === "checking" ? "checking" : "ready";
}
function gameState(readiness, sessionRead, session) {
  return Object.freeze({ readiness, sessionRead, session });
}
function sameGameState(left, right) {
  return left.readiness.sessionId === right.readiness.sessionId && left.readiness.status === right.readiness.status && left.sessionRead === right.sessionRead && left.session === right.session;
}

// src/renderer/state/sessionEvents.ts
function createSessionEventConsumer(options) {
  let closed = false;
  let synchronized = false;
  let greatestRunRevision = ownedRevision(options.get(), options.sessionId);
  let lastSequence = null;
  let tail = Promise.resolve();
  const enqueue = (operation) => {
    tail = tail.then(operation).catch((error) => {
      if (!closed) {
        options.onError?.(
          error instanceof Error ? error : new Error("session reconcile failed")
        );
      }
    });
    return tail;
  };
  const reconcileNow = async () => {
    if (closed) return;
    const revisionBeforeRead = Math.max(
      greatestRunRevision,
      ownedRevision(options.get(), options.sessionId)
    );
    const session = await options.read(options.sessionId);
    if (closed) return;
    if (session !== null) {
      if (session.id !== options.sessionId) {
        throw new TypeError("session reconcile owner mismatch");
      }
      greatestRunRevision = Math.max(greatestRunRevision, session.run_revision);
      options.apply(session);
    } else {
      const current = options.get();
      if (current !== null && current.id === options.sessionId && current.run_revision <= revisionBeforeRead) {
        options.clear(options.sessionId, revisionBeforeRead);
      }
    }
    synchronized = true;
    options.onSynchronized?.(session);
  };
  const applyEvent = (event) => {
    const session = eventSession(event);
    const currentRevision = ownedRevision(options.get(), options.sessionId);
    if (session.run_revision < Math.max(greatestRunRevision, currentRevision)) return;
    greatestRunRevision = Math.max(greatestRunRevision, session.run_revision);
    if (event.type === "session.stopped") {
      if (options.clear(options.sessionId, session.run_revision)) options.onEnded?.(session);
      return;
    }
    options.apply(session);
  };
  return Object.freeze({
    accept(event) {
      return enqueue(async () => {
        if (closed || event.session_id !== options.sessionId) return;
        if (lastSequence !== null && event.sequence <= lastSequence) return;
        options.onObserved?.(event);
        const gap = lastSequence !== null && event.sequence !== lastSequence + 1;
        lastSequence = event.sequence;
        if (!synchronized || gap) {
          await reconcileNow();
          return;
        }
        applyEvent(event);
      });
    },
    reconcile() {
      return enqueue(reconcileNow);
    },
    close() {
      closed = true;
    }
  });
}
function eventSession(event) {
  return event.type === "session.failed" ? event.payload.session : event.payload;
}
function ownedRevision(session, sessionId) {
  return session?.id === sessionId ? session.run_revision : 0;
}

// src/renderer/state/rendererSessionSync.ts
var OPEN_GATEWAY_STATE = "open";
function startRendererSessionSync(dependencies) {
  let disposed = false;
  let generation = 0;
  let observedOwner;
  let observedGatewayOpen;
  let cancelStatus = noOp;
  let closeChannel = noOp;
  let cancelRetry = noOp;
  const current = (owner, ownerGeneration) => !disposed && generation === ownerGeneration && observedOwner === owner && observedGatewayOpen === true;
  const clearRetry = () => {
    const cancel = cancelRetry;
    cancelRetry = noOp;
    cancel();
  };
  const clearTarget = () => {
    clearRetry();
    const close = closeChannel;
    closeChannel = noOp;
    close();
    const cancel = cancelStatus;
    cancelStatus = noOp;
    cancel();
  };
  const schedule = (owner, ownerGeneration, retry) => {
    clearRetry();
    cancelRetry = dependencies.scheduleRetry(() => {
      cancelRetry = noOp;
      if (current(owner, ownerGeneration)) retry();
    });
  };
  const openChannel = (owner, ownerGeneration) => {
    let loadErrorReported = false;
    const consumer = createSessionEventConsumer({
      sessionId: owner,
      read: dependencies.readSession,
      get: () => dependencies.store.currentSession(),
      apply: (session) => dependencies.store.applySessionSnapshot(session),
      clear: (sessionId, runRevision) => dependencies.store.clearSessionRun(sessionId, runRevision),
      onSynchronized: () => {
        if (!current(owner, ownerGeneration)) return;
        loadErrorReported = false;
        clearRetry();
        dependencies.store.applySessionReadStatus(owner, "ready");
      },
      onEnded: (session) => {
        if (current(owner, ownerGeneration)) dependencies.onEnded(session);
      },
      onError: (error) => {
        if (!current(owner, ownerGeneration)) return;
        dependencies.store.applySessionReadStatus(owner, "unavailable");
        if (!loadErrorReported) {
          loadErrorReported = true;
          dependencies.onLoadError(error);
        }
        schedule(owner, ownerGeneration, () => {
          void consumer.reconcile();
        });
      }
    });
    let closeSocket = noOp;
    try {
      closeSocket = dependencies.openEvents(
        owner,
        (event) => consumer.accept(event),
        (error) => {
          if (!current(owner, ownerGeneration)) return;
          dependencies.onEventError(error);
          void consumer.reconcile();
        }
      );
    } catch (error) {
      dependencies.onEventError(error);
    }
    closeChannel = () => {
      consumer.close();
      closeSocket();
    };
    void consumer.reconcile();
  };
  const checkHermesStatus = (owner, ownerGeneration) => {
    clearRetry();
    cancelStatus();
    cancelStatus = () => dependencies.cancelHermesStatus(owner);
    dependencies.store.applyHermesReadiness(
      projectOwnedHermesSession(owner, true, "pending")
    );
    void Promise.resolve().then(() => dependencies.readHermesStatus(owner)).then(
      () => {
        if (!current(owner, ownerGeneration)) return;
        dependencies.store.applyHermesReadiness(
          projectOwnedHermesSession(owner, true, "success")
        );
        openChannel(owner, ownerGeneration);
      },
      () => {
        if (!current(owner, ownerGeneration)) return;
        dependencies.store.applyHermesReadiness(
          projectOwnedHermesSession(owner, true, "error")
        );
        schedule(owner, ownerGeneration, () => {
          checkHermesStatus(owner, ownerGeneration);
        });
      }
    );
  };
  const reconcile = () => {
    if (disposed) return;
    const owner = dependencies.activeSessionId.get();
    const gatewayOpen = dependencies.gateway.get() === OPEN_GATEWAY_STATE;
    if (owner === observedOwner && gatewayOpen === observedGatewayOpen) return;
    generation += 1;
    clearTarget();
    observedOwner = owner;
    observedGatewayOpen = gatewayOpen;
    dependencies.store.applyHermesReadiness(
      projectOwnedHermesSession(owner, gatewayOpen, "pending")
    );
    if (owner && gatewayOpen) checkHermesStatus(owner, generation);
  };
  const subscriptions = [
    dependencies.activeSessionId.subscribe(reconcile),
    dependencies.gateway.subscribe(reconcile)
  ];
  return () => {
    if (disposed) return;
    disposed = true;
    generation += 1;
    for (const unsubscribe of subscriptions.reverse()) unsubscribe();
    clearTarget();
  };
}
function noOp() {
}

// src/renderer/state/stopGameFlow.ts
async function executeStopGame(ctx, sessionId, ports) {
  const operation = ports.beginSessionOperation(sessionId);
  if (operation === null) return false;
  const observed = ports.currentSession();
  const observedRevision = observed?.id === sessionId ? observed.run_revision : null;
  try {
    const current = await ports.getSession(ctx, sessionId);
    if (current === null) {
      if (observedRevision !== null) ports.clearSessionRun(sessionId, observedRevision);
      return false;
    }
    ports.applySessionSnapshot(current);
    if (observedRevision !== null && current.run_revision !== observedRevision) return false;
    const requestedRevision = current.run_revision;
    try {
      const stopped = await ports.stopSession(ctx, sessionId, requestedRevision);
      requireStoppedRun(stopped, sessionId, requestedRevision);
      ports.clearSessionRun(sessionId, requestedRevision);
      return true;
    } catch (error) {
      if (!isRunReplacement(error)) throw error;
      const replacement = await ports.getSession(ctx, sessionId);
      if (replacement === null) ports.clearSessionRun(sessionId, requestedRevision);
      else ports.applySessionSnapshot(replacement);
      return false;
    }
  } finally {
    ports.finishSessionOperation(operation);
  }
}
function requireStoppedRun(stopped, sessionId, runRevision) {
  if (stopped.id !== sessionId || stopped.run_revision !== runRevision) {
    throw new TypeError("invalid Toqraq stopped run identity");
  }
}
function isRunReplacement(error) {
  return error instanceof ToqraqApiError && error.code === "session.invalid_state" && error.details.reason === "run_replaced";
}

// src/renderer/state/stopGame.ts
async function stopGame(ctx, store, sessionId) {
  return executeStopGame(ctx, sessionId, {
    beginSessionOperation: (owner) => store.beginSessionOperation(owner),
    finishSessionOperation: (token) => store.finishSessionOperation(token),
    currentSession: () => store.currentSession(),
    applySessionSnapshot: (session) => store.applySessionSnapshot(session),
    clearSessionRun: (owner, runRevision) => store.clearSessionRun(owner, runRevision),
    getSession,
    stopSession
  });
}

// src/renderer/state/workspace.ts
var WINDOWS_DRIVE_ROOT = /^[A-Za-z]:[\\/]/;
var WINDOWS_UNC_ROOT = /^\\\\[^\\/]+[\\/][^\\/]+(?:[\\/]|$)/;
function absoluteWorkspace(value) {
  if (typeof value !== "string") return "";
  const candidate = value.trim();
  if (candidate.startsWith("/") || WINDOWS_DRIVE_ROOT.test(candidate) || WINDOWS_UNC_ROOT.test(candidate)) {
    return candidate;
  }
  return "";
}

// src/renderer/state/workspaceContextSync.ts
var OPEN_GATEWAY_STATE2 = "open";
function startWorkspaceContextSync(dependencies) {
  let disposed = false;
  let currentKey = "";
  const reconcile = () => {
    if (disposed) return;
    const ownerId = dependencies.activeSessionId.get();
    if (!ownerId || dependencies.gateway.get() !== OPEN_GATEWAY_STATE2) {
      currentKey = "";
      return;
    }
    const workspaceDir = absoluteWorkspace(dependencies.cwd.get());
    const nextKey = JSON.stringify([ownerId, workspaceDir]);
    if (nextKey === currentKey) return;
    currentKey = nextKey;
    try {
      void dependencies.fetch(ownerId, workspaceDir).catch(() => {
        if (!disposed && currentKey === nextKey) currentKey = "";
      });
    } catch {
      if (currentKey === nextKey) currentKey = "";
    }
  };
  const subscriptions = [
    dependencies.activeSessionId.subscribe(reconcile),
    dependencies.cwd.subscribe(reconcile),
    dependencies.gateway.subscribe(reconcile)
  ];
  return () => {
    if (disposed) return;
    disposed = true;
    for (const unsubscribe of subscriptions.reverse()) unsubscribe();
  };
}

// src/renderer/ui/StatusChip.ts
import { jsx, jsxs } from "react/jsx-runtime";
import { StatusDot, usePluginI18n, useValue } from "@hermes/plugin-sdk";

// src/renderer/state/runtimePresentation.ts
function projectGameRuntimeState(game) {
  if (game.readiness.status === "unavailable" || game.session === null && game.sessionRead === "unavailable") return "unavailable";
  return projectRuntimeState(game.session);
}
function projectRuntimeState(session) {
  if (!session || session.process_state === "ended") return "idle";
  return session.process_state;
}

// src/renderer/ui/StatusChip.ts
function StatusChip({ sessionStore }) {
  const t = usePluginI18n("toqraq");
  const processState = projectGameRuntimeState(useValue(sessionStore.gameState));
  const tone = processState === "running" || processState === "paused" ? "good" : processState === "stopping" ? "warn" : processState === "idle" ? "muted" : "bad";
  const dotProps = { tone };
  return jsxs("span", {
    role: "status",
    "aria-live": "polite",
    "aria-atomic": true,
    className: "flex items-center gap-1 px-1.5 text-[0.6875rem] text-(--ui-text-tertiary)",
    title: t("status.title"),
    children: [
      jsx(StatusDot, dotProps),
      t("status.value", t(`status.${processState}`))
    ]
  });
}

// src/renderer/ui/ViewportPane.ts
import { useCallback as useCallback4, useRef as useRef3 } from "react";
import { jsx as jsx8, jsxs as jsxs8 } from "react/jsx-runtime";
import { host as host3, usePluginI18n as usePluginI18n8, useValue as useValue3 } from "@hermes/plugin-sdk";

// src/renderer/hooks/useGameLifecycle.ts
import { useCallback } from "react";
import { haptic, host } from "@hermes/plugin-sdk";

// src/renderer/state/pauseAvailability.ts
function canPauseGame(session) {
  return Boolean(
    session?.alive && (session.process_state === "running" || session.process_state === "paused") && session.control.state === "ready" && session.capabilities.includes("toqraq.play.pause")
  );
}

// src/renderer/hooks/useGameLifecycle.ts
function useGameLifecycle({
  ctx,
  t,
  store,
  sessionId,
  sessionStatus,
  selectedSession,
  workspaceDir,
  setupView,
  invalidateSetup
}) {
  const start = useCallback(async () => {
    if (!sessionId || sessionStatus !== "ready") {
      host.notify({ kind: "warning", message: t("notify.needSession") });
      return;
    }
    if (!workspaceDir) {
      host.notify({ kind: "warning", message: t("notify.needProject") });
      return;
    }
    if (!setupView.startable) {
      host.notify({ kind: "warning", message: blockedStartMessage(t, setupView) });
      return;
    }
    const operation = store.beginSessionOperation(sessionId);
    if (operation === null) return;
    try {
      try {
        await host.request("session.status", { session_id: sessionId });
      } catch {
        if (store.ownsSelectedSessionOperation(operation)) {
          host.notify({ kind: "warning", message: t("notify.needSession") });
        }
        return;
      }
      if (!store.ownsSelectedSessionOperation(operation)) return;
      try {
        const started = await startSession(ctx, { projectDir: workspaceDir, hermesSession: sessionId });
        if (store.applySessionSnapshot(started)) {
          await invalidateSetup();
          haptic("success");
        }
      } catch (error) {
        if (store.ownsSelectedSessionOperation(operation)) {
          host.notifyError(normalizeThrown(ctx, error), t("notify.startFailed"));
        }
      }
    } finally {
      store.finishSessionOperation(operation);
    }
  }, [ctx, t, store, sessionId, sessionStatus, workspaceDir, setupView, invalidateSetup]);
  const stop = useCallback(async () => {
    if (!selectedSession?.id) return;
    const owner = selectedSession.id;
    try {
      await stopGame(ctx, store, owner);
    } catch (error) {
      if (store.active && host.state.activeSessionId.get() === owner) {
        host.notifyError(normalizeThrown(ctx, error), t("notify.stopFailed"));
      }
    }
  }, [ctx, t, selectedSession, store]);
  const togglePause = useCallback(async () => {
    if (!canPauseGame(selectedSession)) return;
    const operation = store.beginSessionOperation(selectedSession.id);
    if (operation === null) return;
    try {
      store.applySessionSnapshot(
        await setPaused(ctx, selectedSession.id, selectedSession.process_state !== "paused")
      );
    } catch (error) {
      if (store.ownsSelectedSessionOperation(operation)) {
        host.notifyError(normalizeThrown(ctx, error), t("notify.pauseFailed"));
      }
    } finally {
      store.finishSessionOperation(operation);
    }
  }, [ctx, t, selectedSession, store]);
  return { canPause: canPauseGame(selectedSession), start, stop, togglePause };
}
function blockedStartMessage(t, setupView) {
  if (setupView.headline === "host") return t("notify.unsupportedHost");
  if (setupView.headline === "hostUnavailable") return t("notify.displayUnavailable");
  if (setupView.headline === "install") return t("notify.componentRequired");
  return t("notify.projectInvalid");
}

// src/renderer/hooks/useNativeDisplay.ts
import { useEffect, useLayoutEffect, useRef, useState } from "react";

// src/renderer/bridge/previewDecoders.ts
function decodePreviewOperation(value) {
  const source = recordValue(value, PreviewOperationResultRules, "preview operation");
  return Object.freeze({ ok: booleanValue(source.ok, "preview operation acknowledgement") });
}

// src/renderer/bridge/previewClient.ts
async function attachNativePreview(ctx, attachment) {
  return requestDecoded(
    ctx,
    "/preview/native/attach",
    {
      method: "POST",
      timeoutMs: REQUEST_TIMEOUT_MS,
      body: {
        session_id: attachment.sessionId,
        attachment_id: attachment.attachmentId,
        pane_rect: attachment.paneRect
      }
    },
    (value) => {
      const session = decodeSession(value);
      if (session.id !== attachment.sessionId) invalidPreviewOwner();
      return session;
    }
  );
}
async function followNativePreview(ctx, sessionId, attachmentId, paneRect) {
  return requestDecoded(
    ctx,
    "/preview/native/rect",
    {
      method: "POST",
      timeoutMs: REQUEST_TIMEOUT_MS,
      body: { session_id: sessionId, attachment_id: attachmentId, pane_rect: paneRect }
    },
    decodePreviewOperation
  );
}
async function setNativePreviewVisible(ctx, sessionId, attachmentId, visible) {
  return requestDecoded(
    ctx,
    "/preview/native/visible",
    {
      method: "POST",
      timeoutMs: REQUEST_TIMEOUT_MS,
      body: { session_id: sessionId, attachment_id: attachmentId, visible }
    },
    decodePreviewOperation
  );
}
async function detachNativePreview(ctx, sessionId, attachmentId) {
  return requestDecoded(
    ctx,
    "/preview/native/detach",
    {
      method: "POST",
      timeoutMs: REQUEST_TIMEOUT_MS,
      body: { session_id: sessionId, attachment_id: attachmentId }
    },
    decodePreviewOperation
  );
}
function invalidPreviewOwner() {
  throw new TypeError("invalid Toqraq preview session identity");
}

// src/renderer/lib/viewportMath.ts
var WINDOWS_MINIMIZED_COORDINATE = -3e4;
function isUsableScreenRect(rect) {
  return rect.x > WINDOWS_MINIMIZED_COORDINATE && rect.y > WINDOWS_MINIMIZED_COORDINATE;
}
function elementScreenRect(element) {
  const rect = element.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const sideBorder = Math.max(0, (window.outerWidth - window.innerWidth) / 2);
  const chromeTop = Math.max(0, window.outerHeight - window.innerHeight - sideBorder);
  return {
    x: Math.round((window.screenX + sideBorder + rect.left) * dpr),
    y: Math.round((window.screenY + chromeTop + rect.top) * dpr),
    width: Math.round(rect.width * dpr),
    height: Math.round(rect.height * dpr)
  };
}

// src/renderer/bridge/rectReporter.ts
var MIN_REPORT_INTERVAL_MS = 33;
var RESIZE_SETTLE_DELAY_MS = 140;
var POSITION_PROBE_INTERVAL_MS = 500;
var RectReporter = class {
  _element;
  _onRect;
  _observer = null;
  _frame = 0;
  _probeTimer = 0;
  _settleTimer = 0;
  _lastSentAt = 0;
  _lastKey = "";
  _lastRect = null;
  _hasReported = false;
  _forceSettled = false;
  constructor(element, onRect) {
    this._element = element;
    this._onRect = onRect;
  }
  /** Start observing and report the initial pane as already settled. */
  start() {
    this.stop();
    this._lastSentAt = 0;
    this._lastKey = "";
    this._lastRect = null;
    this._hasReported = false;
    this._forceSettled = false;
    this._observer = new ResizeObserver(() => this._schedule());
    this._observer.observe(this._element);
    this._probeTimer = window.setInterval(() => this._schedule(), POSITION_PROBE_INTERVAL_MS);
    this._schedule();
  }
  /** Stop observing and cancel every pending measurement or settle signal. */
  stop() {
    this._observer?.disconnect();
    this._observer = null;
    if (this._frame) cancelAnimationFrame(this._frame);
    if (this._probeTimer) window.clearInterval(this._probeTimer);
    if (this._settleTimer) window.clearTimeout(this._settleTimer);
    this._frame = 0;
    this._probeTimer = 0;
    this._settleTimer = 0;
  }
  /** Force a fresh settled measurement after visibility or layout restoration. */
  refresh() {
    this._lastKey = "";
    this._forceSettled = true;
    this._schedule();
  }
  _schedule() {
    if (this._frame) return;
    this._frame = requestAnimationFrame(() => {
      this._frame = 0;
      const now = performance.now();
      if (now - this._lastSentAt < MIN_REPORT_INTERVAL_MS) {
        this._schedule();
        return;
      }
      if (document.visibilityState !== "visible") return;
      const rect = elementScreenRect(this._element);
      if (rect.width < 1 || rect.height < 1 || !isUsableScreenRect(rect)) return;
      const key = `${rect.x},${rect.y},${rect.width},${rect.height}`;
      if (key === this._lastKey) return;
      this._lastKey = key;
      this._lastRect = rect;
      this._lastSentAt = now;
      if (!this._hasReported || this._forceSettled) {
        this._hasReported = true;
        this._forceSettled = false;
        if (this._settleTimer) window.clearTimeout(this._settleTimer);
        this._settleTimer = 0;
        this._onRect(rect, true);
        return;
      }
      this._onRect(rect, false);
      this._scheduleSettled();
    });
  }
  _scheduleSettled() {
    if (this._settleTimer) window.clearTimeout(this._settleTimer);
    this._settleTimer = window.setTimeout(() => {
      this._settleTimer = 0;
      if (document.visibilityState === "visible" && this._lastRect !== null) {
        this._onRect(this._lastRect, true);
      }
    }, RESIZE_SETTLE_DELAY_MS);
  }
};

// src/renderer/state/nativePreviewController.ts
var INITIAL_PREVIEW_RETRY_DELAY_MS = 500;
var MAX_PREVIEW_RETRY_DELAY_MS = 8e3;
var NativePreviewController = class {
  #sessionId;
  #runRevision;
  #documentVisible;
  #api;
  #scheduleRetry;
  #cancelRetry;
  #onStatus;
  #onError;
  #pane = null;
  #paneRevision = 0;
  #appliedPaneRevision = 0;
  #resizeActive = false;
  #attached = false;
  #actualVisible = null;
  #closed = false;
  #drivePromise = null;
  #closePromise = null;
  #retryHandle = null;
  #retryDelay = INITIAL_PREVIEW_RETRY_DELAY_MS;
  #errorReported = false;
  constructor(options) {
    this.#sessionId = options.sessionId;
    this.#runRevision = options.runRevision;
    this.#documentVisible = options.documentVisible;
    this.#api = options.api;
    this.#scheduleRetry = options.scheduleRetry;
    this.#cancelRetry = options.cancelRetry;
    this.#onStatus = options.onStatus;
    this.#onError = options.onError;
    this.#onStatus("connecting");
  }
  /** Accept the newest pane and whether drag-resize has settled. */
  updatePane(pane, settled) {
    if (this.#closed) return Promise.resolve();
    this.#pane = Object.freeze({ ...pane });
    this.#paneRevision += 1;
    this.#resizeActive = !settled;
    return this.#requestDrive();
  }
  setDocumentVisible(visible) {
    if (this.#closed || this.#documentVisible === visible) {
      return this.#drivePromise ?? Promise.resolve();
    }
    this.#documentVisible = visible;
    return this.#requestDrive();
  }
  /** Restore the native window after all already-started effects settle. */
  close() {
    if (this.#closePromise !== null) return this.#closePromise;
    this.#closed = true;
    this.#cancelScheduledRetry();
    this.#closePromise = this.#finishClose();
    return this.#closePromise;
  }
  async #finishClose() {
    await this.#drivePromise;
    requireAcknowledged(await this.#api.detach());
  }
  #requestDrive() {
    this.#cancelScheduledRetry();
    if (this.#drivePromise === null) {
      const running = this.#drive();
      this.#drivePromise = running;
      void running.finally(() => {
        if (this.#drivePromise === running) this.#drivePromise = null;
      });
    }
    return this.#drivePromise;
  }
  async #drive() {
    try {
      while (!this.#closed && this.#pane !== null) {
        if (!this.#attached) {
          await this.#attachCurrentPane();
          continue;
        }
        const desiredVisible = this.#documentVisible && !this.#resizeActive;
        if (!desiredVisible && this.#actualVisible !== false) {
          await this.#setVisible(false);
          continue;
        }
        if (this.#appliedPaneRevision < this.#paneRevision) {
          await this.#followCurrentPane();
          continue;
        }
        if (this.#actualVisible !== desiredVisible) {
          await this.#setVisible(desiredVisible);
          continue;
        }
        this.#errorReported = false;
        this.#retryDelay = INITIAL_PREVIEW_RETRY_DELAY_MS;
        this.#onStatus("attached");
        return;
      }
    } catch (error) {
      if (this.#closed || error instanceof StaleNativePreviewOwnerError) return;
      this.#onStatus("failed");
      if (!this.#errorReported) {
        this.#errorReported = true;
        this.#onError(error);
      }
      this.#scheduleRetryAfterFailure();
    }
  }
  async #attachCurrentPane() {
    const pane = this.#requirePane();
    const revision = this.#paneRevision;
    const session = await this.#api.attach({ paneRect: pane });
    if (session.id !== this.#sessionId || session.run_revision !== this.#runRevision) {
      requireAcknowledged(await this.#api.detach());
      throw new StaleNativePreviewOwnerError();
    }
    if (this.#closed) return;
    this.#attached = true;
    this.#actualVisible = null;
    this.#appliedPaneRevision = revision;
  }
  async #followCurrentPane() {
    const pane = this.#requirePane();
    const revision = this.#paneRevision;
    requireAcknowledged(await this.#api.follow(pane));
    if (!this.#closed) this.#appliedPaneRevision = revision;
  }
  async #setVisible(visible) {
    requireAcknowledged(await this.#api.setVisible(visible));
    if (!this.#closed) this.#actualVisible = visible;
  }
  #requirePane() {
    if (this.#pane === null) throw new TypeError("native preview pane is unavailable");
    return this.#pane;
  }
  #scheduleRetryAfterFailure() {
    if (this.#closed || this.#retryHandle !== null) return;
    const delay = this.#retryDelay;
    this.#retryDelay = Math.min(this.#retryDelay * 2, MAX_PREVIEW_RETRY_DELAY_MS);
    this.#retryHandle = this.#scheduleRetry(() => {
      this.#retryHandle = null;
      if (!this.#closed) void this.#requestDrive();
    }, delay);
  }
  #cancelScheduledRetry() {
    if (this.#retryHandle === null) return;
    this.#cancelRetry(this.#retryHandle);
    this.#retryHandle = null;
  }
};
function requireAcknowledged(result) {
  if (!result.ok) throw new Error("native preview operation was not acknowledged");
}
var StaleNativePreviewOwnerError = class extends Error {
  constructor() {
    super("native preview owner was replaced");
    this.name = "StaleNativePreviewOwnerError";
  }
};

// src/renderer/state/nativePreviewProjection.ts
function projectNativePreview(session, attachmentState) {
  if (!session) return projection(null, "setup");
  if (session.process_state === "stopping") return projection(null, "unavailable");
  if (!session.alive) return projection(null, "setup");
  if (session.process_state !== "running" && session.process_state !== "paused" || !session.capabilities.includes("toqraq.preview.display")) {
    return projection(null, "unavailable");
  }
  if (session.preview.state === "failed") return projection(null, "failed");
  if (session.preview.state === "connecting") return projection(null, "connecting");
  if (session.preview.state !== "ready" || session.preview.surface?.kind !== "native_window") {
    return projection(null, "unavailable");
  }
  const status = attachmentOwnerMatches(attachmentState, session) ? attachmentState.status : "connecting";
  return projection(session, status === "failed" ? "retrying" : status);
}
function attachmentOwnerMatches(attachmentState, session) {
  return Boolean(
    attachmentState && attachmentState.sessionId === session.id && attachmentState.runRevision === session.run_revision
  );
}
function projection(attachment, view) {
  return Object.freeze({ attachment, view });
}

// src/renderer/hooks/useNativeDisplay.ts
function useNativeDisplay({
  ctx,
  session,
  elementRef,
  onError
}) {
  const [attachmentState, setAttachmentState] = useState(null);
  const errorRef = useRef(onError);
  errorRef.current = onError;
  const preview = projectNativePreview(session, attachmentState);
  const sessionId = preview.attachment?.id ?? null;
  const runRevision = preview.attachment?.run_revision ?? null;
  useLayoutEffect(() => {
    if (preview.attachment === null && attachmentState !== null) {
      setAttachmentState(null);
    }
  }, [preview.attachment, attachmentState]);
  useEffect(() => {
    const element = elementRef.current;
    if (!sessionId || !runRevision || !element) {
      return void 0;
    }
    let disposed = false;
    const cleanupErrorSink = errorRef.current;
    const attachmentId = globalThis.crypto.randomUUID();
    const controller = new NativePreviewController({
      sessionId,
      runRevision,
      documentVisible: document.visibilityState === "visible",
      api: {
        attach: ({ paneRect }) => attachNativePreview(ctx, {
          sessionId,
          attachmentId,
          paneRect
        }),
        follow: (paneRect) => followNativePreview(ctx, sessionId, attachmentId, paneRect),
        setVisible: (visible) => setNativePreviewVisible(ctx, sessionId, attachmentId, visible),
        detach: () => detachNativePreview(ctx, sessionId, attachmentId)
      },
      scheduleRetry: (callback, delayMs) => window.setTimeout(callback, delayMs),
      cancelRetry: (handle) => {
        if (typeof handle === "number") window.clearTimeout(handle);
      },
      onStatus: (nextStatus) => {
        if (!disposed) {
          setAttachmentState(Object.freeze({ sessionId, runRevision, status: nextStatus }));
        }
      },
      onError: (error) => {
        if (!disposed) errorRef.current(normalizeThrown(ctx, error));
      }
    });
    const reporter = new RectReporter(element, (rect, settled) => {
      void controller.updatePane(rect, settled).then(() => {
        if (settled && document.visibilityState === "visible") {
          void controller.setDocumentVisible(true);
        }
      });
    });
    reporter.start();
    const onVisibility = () => {
      const visible = document.visibilityState === "visible";
      if (visible) reporter.refresh();
      else void controller.setDocumentVisible(false);
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      disposed = true;
      reporter.stop();
      document.removeEventListener("visibilitychange", onVisibility);
      void controller.close().catch((error) => {
        cleanupErrorSink(normalizeThrown(ctx, error));
      });
    };
  }, [ctx, sessionId, runRevision, elementRef]);
  return preview.view;
}

// src/renderer/hooks/useViewportSetup.ts
import { useCallback as useCallback2 } from "react";
import { host as host2, queryClient, useQuery, useValue as useValue2 } from "@hermes/plugin-sdk";

// src/renderer/state/setupView.ts
function shouldCheckSetup(workspaceDir, sessionOwned) {
  return workspaceDir.length > 0 && !sessionOwned;
}
function deriveSetupView({
  setup,
  sessionStatus,
  workspacePresent,
  checking,
  failed = false
}) {
  if (!workspacePresent) {
    return {
      headline: "workspaceMissing",
      showReadiness: false,
      showComponentPlan: false,
      retryable: false,
      startable: false,
      session: sessionStatus,
      host: "checking",
      project: "missing",
      runtime: "checking"
    };
  }
  if (failed) {
    const headline2 = sessionStatus === "needed" ? "session" : sessionStatus === "unavailable" ? "sessionUnavailable" : "setupUnavailable";
    return {
      headline: headline2,
      showReadiness: true,
      showComponentPlan: false,
      retryable: headline2 === "setupUnavailable",
      startable: false,
      session: sessionStatus,
      host: "checking",
      project: "checking",
      runtime: "checking"
    };
  }
  if (checking || !setup) {
    return {
      headline: sessionStatus === "needed" ? "session" : sessionStatus === "unavailable" ? "sessionUnavailable" : "checking",
      showReadiness: true,
      showComponentPlan: false,
      retryable: false,
      startable: false,
      session: sessionStatus,
      host: "checking",
      project: "checking",
      runtime: "checking"
    };
  }
  const project = setup.project.state;
  const host5 = setup.action !== "unsupported_host" ? "ready" : setup.host.platform === "windows" && !setup.host.native_display ? "unavailable" : "unsupported";
  const runtime = setup.engine === null ? "unavailable" : setup.action === "select_version" ? "choice" : setup.engine.runtime_install_required ? "required" : setup.engine.runtime === null ? "unavailable" : "ready";
  let headline = "ready";
  if (setup.action === "engine_unavailable") headline = "engineUnavailable";
  else if (setup.action === "runtime_unavailable") headline = "runtimeUnavailable";
  else if (sessionStatus === "needed") headline = "session";
  else if (sessionStatus === "unavailable") headline = "sessionUnavailable";
  else if (sessionStatus === "checking") headline = "checking";
  else if (setup.action === "select_engine") headline = "engineChoice";
  else if (setup.action === "select_version") headline = "versionChoice";
  else if (host5 === "unsupported") headline = "host";
  else if (host5 === "unavailable") headline = "hostUnavailable";
  else if (project === "invalid" || project === "not_detected") headline = "projectInvalid";
  else if (project !== "ready") headline = "projectMissing";
  else if (setup.action === "install") headline = "install";
  return {
    headline,
    showReadiness: true,
    showComponentPlan: setup.action === "install" || setup.action === "start",
    retryable: false,
    startable: sessionStatus === "ready" && setup.action === "start",
    session: sessionStatus,
    host: host5,
    project,
    runtime
  };
}

// src/renderer/hooks/useViewportSetup.ts
function useViewportSetup({
  ctx,
  sessionId,
  sessionStatus,
  sessionOwned
}) {
  const workspaceDir = absoluteWorkspace(useValue2(host2.state.cwd));
  const enabled = shouldCheckSetup(workspaceDir, sessionOwned);
  const queryKey = workspaceSetupQueryKey(sessionId, workspaceDir);
  const setupQuery = useQuery({
    queryKey,
    enabled,
    queryFn: () => sessionId ? syncWorkspaceContext(ctx, sessionId, { projectDir: workspaceDir }) : checkSetup(ctx, { projectDir: workspaceDir }),
    retry: SETUP_QUERY_RETRY_COUNT,
    retryDelay: SETUP_QUERY_RETRY_DELAY_MS,
    staleTime: Infinity
  });
  const setup = enabled ? setupQuery.data ?? null : null;
  const view = deriveSetupView({
    setup,
    sessionStatus,
    workspacePresent: Boolean(workspaceDir),
    checking: enabled && setupQuery.isPending,
    failed: enabled && setupQuery.isError
  });
  const invalidate = useCallback2(async () => {
    await queryClient.invalidateQueries({ queryKey });
  }, [sessionId, workspaceDir]);
  const componentTerminal = useCallback2(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: componentCatalogQueryKey() }),
      queryClient.invalidateQueries({ queryKey })
    ]);
  }, [sessionId, workspaceDir]);
  const retry = useCallback2(() => {
    void setupQuery.refetch();
  }, [setupQuery]);
  return {
    workspaceDir,
    setup,
    view,
    retrying: setupQuery.isFetching,
    retry,
    invalidate,
    componentTerminal
  };
}

// src/renderer/ui/Toolbar.ts
import { jsx as jsx2, jsxs as jsxs2 } from "react/jsx-runtime";
import { Button, icons, usePluginI18n as usePluginI18n2 } from "@hermes/plugin-sdk";
function Toolbar(props) {
  const t = usePluginI18n2("toqraq");
  const pauseLabel = props.paused ? t("toolbar.resumeTitle") : t("toolbar.pauseTitle");
  const stopLabel = props.processState === "stopping" ? t("toolbar.finishStopTitle") : t("toolbar.stopTitle");
  return jsxs2("div", {
    role: "toolbar",
    "aria-label": t("toolbar.runtimeControls"),
    className: "flex items-center gap-1.5 px-2 py-1.5 border-b border-(--ui-stroke-secondary)",
    children: [
      jsxs2("div", {
        className: "flex min-w-0 flex-1 items-baseline gap-2",
        children: [
          jsx2("span", {
            className: "min-w-0 flex-1 truncate text-xs text-(--ui-text-secondary)",
            title: props.projectDir,
            children: props.projectDir
          }),
          jsx2("span", {
            className: "shrink-0 text-[0.6875rem] text-(--ui-text-tertiary)",
            children: t(
              "toolbar.runtimeIdentity",
              props.runtime.engine,
              props.runtime.version
            )
          }),
          jsx2("span", {
            className: `shrink-0 text-[0.6875rem] ${props.paused ? "text-(--ui-accent)" : "text-(--ui-text-tertiary)"}`,
            children: t(
              "toolbar.processState",
              t(`status.${props.processState}`)
            )
          })
        ]
      }),
      props.canPause && jsx2(Button, {
        size: "sm",
        variant: "ghost",
        disabled: props.busy,
        onClick: props.onTogglePause,
        title: pauseLabel,
        "aria-label": pauseLabel,
        className: props.paused ? "text-(--ui-accent)" : void 0,
        children: props.paused ? jsx2(icons.Play, { size: 13 }) : jsx2(icons.Pause, { size: 13 })
      }),
      jsx2(Button, {
        size: "sm",
        variant: "ghost",
        disabled: props.busy,
        onClick: props.onStop,
        title: stopLabel,
        "aria-label": stopLabel,
        className: "text-destructive hover:text-destructive",
        children: jsx2(icons.Square, { size: 13 })
      })
    ]
  });
}

// src/renderer/ui/ViewportSurface.ts
import { jsx as jsx7, jsxs as jsxs7 } from "react/jsx-runtime";
import { usePluginI18n as usePluginI18n7 } from "@hermes/plugin-sdk";

// src/renderer/ui/SetupGuide.ts
import { jsx as jsx6, jsxs as jsxs6 } from "react/jsx-runtime";
import { Button as Button4, icons as icons2, usePluginI18n as usePluginI18n6 } from "@hermes/plugin-sdk";

// src/renderer/ui/ComponentSetup.ts
import { jsx as jsx5, jsxs as jsxs5 } from "react/jsx-runtime";
import { Button as Button3, usePluginI18n as usePluginI18n5 } from "@hermes/plugin-sdk";

// src/renderer/hooks/useComponentSetup.ts
import { useCallback as useCallback3, useEffect as useEffect2, useRef as useRef2, useState as useState2 } from "react";
import { useQuery as useQuery2 } from "@hermes/plugin-sdk";

// src/renderer/bridge/componentDecoders.ts
var ACTIVE_JOB_STATES = /* @__PURE__ */ new Set([
  "queued",
  "running",
  "cancelling"
]);
var PREPARE_PHASES = /* @__PURE__ */ new Set([
  "checking",
  "downloading",
  "installing",
  "verifying",
  "ready"
]);
var REMOVE_PHASES = /* @__PURE__ */ new Set(["checking", "removing", "ready"]);
function decodeComponentList(value) {
  const source = recordValue(value, ComponentListResultRules, "component list");
  const releases = arrayValue(
    source.releases,
    ComponentListResultRules.releases,
    "component releases"
  );
  return Object.freeze({ releases: Object.freeze(releases.map(decodeRelease)) });
}
function decodeActiveComponentJobs(value) {
  const source = recordValue(value, ComponentActiveJobsResultRules, "active component jobs");
  const jobs = arrayValue(
    source.jobs,
    ComponentActiveJobsResultRules.jobs,
    "active component jobs"
  ).map(decodeComponentJob);
  const operationIds = /* @__PURE__ */ new Set();
  const releaseIds = /* @__PURE__ */ new Set();
  for (const job of jobs) {
    if (!ACTIVE_JOB_STATES.has(job.state) || operationIds.has(job.operation_id) || releaseIds.has(job.release_id)) {
      invalid("active component jobs");
    }
    operationIds.add(job.operation_id);
    releaseIds.add(job.release_id);
  }
  return Object.freeze({ jobs: Object.freeze(jobs) });
}
function decodeComponentJob(value) {
  const source = recordValue(value, ComponentJobResultRules, "component job");
  const action = enumValue(source.action, ComponentJobResultRules.action, "component job action");
  const state = enumValue(source.state, ComponentJobResultRules.state, "component job state");
  const phase = enumValue(source.phase, ComponentJobResultRules.phase, "component job phase");
  const completedBytes = integerValue(
    source.completed_bytes,
    ComponentJobResultRules.completed_bytes,
    "component job completed bytes"
  );
  const totalBytes = integerValue(
    source.total_bytes,
    ComponentJobResultRules.total_bytes,
    "component job total bytes"
  );
  const errorValue = Object.hasOwn(source, "error") ? source.error : null;
  const error = errorValue === null ? null : decodePublicError(errorValue);
  if (errorValue !== null && !error) invalid("component job error");
  validateJob(action, state, phase, completedBytes, totalBytes, error);
  return Object.freeze({
    operation_id: stringValue(
      source.operation_id,
      ComponentJobResultRules.operation_id,
      "operation id"
    ),
    release_id: stringValue(source.release_id, ComponentJobResultRules.release_id, "release id"),
    component_id: stringValue(
      source.component_id,
      ComponentJobResultRules.component_id,
      "component id"
    ),
    action,
    state,
    phase,
    completed_bytes: completedBytes,
    total_bytes: totalBytes,
    revision: integerValue(
      source.revision,
      ComponentJobResultRules.revision,
      "component job revision"
    ),
    error
  });
}
function decodeRelease(value) {
  const source = recordValue(value, ComponentReleaseResultRules, "component release");
  const capabilities = stringArrayValue(
    source.capabilities,
    ComponentReleaseResultRules.capabilities,
    "component capability"
  );
  const componentKind = enumValue(source.kind, ComponentReleaseResultRules.kind, "component kind");
  const readiness = enumValue(
    source.readiness,
    ComponentReleaseResultRules.readiness,
    "component readiness"
  );
  return Object.freeze({
    release_id: stringValue(source.release_id, ComponentReleaseResultRules.release_id, "release id"),
    component_id: stringValue(
      source.component_id,
      ComponentReleaseResultRules.component_id,
      "component id"
    ),
    kind: componentKind,
    label: stringValue(source.label, ComponentReleaseResultRules.label, "component label"),
    version: stringValue(source.version, ComponentReleaseResultRules.version, "component version"),
    build_id: stringValue(source.build_id, ComponentReleaseResultRules.build_id, "component build id"),
    platform: stringValue(
      source.platform,
      ComponentReleaseResultRules.platform,
      "component platform"
    ),
    architecture: stringValue(
      source.architecture,
      ComponentReleaseResultRules.architecture,
      "component architecture"
    ),
    package_bytes: integerValue(
      source.package_bytes,
      ComponentReleaseResultRules.package_bytes,
      "package bytes"
    ),
    installed_bytes: integerValue(
      source.installed_bytes,
      ComponentReleaseResultRules.installed_bytes,
      "installed bytes"
    ),
    package_sha256: stringValue(
      source.package_sha256,
      ComponentReleaseResultRules.package_sha256,
      "package digest"
    ),
    source: decodeSource(source.source),
    license: decodeLicense(source.license),
    authentication_required: booleanValue(
      source.authentication_required,
      "authentication requirement"
    ),
    capabilities,
    readiness,
    in_use: booleanValue(source.in_use, "component lease state")
  });
}
function decodeSource(value) {
  const source = recordValue(value, ComponentSourceResultRules, "component source");
  return Object.freeze({
    publisher: stringValue(
      source.publisher,
      ComponentSourceResultRules.publisher,
      "component publisher"
    ),
    package_url: stringValue(
      source.package_url,
      ComponentSourceResultRules.package_url,
      "component package URL"
    ),
    provenance_url: stringValue(
      source.provenance_url,
      ComponentSourceResultRules.provenance_url,
      "component provenance URL"
    )
  });
}
function decodeLicense(value) {
  const source = recordValue(value, ComponentLicenseResultRules, "component license");
  return Object.freeze({
    identifier: stringValue(
      source.identifier,
      ComponentLicenseResultRules.identifier,
      "license identifier"
    ),
    name: stringValue(source.name, ComponentLicenseResultRules.name, "license name"),
    url: stringValue(source.url, ComponentLicenseResultRules.url, "license URL"),
    acceptance_required: booleanValue(
      source.acceptance_required,
      "license acceptance requirement"
    )
  });
}
function validateJob(action, state, phase, completedBytes, totalBytes, error) {
  const allowedPhases = action === "prepare" ? PREPARE_PHASES : REMOVE_PHASES;
  if (!allowedPhases.has(phase)) invalid("component job action phase");
  if (completedBytes > totalBytes) invalid("component job progress");
  if (state === "failed" !== (error !== null)) invalid("component job failure state");
  if (state === "ready" !== (phase === "ready")) invalid("component job ready phase");
  if (state === "ready" && completedBytes !== totalBytes) invalid("component job completion");
  if (state === "queued" && phase !== "checking") invalid("component job queued phase");
}

// src/renderer/bridge/componentClient.ts
async function listComponents(ctx) {
  return requestDecoded(ctx, "/components", { timeoutMs: REQUEST_TIMEOUT_MS }, decodeComponentList);
}
async function listActiveComponentJobs(ctx) {
  return requestDecoded(
    ctx,
    "/component-jobs/active",
    { timeoutMs: REQUEST_TIMEOUT_MS },
    decodeActiveComponentJobs
  );
}
async function startComponentJob(ctx, releaseId, action) {
  return requestComponentJobSnapshot(
    ctx,
    "/component-jobs",
    {
      method: "POST",
      timeoutMs: REQUEST_TIMEOUT_MS,
      body: { release_id: releaseId, action }
    },
    (value) => {
      const job = decodeComponentJob(value);
      if (job.release_id !== releaseId || job.action !== action) invalidComponentJobIdentity();
      return job;
    }
  );
}
async function getComponentJob(ctx, operationId) {
  return requestComponentJobSnapshot(
    ctx,
    `/component-jobs/${encodeURIComponent(operationId)}`,
    { timeoutMs: REQUEST_TIMEOUT_MS },
    (value) => {
      const job = decodeComponentJob(value);
      if (job.operation_id !== operationId) invalidComponentJobIdentity();
      return job;
    }
  );
}
async function cancelComponentJob(ctx, operationId) {
  return requestComponentJobSnapshot(
    ctx,
    `/component-jobs/${encodeURIComponent(operationId)}/cancel`,
    { method: "POST", timeoutMs: REQUEST_TIMEOUT_MS },
    (value) => {
      const job = decodeComponentJob(value);
      if (job.operation_id !== operationId) invalidComponentJobIdentity();
      return job;
    }
  );
}
function invalidComponentJobIdentity() {
  throw new TypeError("invalid Toqraq component job identity");
}

// src/renderer/state/componentJobs.ts
var EMPTY_JOBS = Object.freeze({});
function createComponentJobState() {
  return Object.freeze({ byOperationId: EMPTY_JOBS });
}
function reconcileComponentJob(state, snapshot) {
  const current = state.byOperationId[snapshot.operation_id];
  if (current && current.revision >= snapshot.revision) return state;
  return Object.freeze({
    byOperationId: Object.freeze({
      ...state.byOperationId,
      [snapshot.operation_id]: snapshot
    })
  });
}
function selectComponentJob(state, operationId) {
  return Object.hasOwn(state.byOperationId, operationId) ? state.byOperationId[operationId] ?? null : null;
}

// src/renderer/state/componentSetup.ts
var COMPONENT_JOB_POLL_INTERVAL_MS = 750;
var COMPONENT_JOB_RETRY_INTERVAL_MS = 4e3;
function resolveSetupComponentPlan(setup, components) {
  if (!setup?.engine || !components) return null;
  const releaseIds = setup.engine.required_component_release_ids;
  if (releaseIds.length === 0) return null;
  const catalog = /* @__PURE__ */ new Map();
  for (const release of components.releases) {
    if (catalog.has(release.release_id)) return null;
    catalog.set(release.release_id, release);
  }
  const requested = /* @__PURE__ */ new Set();
  const releases = [];
  for (const releaseId of releaseIds) {
    if (requested.has(releaseId)) return null;
    requested.add(releaseId);
    const release = catalog.get(releaseId);
    if (!release) return null;
    releases.push(release);
  }
  return Object.freeze(releases);
}
function componentJobPollInterval(job, readFailed = false) {
  if (job && !isActiveComponentJob(job)) return false;
  if (readFailed) return COMPONENT_JOB_RETRY_INTERVAL_MS;
  return job ? COMPONENT_JOB_POLL_INTERVAL_MS : false;
}
function isActiveComponentJob(job) {
  return job.state === "queued" || job.state === "running" || job.state === "cancelling";
}
function selectRecoverableComponentJob(requiredReleaseIds, activeJobs, ignoredOperationId = "") {
  if (!activeJobs || requiredReleaseIds.length === 0) return null;
  const planIds = new Set(requiredReleaseIds);
  if (planIds.size !== requiredReleaseIds.length) return null;
  const operationIds = /* @__PURE__ */ new Set();
  const jobsByRelease = /* @__PURE__ */ new Map();
  for (const job of activeJobs.jobs) {
    if (!isActiveComponentJob(job) || operationIds.has(job.operation_id) || jobsByRelease.has(job.release_id)) {
      return null;
    }
    operationIds.add(job.operation_id);
    jobsByRelease.set(job.release_id, job);
  }
  for (const releaseId of requiredReleaseIds) {
    const job = jobsByRelease.get(releaseId);
    if (job?.action === "prepare" && job.operation_id !== ignoredOperationId) return job;
  }
  return null;
}
function isMissingRecoveredComponentJob(operationId, recoveredOperationId, errorCode) {
  return Boolean(
    operationId && operationId === recoveredOperationId && errorCode === "component.job_not_found"
  );
}
function nextTerminalComponentOperation(job, observedOperationId) {
  if (!job || isActiveComponentJob(job) || job.operation_id === observedOperationId) {
    return null;
  }
  return job.operation_id;
}
function shouldAdvanceComponentRecovery(job, operationId) {
  return Boolean(
    job && job.operation_id === operationId && job.state === "ready"
  );
}
function deriveComponentActions(release, job) {
  const sameRelease = job?.release_id === release.release_id ? job : null;
  const active = sameRelease ? isActiveComponentJob(sameRelease) : false;
  const failed = sameRelease?.state === "failed" || sameRelease?.state === "cancelled";
  return Object.freeze({
    canPrepare: !active && release.readiness !== "ready",
    canRemove: !active && !release.in_use && release.readiness === "ready",
    canCancel: sameRelease?.state === "queued" || sameRelease?.state === "running",
    canRetry: Boolean(failed),
    active
  });
}
function componentProgress(job) {
  if (!job || job.total_bytes === 0) return null;
  return Math.min(1, job.completed_bytes / job.total_bytes);
}
function deriveComponentCardState(release, job, requesting) {
  const releaseJob = job?.release_id === release.release_id ? job : null;
  return Object.freeze({
    job: releaseJob,
    actions: deriveComponentActions(release, releaseJob),
    actionDisabled: requesting || Boolean(job && !releaseJob && isActiveComponentJob(job)),
    progress: componentProgress(releaseJob)
  });
}
function componentPrepareActionKey(release) {
  if (release.readiness === "invalid") {
    return release.license.acceptance_required ? "component.action.acceptAndRepair" : "component.action.repair";
  }
  return release.license.acceptance_required ? "component.action.acceptAndPrepare" : "component.action.prepare";
}

// src/renderer/hooks/useComponentSetup.ts
function useComponentSetup(ctx, enabled, requiredReleaseIds, onTerminal) {
  const [jobs, setJobs] = useState2(createComponentJobState);
  const [operationId, setOperationId] = useState2(null);
  const [requesting, setRequesting] = useState2(false);
  const [requestError, setRequestError] = useState2(null);
  const observedTerminal = useRef2("");
  const mounted = useRef2(false);
  const requestInFlight = useRef2(false);
  const requestRevision = useRef2(0);
  const recoveredOperation = useRef2("");
  const ignoredRecoveryOperation = useRef2("");
  const planKey = requiredReleaseIds.join(":");
  const currentPlan = useRef2(planKey);
  const job = operationId ? selectComponentJob(jobs, operationId) : null;
  useEffect2(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      requestInFlight.current = false;
      requestRevision.current += 1;
    };
  }, []);
  useEffect2(() => {
    if (currentPlan.current === planKey) return;
    currentPlan.current = planKey;
    requestRevision.current += 1;
    requestInFlight.current = false;
    recoveredOperation.current = "";
    ignoredRecoveryOperation.current = "";
    observedTerminal.current = "";
    setRequesting(false);
    setRequestError(null);
    setJobs(createComponentJobState());
    setOperationId(null);
  }, [planKey]);
  const componentsQuery = useQuery2({
    queryKey: componentCatalogQueryKey(),
    enabled,
    queryFn: () => listComponents(ctx),
    retry: COMPONENT_QUERY_RETRY_COUNT
  });
  const activeJobsQuery = useQuery2({
    queryKey: activeComponentJobsQueryKey(planKey),
    enabled: enabled && requiredReleaseIds.length > 0 && !operationId,
    queryFn: () => listActiveComponentJobs(ctx),
    retry: COMPONENT_QUERY_RETRY_COUNT,
    refetchOnMount: "always"
  });
  const jobQuery = useQuery2({
    queryKey: componentJobQueryKey(operationId),
    enabled: enabled && Boolean(operationId),
    queryFn: () => getComponentJob(ctx, operationId ?? ""),
    retry: COMPONENT_QUERY_RETRY_COUNT,
    refetchInterval: (query) => componentJobPollInterval(
      query.state.data ?? null,
      query.state.status === "error"
    )
  });
  useEffect2(() => {
    if (!enabled || operationId || !activeJobsQuery.data || activeJobsQuery.error || activeJobsQuery.isFetching) {
      return;
    }
    const recovered = selectRecoverableComponentJob(
      requiredReleaseIds,
      activeJobsQuery.data,
      ignoredRecoveryOperation.current
    );
    if (!recovered) return;
    setJobs((current) => reconcileComponentJob(current, recovered));
    recoveredOperation.current = recovered.operation_id;
    setOperationId(recovered.operation_id);
  }, [
    activeJobsQuery.data,
    activeJobsQuery.error,
    activeJobsQuery.isFetching,
    enabled,
    operationId,
    planKey,
    requiredReleaseIds
  ]);
  useEffect2(() => {
    if (!jobQuery.data || jobQuery.data.operation_id !== operationId) return;
    setJobs((current) => reconcileComponentJob(current, jobQuery.data));
  }, [jobQuery.data, operationId]);
  useEffect2(() => {
    const errorCode = jobQuery.error instanceof ToqraqApiError ? jobQuery.error.code : "";
    if (!operationId || !isMissingRecoveredComponentJob(
      operationId,
      recoveredOperation.current,
      errorCode
    )) {
      return;
    }
    ignoredRecoveryOperation.current = operationId;
    recoveredOperation.current = "";
    observedTerminal.current = operationId;
    setOperationId(null);
    void onTerminal().catch((error) => {
      if (mounted.current && ignoredRecoveryOperation.current === operationId) {
        setRequestError(normalizeThrown(ctx, error));
      }
    });
  }, [ctx, jobQuery.error, onTerminal, operationId]);
  useEffect2(() => {
    if (!enabled) return;
    const terminalOperation = nextTerminalComponentOperation(job, observedTerminal.current);
    if (!terminalOperation) return;
    observedTerminal.current = terminalOperation;
    const terminalPlan = currentPlan.current;
    if (shouldAdvanceComponentRecovery(job, terminalOperation)) {
      ignoredRecoveryOperation.current = terminalOperation;
      recoveredOperation.current = "";
      setOperationId(null);
    }
    void onTerminal().catch((error) => {
      if (mounted.current && currentPlan.current === terminalPlan) {
        setRequestError(normalizeThrown(ctx, error));
      }
    });
  }, [ctx, enabled, job, onTerminal]);
  const performRequest = useCallback3(
    async (request) => {
      if (!mounted.current || requestInFlight.current) return;
      requestInFlight.current = true;
      const revision = ++requestRevision.current;
      setRequesting(true);
      setRequestError(null);
      try {
        const snapshot = await request();
        if (!mounted.current || requestRevision.current !== revision) return;
        setJobs((current) => reconcileComponentJob(current, snapshot));
        recoveredOperation.current = "";
        setOperationId(snapshot.operation_id);
      } catch (error) {
        if (mounted.current && requestRevision.current === revision) {
          setRequestError(normalizeThrown(ctx, error));
        }
      } finally {
        if (requestRevision.current === revision) {
          requestInFlight.current = false;
          if (mounted.current) setRequesting(false);
        }
      }
    },
    [ctx]
  );
  const start = useCallback3(
    async (releaseId, action) => {
      await performRequest(() => startComponentJob(ctx, releaseId, action));
    },
    [ctx, performRequest]
  );
  const cancel = useCallback3(async () => {
    if (!operationId) return;
    await performRequest(() => cancelComponentJob(ctx, operationId));
  }, [ctx, operationId, performRequest]);
  const retry = useCallback3(async () => {
    if (!job) return;
    await start(job.release_id, job.action);
  }, [job, start]);
  return Object.freeze({
    components: componentsQuery.data ?? null,
    componentsPending: componentsQuery.isPending,
    componentsRefreshing: componentsQuery.isFetching,
    componentsError: componentsQuery.error ?? null,
    job,
    jobError: operationId ? jobQuery.error ?? null : activeJobsQuery.error ?? null,
    requestError,
    requesting: requesting || enabled && requiredReleaseIds.length > 0 && !operationId && activeJobsQuery.isFetching,
    refreshComponents: async () => {
      setRequestError(null);
      await componentsQuery.refetch();
    },
    start,
    cancel,
    retry
  });
}

// src/renderer/ui/ComponentCard.ts
import { jsx as jsx4, jsxs as jsxs4 } from "react/jsx-runtime";
import { Button as Button2, usePluginI18n as usePluginI18n4 } from "@hermes/plugin-sdk";

// src/renderer/ui/ComponentProgress.ts
import { jsx as jsx3, jsxs as jsxs3 } from "react/jsx-runtime";
import { usePluginI18n as usePluginI18n3 } from "@hermes/plugin-sdk";

// src/renderer/ui/componentText.ts
function componentReleaseIdentity(release) {
  return `${release.component_id} / ${release.version} / ${release.build_id}`;
}
function componentReleaseTarget(release) {
  return `${release.platform} / ${release.architecture}`;
}
function formatExactBytes(bytes) {
  return new Intl.NumberFormat().format(bytes);
}

// src/renderer/ui/ComponentProgress.ts
function ComponentProgress({ job, progress }) {
  const t = usePluginI18n3("toqraq");
  return jsxs3("div", {
    className: "space-y-1",
    children: [
      jsxs3("div", {
        className: "flex justify-between gap-2 text-[0.6875rem] text-(--ui-text-secondary)",
        children: [
          jsx3("span", {
            role: "status",
            "aria-live": "polite",
            "aria-atomic": true,
            children: t(
              "component.statePhase",
              t(`component.state.${job.state}`),
              t(`component.phase.${job.phase}`)
            )
          }),
          job.total_bytes > 0 && jsx3("span", {
            children: t(
              "component.progressValue",
              formatExactBytes(job.completed_bytes),
              formatExactBytes(job.total_bytes)
            )
          })
        ]
      }),
      jsx3("progress", {
        className: "h-1.5 w-full accent-(--ui-accent)",
        max: 1,
        ...progress === null ? {} : { value: progress },
        "aria-label": t("component.progressLabel")
      }),
      job.error && jsx3("p", {
        className: "text-xs text-destructive",
        role: "alert",
        "aria-atomic": true,
        children: localizePublicError(t, job.error)
      })
    ]
  });
}

// src/renderer/ui/ComponentCard.ts
function ComponentCard({
  release,
  setupAction,
  job,
  requesting,
  onStart,
  onCancel,
  onRetry
}) {
  const t = usePluginI18n4("toqraq");
  const view = deriveComponentCardState(release, job, requesting);
  return jsxs4("article", {
    className: "space-y-2 rounded border border-(--ui-stroke-secondary) bg-(--ui-bg-secondary) p-2.5",
    children: [
      jsxs4("div", {
        className: "flex items-start justify-between gap-3",
        children: [
          jsxs4("div", {
            className: "min-w-0",
            children: [
              jsx4("div", {
                className: "truncate text-xs font-medium text-(--ui-text-primary)",
                children: release.label
              }),
              jsx4("div", {
                className: "truncate text-[0.6875rem] text-(--ui-text-tertiary)",
                children: componentReleaseIdentity(release)
              })
            ]
          }),
          jsx4("span", {
            className: "shrink-0 text-[0.6875rem] text-(--ui-text-secondary)",
            children: t(`component.readiness.${release.readiness}`)
          })
        ]
      }),
      jsxs4("dl", {
        className: "grid grid-cols-[6rem_minmax(0,1fr)] gap-x-2 gap-y-1 text-[0.6875rem]",
        children: [
          jsx4(Detail, {
            label: t("component.detail.target"),
            children: componentReleaseTarget(release)
          }),
          jsx4(Detail, {
            label: t("component.detail.size"),
            children: t(
              "component.sizeValue",
              formatExactBytes(release.package_bytes),
              formatExactBytes(release.installed_bytes)
            )
          }),
          jsx4(Detail, {
            label: t("component.detail.source"),
            children: jsxs4("span", {
              className: "inline-flex min-w-0 flex-wrap gap-x-2",
              children: [
                externalLink(release.source.provenance_url, release.source.publisher),
                externalLink(release.source.package_url, t("component.packageLink"))
              ]
            })
          }),
          jsx4(Detail, {
            label: t("component.detail.license"),
            children: jsxs4("span", {
              className: "inline-flex min-w-0 flex-wrap gap-x-1",
              children: [
                externalLink(
                  release.license.url,
                  `${release.license.name} (${release.license.identifier})`
                ),
                release.license.acceptance_required && t("component.requiredMarker")
              ]
            })
          }),
          jsx4(Detail, {
            label: t("component.detail.authentication"),
            children: release.authentication_required ? t("component.authenticationRequired") : t("component.authenticationNotRequired")
          })
        ]
      }),
      view.job && jsx4(ComponentProgress, { job: view.job, progress: view.progress }),
      release.in_use && release.readiness === "ready" && jsx4("p", {
        className: "text-[0.6875rem] text-(--ui-text-tertiary)",
        children: t("component.removeBlocked")
      }),
      jsx4("div", {
        className: "flex flex-wrap justify-end gap-1.5",
        children: componentActionButtons({
          t,
          release,
          setupAction,
          actions: view.actions,
          actionDisabled: view.actionDisabled,
          onStart,
          onCancel,
          onRetry
        })
      })
    ]
  });
}
function componentActionButtons(input) {
  const buttons = [];
  if (input.actions.canCancel) {
    buttons.push(
      jsx4(Button2, {
        size: "sm",
        variant: "ghost",
        disabled: input.actionDisabled,
        onClick: () => void input.onCancel(),
        children: input.t("component.action.cancel")
      }, "cancel")
    );
  }
  if (input.actions.canRetry) {
    buttons.push(
      jsx4(Button2, {
        size: "sm",
        variant: "default",
        disabled: input.actionDisabled,
        onClick: () => void input.onRetry(),
        children: input.t("component.action.retry")
      }, "retry")
    );
  } else if (input.setupAction === "install" && input.actions.canPrepare) {
    buttons.push(
      jsx4(Button2, {
        size: "sm",
        variant: "default",
        disabled: input.actionDisabled,
        onClick: () => void input.onStart(input.release.release_id, "prepare"),
        children: input.t(componentPrepareActionKey(input.release))
      }, "prepare")
    );
  }
  if (input.actions.canRemove) {
    buttons.push(
      jsx4(Button2, {
        size: "sm",
        variant: "ghost",
        disabled: input.actionDisabled,
        onClick: () => void input.onStart(input.release.release_id, "remove"),
        children: input.t("component.action.remove")
      }, "remove")
    );
  }
  return buttons;
}
function Detail({ label, children }) {
  return jsxs4("div", {
    className: "contents",
    children: [
      jsx4("dt", { className: "text-(--ui-text-tertiary)", children: label }),
      jsx4("dd", { className: "min-w-0 text-(--ui-text-secondary)", children })
    ]
  });
}
function externalLink(url, label) {
  return jsx4("a", {
    href: url,
    target: "_blank",
    rel: "noreferrer noopener",
    className: "min-w-0 truncate text-(--ui-accent) hover:underline",
    title: url,
    children: label
  });
}

// src/renderer/ui/ComponentSetup.ts
function ComponentSetup({ ctx, setup, onTerminal }) {
  const t = usePluginI18n5("toqraq");
  const requiredReleaseIds = setup.engine?.required_component_release_ids ?? [];
  const controller = useComponentSetup(
    ctx,
    true,
    requiredReleaseIds,
    onTerminal
  );
  const releases = resolveSetupComponentPlan(setup, controller.components);
  const componentsError = visibleApiError(t, controller.componentsError);
  const jobReadError = visibleApiError(t, controller.jobError);
  const requestError = controller.requestError ? localizeApiError(t, controller.requestError) : null;
  if (controller.componentsPending) {
    return jsx5(ComponentMessage, { children: t("component.loading") });
  }
  if (componentsError) {
    return jsx5(RefreshableComponentError, {
      message: componentsError,
      refreshing: controller.componentsRefreshing,
      onRetry: controller.refreshComponents
    });
  }
  if (!releases) {
    return jsx5(RefreshableComponentError, {
      message: t("component.planUnavailable"),
      refreshing: controller.componentsRefreshing,
      onRetry: controller.refreshComponents
    });
  }
  return jsxs5("section", {
    className: "space-y-2 pt-1",
    "aria-label": t("component.heading"),
    children: [
      jsx5("h3", {
        className: "text-xs font-medium text-(--ui-text-primary)",
        children: setup.action === "install" ? t("component.headingRequired") : t("component.headingReady")
      }),
      releases.map(
        (release) => jsx5(
          ComponentCard,
          {
            release,
            setupAction: setup.action,
            job: controller.job,
            requesting: controller.requesting,
            onStart: controller.start,
            onCancel: controller.cancel,
            onRetry: controller.retry
          },
          release.release_id
        )
      ),
      (requestError || jobReadError) && jsx5("p", {
        className: "text-xs text-destructive",
        role: "alert",
        "aria-atomic": true,
        children: requestError ?? jobReadError
      })
    ]
  });
}
function RefreshableComponentError({
  message,
  refreshing,
  onRetry
}) {
  const t = usePluginI18n5("toqraq");
  return jsxs5("div", {
    className: "space-y-2 pt-1",
    children: [
      jsx5(ComponentMessage, { tone: "error", children: message }),
      jsx5(Button3, {
        size: "sm",
        variant: "default",
        disabled: refreshing,
        onClick: () => void onRetry(),
        children: refreshing ? t("component.action.refreshing") : t("component.action.retry")
      })
    ]
  });
}
function ComponentMessage({ children, tone = "normal" }) {
  return jsx5("p", {
    className: `pt-1 text-xs ${tone === "error" ? "text-destructive" : "text-(--ui-text-tertiary)"}`,
    ...tone === "error" ? { role: "alert", "aria-atomic": true } : { role: "status", "aria-live": "polite", "aria-atomic": true },
    children
  });
}
function visibleApiError(t, error) {
  if (!error) return null;
  return error instanceof ToqraqApiError ? localizeApiError(t, error) : t("failure.transportUnavailable");
}

// src/renderer/ui/SetupGuide.ts
function SetupGuide({
  ctx,
  setup,
  view,
  retrying,
  busy,
  onStart,
  onRetry,
  onComponentTerminal
}) {
  const t = usePluginI18n6("toqraq");
  return jsxs6("div", {
    className: "flex w-full max-w-md flex-col gap-3 px-6 text-left",
    children: [
      jsxs6("div", {
        role: "status",
        "aria-live": "polite",
        "aria-atomic": true,
        className: "space-y-1",
        children: [
          jsx6("h2", {
            className: "text-sm font-medium text-(--ui-text-primary)",
            children: t(`setup.headline.${view.headline}`)
          }),
          jsx6("div", {
            className: "text-xs text-(--ui-text-tertiary)",
            children: t(`setup.description.${view.headline}`)
          })
        ]
      }),
      view.showReadiness && jsxs6("dl", {
        className: "grid gap-1.5",
        children: [
          jsx6(SetupRow, {
            label: t("setup.item.session"),
            value: t(`setup.state.session.${view.session}`),
            ready: view.session === "ready"
          }),
          jsx6(SetupRow, {
            label: t("setup.item.host"),
            value: t(`setup.state.host.${view.host}`),
            ready: view.host === "ready"
          }),
          jsx6(SetupRow, {
            label: t("setup.item.project"),
            value: t(`setup.state.project.${view.project}`),
            ready: view.project === "ready"
          }),
          setup?.engine && jsx6(SetupRow, {
            label: t("setup.item.engine"),
            value: setup.engine.id,
            ready: true
          }),
          jsx6(SetupRow, {
            label: t("setup.item.runtime"),
            value: t(`setup.state.runtime.${view.runtime}`),
            ready: view.runtime === "ready"
          })
        ]
      }),
      view.showComponentPlan && setup?.engine && setup.engine.required_component_release_ids.length > 0 && jsx6(ComponentSetup, {
        ctx,
        setup,
        onTerminal: onComponentTerminal
      }),
      view.startable && jsxs6(Button4, {
        size: "sm",
        variant: "default",
        disabled: busy,
        onClick: onStart,
        className: "self-start",
        children: [
          jsx6(icons2.Play, { size: 13 }),
          jsx6("span", {
            children: busy ? t("setup.action.starting") : t("setup.action.start")
          })
        ]
      }),
      view.retryable && jsx6(Button4, {
        size: "sm",
        variant: "default",
        disabled: retrying,
        onClick: onRetry,
        className: "self-start",
        children: retrying ? t("setup.action.retrying") : t("setup.action.retry")
      })
    ]
  });
}
function SetupRow({ label, value, ready }) {
  return jsxs6("div", {
    className: "flex items-center gap-2 rounded px-2 py-1.5 bg-(--ui-bg-secondary)",
    children: [
      jsx6("span", {
        "aria-hidden": true,
        className: `size-1.5 rounded-full ${ready ? "bg-(--ui-accent)" : "bg-(--ui-text-tertiary)"}`
      }),
      jsx6("dt", {
        className: "w-20 text-(--ui-text-secondary)",
        children: label
      }),
      jsx6("dd", {
        className: "min-w-0 flex-1 truncate text-(--ui-text-primary)",
        children: value
      })
    ]
  });
}

// src/renderer/ui/ViewportSurface.ts
function ViewportSurface({
  ctx,
  areaRef,
  busy,
  setup,
  setupView,
  setupRetrying,
  previewView,
  previewError,
  onStart,
  onRetrySetup,
  onComponentTerminal
}) {
  const t = usePluginI18n7("toqraq");
  let child;
  if (previewView === "setup") {
    child = jsx7(SetupGuide, {
      ctx,
      setup,
      view: setupView,
      retrying: setupRetrying,
      busy,
      onStart,
      onRetry: onRetrySetup,
      onComponentTerminal
    });
  } else {
    child = previewStatus(t, previewView, previewError);
  }
  return jsx7("div", {
    ref: areaRef,
    role: "region",
    "aria-label": t("pane.previewLabel"),
    className: "relative flex-1 min-h-[10rem] flex items-center justify-center overflow-hidden text-xs text-(--ui-text-tertiary)",
    children: child
  });
}
function previewStatus(t, view, error) {
  const failed = view === "failed";
  return jsxs7("div", {
    ...failed ? { role: "alert", "aria-atomic": true } : { role: "status", "aria-live": "polite", "aria-atomic": true },
    className: "space-y-1 text-center",
    children: [
      jsx7("p", { children: previewMessage(t, view) }),
      failed && error && jsx7("p", {
        className: "text-destructive",
        children: localizePublicError(t, error)
      })
    ]
  });
}
function previewMessage(t, view) {
  if (view === "failed") return t("pane.previewFailed");
  if (view === "retrying") return t("pane.nativeRetrying");
  if (view === "unavailable") return t("pane.previewUnavailable");
  if (view === "attached") return t("pane.nativeActive");
  return t("pane.nativeConnecting");
}

// src/renderer/ui/ViewportPane.ts
function ViewportPane({ ctx, sessionStore }) {
  const t = usePluginI18n8("toqraq");
  const notifyDisplayError = useCallback4(
    (error) => host3.notifyError(error, t("notify.displayFailed")),
    [t]
  );
  const game = useValue3(sessionStore.gameState);
  const selectedSession = game.session?.id === game.readiness.sessionId ? game.session : null;
  const runtimeState = projectRuntimeState(selectedSession);
  const sessionOwned = runtimeState === "running" || runtimeState === "paused" || runtimeState === "stopping";
  const busy = useValue3(sessionStore.busyState);
  const setup = useViewportSetup({
    ctx,
    sessionId: game.readiness.sessionId,
    sessionStatus: game.readiness.status,
    sessionOwned
  });
  const lifecycle = useGameLifecycle({
    ctx,
    t,
    store: sessionStore,
    sessionId: game.readiness.sessionId,
    sessionStatus: game.readiness.status,
    selectedSession,
    workspaceDir: setup.workspaceDir,
    setupView: setup.view,
    invalidateSetup: setup.invalidate
  });
  const areaRef = useRef3(null);
  const previewView = useNativeDisplay({
    ctx,
    session: selectedSession,
    elementRef: areaRef,
    onError: notifyDisplayError
  });
  return jsxs8("div", {
    className: "flex h-full flex-col",
    children: [
      sessionOwned && selectedSession && jsx8(Toolbar, {
        projectDir: selectedSession.project_dir,
        runtime: selectedSession.runtime,
        processState: runtimeState,
        canPause: lifecycle.canPause,
        paused: selectedSession.process_state === "paused",
        busy,
        onStop: lifecycle.stop,
        onTogglePause: lifecycle.togglePause
      }),
      jsx8(ViewportSurface, {
        ctx,
        areaRef,
        busy,
        setup: setup.setup,
        setupView: setup.view,
        setupRetrying: setup.retrying,
        previewView,
        previewError: selectedSession?.preview.error ?? null,
        onStart: lifecycle.start,
        onRetrySetup: setup.retry,
        onComponentTerminal: setup.componentTerminal
      })
    ]
  });
}

// src/renderer/contributions/main.ts
function registerContributions(ctx) {
  const sessionStore = new RendererSessionStore(atom);
  ctx.own(() => sessionStore.dispose());
  ctx.own(
    startRendererSessionSync({
      activeSessionId: host4.state.activeSessionId,
      gateway: host4.state.gateway,
      store: sessionStore,
      readHermesStatus: (sessionId) => queryClient2.fetchQuery({
        queryKey: hermesSessionQueryKey(sessionId),
        queryFn: () => host4.request("session.status", { session_id: sessionId }),
        retry: false,
        staleTime: 0
      }),
      cancelHermesStatus: (sessionId) => {
        void queryClient2.cancelQueries({
          queryKey: hermesSessionQueryKey(sessionId),
          exact: true
        });
      },
      readSession: (sessionId) => getSession(ctx, sessionId),
      openEvents: (sessionId, onEvent, onError) => openEvents(ctx, sessionId, onEvent, onError),
      scheduleRetry: (retry) => {
        const timer = globalThis.setTimeout(
          retry,
          HERMES_SESSION_ERROR_REFRESH_INTERVAL_MS
        );
        return () => globalThis.clearTimeout(timer);
      },
      onLoadError: (error) => {
        host4.notifyError(
          normalizeThrown(ctx, error),
          ctx.i18n.t("notify.loadFailed")
        );
      },
      onEventError: (error) => {
        host4.notifyError(
          normalizeThrown(ctx, error),
          ctx.i18n.t("notify.displayFailed")
        );
      },
      onEnded: (session) => {
        if (session.process_state === "crashed") {
          host4.notify({
            kind: "warning",
            message: ctx.i18n.t("notify.sessionCrashed", session.exit_code)
          });
          return;
        }
        host4.notify({ kind: "info", message: ctx.i18n.t("notify.sessionEnded") });
      }
    })
  );
  ctx.own(() => {
    void queryClient2.cancelQueries({ queryKey: workspaceSetupQueryRoot() });
  });
  ctx.own(
    startWorkspaceContextSync({
      activeSessionId: host4.state.activeSessionId,
      cwd: host4.state.cwd,
      gateway: host4.state.gateway,
      fetch: (ownerId, workspaceDir) => queryClient2.fetchQuery({
        queryKey: workspaceSetupQueryKey(ownerId, workspaceDir),
        queryFn: () => syncWorkspaceContext(
          ctx,
          ownerId,
          workspaceDir ? { projectDir: workspaceDir } : {}
        ),
        retry: SETUP_QUERY_RETRY_COUNT,
        retryDelay: SETUP_QUERY_RETRY_DELAY_MS,
        staleTime: 0
      })
    })
  );
  return ctx.registerMany([
    {
      id: "pane",
      area: PANES_AREA,
      title: ctx.i18n.t("pane.title"),
      data: {
        collapsible: true,
        placement: "bottom",
        dock: { pane: "workspace", pos: "bottom" },
        height: "32vh",
        minHeight: "10rem"
      },
      render: () => jsx9(ViewportPane, { ctx, sessionStore })
    },
    {
      id: "status",
      area: STATUSBAR_AREAS.right,
      order: 140,
      render: () => jsx9(StatusChip, { sessionStore })
    },
    {
      id: "palette.stop",
      area: PALETTE_AREA,
      data: {
        id: "toqraq.stop",
        label: ctx.i18n.t("palette.stop"),
        keywords: ["game", "engine", "toqraq"],
        run: async () => {
          const sessionId = sessionStore.currentSession()?.id;
          if (!sessionId) return;
          try {
            await stopGame(ctx, sessionStore, sessionId);
          } catch (error) {
            if (sessionStore.active && sessionStore.currentGame().readiness.sessionId === sessionId) {
              host4.notifyError(
                normalizeThrown(ctx, error),
                ctx.i18n.t("notify.stopFailed")
              );
            }
          }
        }
      }
    }
  ]);
}

// src/renderer/index.ts
var plugin = {
  id: "toqraq",
  name: "Toqraq",
  register(ctx) {
    ctx.i18n.register(bundles);
    return registerContributions(ctx);
  }
};
var index_default = plugin;
export {
  index_default as default
};
