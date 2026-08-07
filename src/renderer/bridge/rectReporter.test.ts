import assert from 'node:assert/strict'
import test from 'node:test'
import type { ScreenRect } from '../lib/viewportMath.js'
import { RectReporter } from './rectReporter.js'

test('pane measurements mark drag resize active and then settled without polling sleeps', () => {
  const previous = new Map(
    [
      'window',
      'document',
      'performance',
      'ResizeObserver',
      'requestAnimationFrame',
      'cancelAnimationFrame',
    ].map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)]),
  )
  let now = 100
  let frameId = 0
  let timerId = 0
  let resize = () => {}
  const frames = new Map<number, FrameRequestCallback>()
  const timeouts = new Map<number, () => void>()
  const cancelledTimeouts = new Set<number>()
  let rect = { left: 10, top: 20, width: 800, height: 600 }
  const reports: Array<{ readonly value: ScreenRect; readonly settled: boolean }> = []

  replaceGlobal('window', {
    devicePixelRatio: 1,
    outerWidth: 1000,
    innerWidth: 1000,
    outerHeight: 800,
    innerHeight: 800,
    screenX: 0,
    screenY: 0,
    setInterval: () => 1,
    clearInterval: () => {},
    setTimeout(callback: () => void) {
      timerId += 1
      timeouts.set(timerId, callback)
      return timerId
    },
    clearTimeout(id: number) {
      cancelledTimeouts.add(id)
    },
  })
  replaceGlobal('document', { visibilityState: 'visible' })
  replaceGlobal('performance', { now: () => now })
  replaceGlobal('ResizeObserver', class {
    constructor(callback: () => void) {
      resize = callback
    }
    observe() {}
    disconnect() {}
  })
  replaceGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    frameId += 1
    frames.set(frameId, callback)
    return frameId
  })
  replaceGlobal('cancelAnimationFrame', (id: number) => {
    frames.delete(id)
  })

  try {
    const reporter = new RectReporter(
      { getBoundingClientRect: () => rect },
      (value, settled) => reports.push({ value, settled }),
    )
    reporter.start()
    const initialFrame = frames.get(1)
    assert.ok(initialFrame)
    initialFrame(now)

    rect = { ...rect, width: 400, height: 800 }
    now = 200
    resize()
    const resizedFrame = frames.get(2)
    assert.ok(resizedFrame)
    resizedFrame(now)
    const settleId = timerId
    const settle = timeouts.get(settleId)
    assert.ok(settle)
    if (!cancelledTimeouts.has(settleId)) settle()

    assert.deepEqual(reports.map((report) => report.settled), [true, false, true])
    assert.deepEqual(reports.at(-1)?.value, {
      x: 10,
      y: 20,
      width: 400,
      height: 800,
    })
    reporter.stop()
  } finally {
    for (const [key, descriptor] of previous) restoreGlobal(key, descriptor)
  }
})

function replaceGlobal(key: string, value: unknown): void {
  Object.defineProperty(globalThis, key, { configurable: true, writable: true, value })
}

function restoreGlobal(key: string, descriptor: PropertyDescriptor | undefined): void {
  if (descriptor) {
    Object.defineProperty(globalThis, key, descriptor)
  } else {
    Reflect.deleteProperty(globalThis, key)
  }
}
