/** Narrow runtime decoders for successful setup results. */

import type {
  EngineChoiceResult,
  EngineSetupResult,
  ProjectSetupResult,
  SetupResult,
} from '../contracts/generated.js'
import {
  EngineChoiceResultRules,
  EngineSetupResultRules,
  HostSetupResultRules,
  ProjectSetupResultRules,
  SelectedRuntimeResultRules,
  SetupResultRules,
} from '../contracts/runtimeRules.js'
import {
  arrayValue,
  booleanValue,
  decodeSize,
  enumValue,
  integerValue,
  invalid,
  nullableStringValue,
  recordValue,
  stringArrayValue,
  stringValue,
} from './safeData.js'

export function decodeSetup(value: unknown): SetupResult {
  const source = recordValue(value, SetupResultRules, 'setup result')
  const host = recordValue(source.host, HostSetupResultRules, 'setup host')
  const project = recordValue(source.project, ProjectSetupResultRules, 'setup project')
  const action = enumValue(source.action, SetupResultRules.action, 'setup action')
  const projectState = enumValue(project.state, ProjectSetupResultRules.state, 'project state')
  const probedEngineIds = stringArrayValue(
    project.probed_engine_ids,
    ProjectSetupResultRules.probed_engine_ids,
    'probed engine id',
  )
  uniqueStrings(probedEngineIds, 'probed engine ids')
  const engineChoices = Object.freeze(
    arrayValue(source.engine_choices, SetupResultRules.engine_choices, 'setup engine choices').map(
      decodeSetupEngineChoice,
    ),
  )
  uniqueStrings(engineChoices.map((choice) => choice.id), 'setup engine choices')
  const engine = source.engine === null ? null : decodeSetupEngine(source.engine)
  const result: SetupResult = Object.freeze({
    host: Object.freeze({
      platform: stringValue(host.platform, HostSetupResultRules.platform, 'platform'),
      native_display: booleanValue(host.native_display, 'native display'),
    }),
    engine,
    project: Object.freeze({
      path: nullableStringValue(project.path, ProjectSetupResultRules.path, 'project path'),
      state: projectState,
      viewport_size: project.viewport_size === null ? null : decodeSize(project.viewport_size),
      probed_engine_ids: probedEngineIds,
    }),
    engine_choices: engineChoices,
    action,
  })
  validateSetupResult(result)
  return result
}

export function decodeOptionalSetup(value: unknown): SetupResult | null {
  return value === null ? null : decodeSetup(value)
}

function decodeSetupEngine(value: unknown): EngineSetupResult {
  const engine = recordValue(value, EngineSetupResultRules, 'setup engine')
  const availableVersions = stringArrayValue(
    engine.available_versions,
    EngineSetupResultRules.available_versions,
    'runtime version',
  )
  uniqueStrings(availableVersions, 'runtime versions')
  const releaseIds = stringArrayValue(
    engine.required_component_release_ids,
    EngineSetupResultRules.required_component_release_ids,
    'component release id',
  )
  uniqueStrings(releaseIds, 'component release ids')
  const runtime = engine.runtime === null
    ? null
    : Object.freeze({
        version: stringValue(
          recordValue(engine.runtime, SelectedRuntimeResultRules, 'selected runtime').version,
          SelectedRuntimeResultRules.version,
          'runtime version',
        ),
      })
  const installRequired = booleanValue(
    engine.runtime_install_required,
    'runtime install requirement',
  )
  if (runtime === null && releaseIds.length > 0) invalid('unselected runtime components')
  if (runtime !== null && releaseIds.length === 0) invalid('selected runtime components')
  if (installRequired && runtime === null) invalid('runtime install requirement')
  if (runtime !== null && availableVersions.length > 0) invalid('selected runtime versions')
  return Object.freeze({
    id: stringValue(engine.id, EngineSetupResultRules.id, 'engine id'),
    runtime,
    available_versions: availableVersions,
    required_component_release_ids: releaseIds,
    runtime_install_required: installRequired,
  })
}

function decodeSetupEngineChoice(value: unknown): EngineChoiceResult {
  const choice = recordValue(value, EngineChoiceResultRules, 'setup engine choice')
  return Object.freeze({
    id: stringValue(choice.id, EngineChoiceResultRules.id, 'engine id'),
    declared_version: nullableStringValue(
      choice.declared_version,
      EngineChoiceResultRules.declared_version,
      'engine version',
    ),
    confidence: integerValue(
      choice.confidence,
      EngineChoiceResultRules.confidence,
      'engine confidence',
    ),
  })
}

function uniqueStrings(values: readonly string[], name: string): void {
  if (new Set(values).size !== values.length) invalid(name)
}

function validateSetupResult(result: SetupResult): void {
  const action = result.action
  const project = result.project
  const engine = result.engine
  const choices = result.engine_choices
  validateProjectProbeEvidence(project)
  if (action === 'engine_unavailable') {
    if (engine !== null || choices.length !== 0 || project.state !== 'unchecked') {
      invalid('engine unavailable setup state')
    }
    return
  }
  if (action === 'select_project') {
    if (
      engine !== null ||
      choices.length !== 0 ||
      !new Set(['missing', 'invalid', 'not_detected']).has(project.state)
    ) {
      invalid('project selection setup state')
    }
    return
  }
  if (action === 'select_engine') {
    if (engine !== null || choices.length < 2 || project.state !== 'ambiguous') {
      invalid('engine selection setup state')
    }
    if (!sameStrings(choices.map((choice) => choice.id), project.probed_engine_ids)) {
      invalid('engine choices and project probes')
    }
    return
  }
  if (engine === null || choices.length !== 0 || project.state !== 'ready') {
    invalid('runtime setup state')
  }
  const selected = engine
  if (!sameStrings(project.probed_engine_ids, [selected.id])) {
    invalid('selected engine and project probe')
  }
  if (action === 'runtime_unavailable' || action === 'unsupported_host') {
    if (
      selected.runtime !== null ||
      selected.available_versions.length !== 0 ||
      selected.required_component_release_ids.length !== 0 ||
      selected.runtime_install_required
    ) {
      invalid('runtime unavailable setup state')
    }
    return
  }
  if (action === 'select_version') {
    if (selected.runtime !== null || selected.available_versions.length === 0) {
      invalid('version selection setup state')
    }
    return
  }
  if (action === 'install' || action === 'start') {
    if (
      selected.runtime === null ||
      selected.runtime_install_required !== (action === 'install')
    ) {
      invalid('launch setup state')
    }
    return
  }
  invalid('setup action')
}

function validateProjectProbeEvidence(project: ProjectSetupResult): void {
  const count = project.probed_engine_ids.length
  if (project.state === 'missing' && project.path !== null) {
    invalid('missing project path')
  }
  if (project.state !== 'missing' && project.state !== 'unchecked' && project.path === null) {
    invalid('checked project path')
  }
  if (project.state !== 'ready' && project.viewport_size !== null) {
    invalid('project viewport state')
  }
  if (
    (project.state === 'unchecked' ||
      project.state === 'missing' ||
      project.state === 'invalid') &&
    count !== 0
  ) {
    invalid('unprobed project engine evidence')
  }
  if (project.state === 'not_detected' && count < 1) {
    invalid('undetected project engine evidence')
  }
  if (project.state === 'ambiguous' && count < 2) {
    invalid('ambiguous project engine evidence')
  }
  if (project.state === 'ready' && count !== 1) {
    invalid('ready project engine evidence')
  }
}

function sameStrings(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index])
}
