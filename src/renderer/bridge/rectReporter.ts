/** Coalesced physical pane measurements with explicit resize-settled signals. */

import { elementScreenRect, isUsableScreenRect } from '../lib/viewportMath.js'
import type { MeasurableElement, ScreenRect } from '../lib/viewportMath.js'

const MIN_REPORT_INTERVAL_MS = 33
const RESIZE_SETTLE_DELAY_MS = 140
const POSITION_PROBE_INTERVAL_MS = 500

export class RectReporter {
  private readonly _element: MeasurableElement
  private readonly _onRect: (rect: ScreenRect, settled: boolean) => void
  private _observer: ResizeObserver | null = null
  private _frame = 0
  private _probeTimer = 0
  private _settleTimer = 0
  private _lastSentAt = 0
  private _lastKey = ''
  private _lastRect: ScreenRect | null = null
  private _hasReported = false
  private _forceSettled = false

  constructor(
    element: MeasurableElement,
    onRect: (rect: ScreenRect, settled: boolean) => void,
  ) {
    this._element = element
    this._onRect = onRect
  }

  /** Start observing and report the initial pane as already settled. */
  start(): void {
    this.stop()
    this._lastSentAt = 0
    this._lastKey = ''
    this._lastRect = null
    this._hasReported = false
    this._forceSettled = false
    this._observer = new ResizeObserver(() => this._schedule())
    // Production panes are DOM elements; the narrow measurement port keeps tests honest.
    this._observer.observe(this._element as Element)
    this._probeTimer = window.setInterval(() => this._schedule(), POSITION_PROBE_INTERVAL_MS)
    this._schedule()
  }

  /** Stop observing and cancel every pending measurement or settle signal. */
  stop(): void {
    this._observer?.disconnect()
    this._observer = null
    if (this._frame) cancelAnimationFrame(this._frame)
    if (this._probeTimer) window.clearInterval(this._probeTimer)
    if (this._settleTimer) window.clearTimeout(this._settleTimer)
    this._frame = 0
    this._probeTimer = 0
    this._settleTimer = 0
  }

  /** Force a fresh settled measurement after visibility or layout restoration. */
  refresh(): void {
    this._lastKey = ''
    this._forceSettled = true
    this._schedule()
  }

  private _schedule(): void {
    if (this._frame) return
    this._frame = requestAnimationFrame(() => {
      this._frame = 0
      const now = performance.now()
      if (now - this._lastSentAt < MIN_REPORT_INTERVAL_MS) {
        this._schedule()
        return
      }
      if (document.visibilityState !== 'visible') return
      const rect = elementScreenRect(this._element)
      if (rect.width < 1 || rect.height < 1 || !isUsableScreenRect(rect)) return
      const key = `${rect.x},${rect.y},${rect.width},${rect.height}`
      if (key === this._lastKey) return
      this._lastKey = key
      this._lastRect = rect
      this._lastSentAt = now
      if (!this._hasReported || this._forceSettled) {
        this._hasReported = true
        this._forceSettled = false
        if (this._settleTimer) window.clearTimeout(this._settleTimer)
        this._settleTimer = 0
        this._onRect(rect, true)
        return
      }
      this._onRect(rect, false)
      this._scheduleSettled()
    })
  }

  private _scheduleSettled(): void {
    if (this._settleTimer) window.clearTimeout(this._settleTimer)
    this._settleTimer = window.setTimeout(() => {
      this._settleTimer = 0
      if (document.visibilityState === 'visible' && this._lastRect !== null) {
        this._onRect(this._lastRect, true)
      }
    }, RESIZE_SETTLE_DELAY_MS)
  }
}
