import assert from 'node:assert/strict'
import test from 'node:test'
import { bundles } from './messages.js'

test('every locale exposes the same translation keys', () => {
  const [reference, ...others] = Object.values(bundles).map((bundle) => keys(bundle))
  assert.ok(reference)
  for (const localeKeys of others) assert.deepEqual(localeKeys, reference)
})

test('every locale exposes identical named interpolation parameters', () => {
  const [reference, ...others] = Object.values(bundles).map((bundle) => interpolations(bundle))
  assert.ok(reference)
  for (const localeParameters of others) assert.deepEqual(localeParameters, reference)
  assert.deepEqual(reference['toolbar.processState'], ['state'])
  assert.deepEqual(reference['notify.sessionCrashed'], ['exitCode'])
  assert.deepEqual(reference['component.statePhase'], ['state', 'phase'])
  assert.deepEqual(reference['failure.withTraceId'], ['message', 'traceId'])
  assert.deepEqual(reference['status.value'], ['state'])
})

test('interpolated locale functions follow the positional Hermes SDK contract', () => {
  assert.equal(bundles.en.toolbar.runtimeIdentity('Godot', '4.7.1'), 'Godot 4.7.1')
  assert.equal(bundles.en.toolbar.processState('paused'), 'State: paused')
  assert.equal(bundles.zh.notify.sessionCrashed(23), '游戏已崩溃（退出码 23）')
})

test('locale source contains no Unicode replacement characters', () => {
  for (const bundle of Object.values(bundles)) {
    for (const value of values(bundle)) {
      if (typeof value === 'string') assert.equal(value.includes('\uFFFD'), false)
    }
  }
})

test('plugin recovery stays inside the Hermes lifecycle', () => {
  for (const bundle of Object.values(bundles)) {
    assert.match(bundle.setup.description.hostUnavailable, /Hermes/)
    assert.match(bundle.notify.displayUnavailable, /Hermes/)
    for (const value of values(bundle)) {
      if (typeof value === 'string') assert.doesNotMatch(value, /installer|安装器/i)
    }
  }
})

function keys(value: Readonly<Record<string, unknown>>, prefix = ''): string[] {
  return Object.entries(value)
    .flatMap(([key, item]) => {
      const path = prefix ? `${prefix}.${key}` : key
      return isMessageTree(item) ? keys(item, path) : [path]
    })
    .sort()
}

function values(value: Readonly<Record<string, unknown>>): unknown[] {
  return Object.values(value).flatMap((item) =>
    isMessageTree(item) ? values(item) : [item],
  )
}

function interpolations(
  value: Readonly<Record<string, unknown>>,
  prefix = '',
): Record<string, readonly string[]> {
  return Object.fromEntries(
    Object.entries(value).flatMap(([key, item]) => {
      const path = prefix ? `${prefix}.${key}` : key
      if (isMessageTree(item)) return Object.entries(interpolations(item, path))
      if (typeof item !== 'function') return [[path, []]]
      const parameters: unknown = Reflect.get(item, 'i18nParameters')
      assert.ok(isStringArray(parameters), `${path} must declare interpolation parameters`)
      return [[path, parameters]]
    }),
  )
}

function isMessageTree(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringArray(value: unknown): value is readonly string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}
