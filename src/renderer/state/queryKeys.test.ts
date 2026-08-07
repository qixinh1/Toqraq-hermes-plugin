import assert from 'node:assert/strict'
import test from 'node:test'
import {
  activeComponentJobsQueryKey,
  componentCatalogQueryKey,
  componentJobQueryKey,
  hermesSessionQueryKey,
  workspaceSetupQueryKey,
  workspaceSetupQueryRoot,
} from './queryKeys.js'

test('fixed query partitions expose stable frozen tuple identities', () => {
  const components = componentCatalogQueryKey()
  const setup = workspaceSetupQueryRoot()

  assert.deepEqual(components, ['toqraq', 'components'])
  assert.deepEqual(setup, ['toqraq', 'setup'])
  assert.equal(componentCatalogQueryKey(), components)
  assert.equal(workspaceSetupQueryRoot(), setup)
  for (const key of [components, setup]) assert.ok(Object.isFrozen(key))
})

test('variable query identities retain one documented position per owner', () => {
  const hermesSession = hermesSessionQueryKey('task-1')
  const activeJobs = activeComponentJobsQueryKey('release-a:release-b')
  const componentJob = componentJobQueryKey('operation-1')
  const workspace = workspaceSetupQueryKey('task-1', 'D:/game')

  assert.deepEqual(hermesSession, ['toqraq', 'hermes-session', 'task-1'])
  assert.equal(hermesSession[2], 'task-1')
  assert.deepEqual(activeJobs, [
    'toqraq',
    'component-jobs',
    'active',
    'release-a:release-b',
  ])
  assert.equal(activeJobs[3], 'release-a:release-b')
  assert.deepEqual(componentJob, ['toqraq', 'component-job', 'operation-1'])
  assert.equal(componentJob[2], 'operation-1')
  assert.deepEqual(workspace, ['toqraq', 'setup', 'task-1', 'D:/game'])
  assert.equal(workspace[2], 'task-1')
  assert.equal(workspace[3], 'D:/game')
  for (const key of [hermesSession, activeJobs, componentJob, workspace]) {
    assert.ok(Object.isFrozen(key))
  }
})

test('query partitions cannot collide and unresolved owners remain explicit', () => {
  const keys = [
    hermesSessionQueryKey(null),
    componentCatalogQueryKey(),
    activeComponentJobsQueryKey(''),
    componentJobQueryKey(null),
    workspaceSetupQueryKey(null, ''),
  ]
  assert.equal(new Set(keys.map((key) => JSON.stringify(key))).size, keys.length)
  assert.deepEqual(hermesSessionQueryKey(null), ['toqraq', 'hermes-session', null])
  assert.deepEqual(componentJobQueryKey(null), ['toqraq', 'component-job', null])

  const root = workspaceSetupQueryRoot()
  const workspace = workspaceSetupQueryKey('task-2', 'D:/next')
  assert.deepEqual(workspace.slice(0, root.length), root)
})
