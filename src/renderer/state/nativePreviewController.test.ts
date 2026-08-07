import assert from 'node:assert/strict'
import test from 'node:test'
import type { ScreenRect } from '../lib/viewportMath.js'
import {
  INITIAL_PREVIEW_RETRY_DELAY_MS,
  NativePreviewController,
} from './nativePreviewController.js'
import type {
  NativePreviewApi,
  NativePreviewStatus,
} from './nativePreviewController.js'

type PreviewCall =
  | Readonly<{ operation: 'attach'; value: { paneRect: ScreenRect } }>
  | Readonly<{ operation: 'follow'; value: ScreenRect }>
  | Readonly<{ operation: 'visible'; value: boolean }>
  | Readonly<{ operation: 'detach' }>

interface Retry {
  callback(): void
  delayMs: number
  cancelled: boolean
}

interface Deferred {
  promise: Promise<void>
  resolve(): void
}

function deferred(): Deferred {
  let resolve = (): void => {
    throw new Error('deferred promise was not initialized')
  }
  const promise = new Promise<void>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

function harness(overrides: Partial<NativePreviewApi> = {}) {
  const calls: PreviewCall[] = []
  const statuses: NativePreviewStatus[] = []
  const errors: unknown[] = []
  const retries: Retry[] = []
  const api: NativePreviewApi = {
    async attach(payload) {
      calls.push({ operation: 'attach', value: payload })
      return overrides.attach
        ? overrides.attach(payload)
        : { id: 'session-1', run_revision: 2 }
    },
    async follow(rect) {
      calls.push({ operation: 'follow', value: rect })
      return overrides.follow ? overrides.follow(rect) : { ok: true }
    },
    async setVisible(visible) {
      calls.push({ operation: 'visible', value: visible })
      return overrides.setVisible ? overrides.setVisible(visible) : { ok: true }
    },
    async detach() {
      calls.push({ operation: 'detach' })
      return overrides.detach ? overrides.detach() : { ok: true }
    },
  }
  const controller = new NativePreviewController({
    sessionId: 'session-1',
    runRevision: 2,
    documentVisible: true,
    api,
    scheduleRetry(callback, delayMs) {
      const handle = { callback, delayMs, cancelled: false }
      retries.push(handle)
      return handle
    },
    cancelRetry(handle) {
      handle.cancelled = true
    },
    onStatus: (status) => statuses.push(status),
    onError: (error) => errors.push(error),
  })
  return { controller, calls, statuses, errors, retries }
}

test('initial attach reports the physical pane unchanged and explicitly shows it', async () => {
  const { controller, calls, statuses } = harness()

  await controller.updatePane({ x: 100, y: 50, width: 800, height: 600 }, true)

  assert.deepEqual(calls, [
    {
      operation: 'attach',
      value: {
        paneRect: { x: 100, y: 50, width: 800, height: 600 },
      },
    },
    { operation: 'visible', value: true },
  ])
  assert.deepEqual(statuses, ['connecting', 'attached'])
  await controller.close()
})

test('drag resize hides before following and corrects late geometry before showing', async () => {
  const firstFollow = deferred()
  const followStarted = deferred()
  let followCount = 0
  const owner = harness({
    async follow() {
      followCount += 1
      if (followCount === 1) {
        followStarted.resolve()
        await firstFollow.promise
      }
      return { ok: true }
    },
  })
  await owner.controller.updatePane({ x: 0, y: 0, width: 800, height: 600 }, true)
  owner.calls.length = 0

  const resizing = owner.controller.updatePane(
    { x: 0, y: 0, width: 400, height: 800 },
    false,
  )
  await followStarted.promise
  const settled = owner.controller.updatePane(
    { x: 0, y: 0, width: 600, height: 400 },
    true,
  )
  firstFollow.resolve()
  await Promise.all([resizing, settled])

  assert.deepEqual(owner.calls, [
    { operation: 'visible', value: false },
    { operation: 'follow', value: { x: 0, y: 0, width: 400, height: 800 } },
    { operation: 'follow', value: { x: 0, y: 0, width: 600, height: 400 } },
    { operation: 'visible', value: true },
  ])
  await owner.controller.close()
})

test('close waits for a late attach and detaches once', async () => {
  const attachStarted = deferred()
  const releaseAttach = deferred()
  const owner = harness({
    async attach() {
      attachStarted.resolve()
      await releaseAttach.promise
      return { id: 'session-1', run_revision: 2 }
    },
  })

  const attaching = owner.controller.updatePane({ x: 0, y: 0, width: 800, height: 600 }, true)
  await attachStarted.promise
  const closing = owner.controller.close()
  releaseAttach.resolve()
  await Promise.all([attaching, closing, owner.controller.close()])

  assert.deepEqual(owner.calls.map((call) => call.operation), ['attach', 'detach'])
  assert.deepEqual(owner.statuses, ['connecting'])
})

test('an attach response from a replacement run is detached without stale retries', async () => {
  const owner = harness({
    async attach() {
      return { id: 'session-1', run_revision: 3 }
    },
  })

  await owner.controller.updatePane({ x: 0, y: 0, width: 800, height: 600 }, true)

  assert.deepEqual(owner.calls.map((call) => call.operation), ['attach', 'detach'])
  assert.deepEqual(owner.statuses, ['connecting'])
  assert.equal(owner.errors.length, 0)
  assert.equal(owner.retries.length, 0)
  await owner.controller.close()
})

test('a failed effect is reported once and retried through the owned scheduler', async () => {
  const retried = deferred()
  let failures = 1
  const owner = harness({
    async setVisible() {
      if (failures > 0) {
        failures -= 1
        throw new Error('temporary display failure')
      }
      retried.resolve()
      return { ok: true }
    },
  })

  await owner.controller.updatePane({ x: 0, y: 0, width: 800, height: 600 }, true)

  assert.equal(owner.errors.length, 1)
  assert.equal(owner.statuses.at(-1), 'failed')
  const retry = owner.retries[0]
  assert.ok(retry)
  assert.equal(retry.delayMs, INITIAL_PREVIEW_RETRY_DELAY_MS)
  retry.callback()
  await retried.promise
  await owner.controller.setDocumentVisible(true)
  assert.equal(owner.statuses.at(-1), 'attached')
  await owner.controller.close()
})

test('a hostile thrown value is forwarded without invoking its text hooks', async () => {
  let stringCalls = 0
  const hostile = {
    toString() {
      stringCalls += 1
      throw new Error('hostile text hook executed')
    },
  }
  const owner = harness({
    async setVisible() {
      throw hostile
    },
  })

  await owner.controller.updatePane({ x: 0, y: 0, width: 800, height: 600 }, true)

  assert.equal(stringCalls, 0)
  assert.equal(owner.errors[0], hostile)
  await owner.controller.close()
})
