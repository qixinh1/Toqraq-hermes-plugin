import assert from 'node:assert/strict'
import test from 'node:test'
import { elementScreenRect, isUsableScreenRect } from './viewportMath.js'

test('Windows minimized sentinel rectangles are not reportable', () => {
  assert.equal(isUsableScreenRect({ x: -30780, y: -30793, width: 800, height: 600 }), false)
  assert.equal(isUsableScreenRect({ x: -1920, y: 0, width: 1920, height: 1080 }), true)
})

test('elementScreenRect converts CSS pixels to physical screen pixels', () => {
  const previous = Object.getOwnPropertyDescriptor(globalThis, 'window')
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: {
      devicePixelRatio: 2,
      outerWidth: 1020,
      innerWidth: 1000,
      outerHeight: 850,
      innerHeight: 800,
      screenX: 100,
      screenY: 50,
    },
  })
  try {
    assert.deepEqual(
      elementScreenRect({
        getBoundingClientRect: () => ({ left: 20, top: 30, width: 200, height: 100 }),
      }),
      { x: 260, y: 240, width: 400, height: 200 },
    )
  } finally {
    if (previous) Object.defineProperty(globalThis, 'window', previous)
    else Reflect.deleteProperty(globalThis, 'window')
  }
})
