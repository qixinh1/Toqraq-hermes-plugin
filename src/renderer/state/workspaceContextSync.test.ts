import assert from 'node:assert/strict'
import test from 'node:test'

import type { ReadableValue } from './readableValue.js'
import { startWorkspaceContextSync } from './workspaceContextSync.js'

interface MutableReadable<Value> extends ReadableValue<Value> {
  set(value: Value): void
}

function readable<Value>(initial: Value): MutableReadable<Value> {
  let value = initial
  const listeners = new Set<(value: Value) => void>()
  return {
    get: () => value,
    subscribe(listener) {
      listeners.add(listener)
      listener(value)
      return () => {
        listeners.delete(listener)
      }
    },
    set(next) {
      value = next
      for (const listener of listeners) listener(value)
    },
  }
}

interface Deferred<Value> {
  promise: Promise<Value>
  resolve(value: Value): void
  reject(reason: Error): void
}

function deferred<Value>(): Deferred<Value> {
  let resolve = (_value: Value): void => {
    throw new Error('deferred promise was not initialized')
  }
  let reject = (_reason: Error): void => {
    throw new Error('deferred promise was not initialized')
  }
  const promise = new Promise<Value>((onResolve, onReject) => {
    resolve = onResolve
    reject = onReject
  })
  return { promise, resolve, reject }
}

test('sync follows public task, workspace, and gateway state without a pane', () => {
  const activeSessionId = readable<string | null>(null)
  const cwd = readable('D:/game')
  const gateway = readable('open')
  const calls: Array<[string, string]> = []
  const dispose = startWorkspaceContextSync({
    activeSessionId,
    cwd,
    gateway,
    fetch: async (ownerId, workspaceDir) => {
      calls.push([ownerId, workspaceDir])
    },
  })

  activeSessionId.set('task-1')
  cwd.set('relative/transient')
  gateway.set('connecting')
  cwd.set('D:/next')
  gateway.set('open')
  activeSessionId.set('task-2')

  assert.deepEqual(calls, [
    ['task-1', 'D:/game'],
    ['task-1', ''],
    ['task-1', 'D:/next'],
    ['task-2', 'D:/next'],
  ])
  dispose()
})

test('late failure cannot reopen the current workspace request', async () => {
  const activeSessionId = readable<string | null>('task-1')
  const cwd = readable('D:/old')
  const gateway = readable('open')
  const oldRequest = deferred<void>()
  const calls: Array<[string, string]> = []
  const dispose = startWorkspaceContextSync({
    activeSessionId,
    cwd,
    gateway,
    fetch: (ownerId, workspaceDir) => {
      calls.push([ownerId, workspaceDir])
      return workspaceDir === 'D:/old' ? oldRequest.promise : Promise.resolve()
    },
  })

  cwd.set('D:/new')
  oldRequest.reject(new Error('late failure'))
  await Promise.resolve()
  cwd.set('D:/new')

  assert.deepEqual(calls, [
    ['task-1', 'D:/old'],
    ['task-1', 'D:/new'],
  ])
  dispose()
})

test('dispose is idempotent and prevents later synchronization', () => {
  const activeSessionId = readable<string | null>('task-1')
  const cwd = readable('D:/game')
  const gateway = readable('open')
  const calls: Array<[string, string]> = []
  const dispose = startWorkspaceContextSync({
    activeSessionId,
    cwd,
    gateway,
    fetch: async (ownerId, workspaceDir) => {
      calls.push([ownerId, workspaceDir])
    },
  })

  dispose()
  dispose()
  cwd.set('D:/other')
  activeSessionId.set('task-2')

  assert.deepEqual(calls, [['task-1', 'D:/game']])
})
