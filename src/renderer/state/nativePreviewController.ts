/** Serialized, revision-safe ownership of one native preview attachment. */

import type {
  PreviewOperationResult,
  SessionResult,
} from '../contracts/generated.js'
import type { ScreenRect } from '../lib/viewportMath.js'

type AttachedRun = Pick<SessionResult, 'id' | 'run_revision'>
type PreviewAcknowledgement = Pick<PreviewOperationResult, 'ok'>

export type NativePreviewStatus = 'connecting' | 'attached' | 'failed'

export interface NativePreviewApi {
  attach(payload: { paneRect: ScreenRect }): Promise<AttachedRun>
  follow(paneRect: ScreenRect): Promise<PreviewAcknowledgement>
  setVisible(visible: boolean): Promise<PreviewAcknowledgement>
  detach(): Promise<PreviewAcknowledgement>
}

interface NativePreviewControllerOptions<RetryHandle> {
  sessionId: string
  runRevision: number
  documentVisible: boolean
  api: NativePreviewApi
  scheduleRetry(callback: () => void, delayMs: number): RetryHandle
  cancelRetry(handle: RetryHandle): void
  onStatus(status: NativePreviewStatus): void
  onError(error: unknown): void
}

export const INITIAL_PREVIEW_RETRY_DELAY_MS = 500
const MAX_PREVIEW_RETRY_DELAY_MS = 8_000

export class NativePreviewController<RetryHandle> {
  readonly #sessionId: string
  readonly #runRevision: number
  #documentVisible: boolean
  readonly #api: NativePreviewApi
  readonly #scheduleRetry: (callback: () => void, delayMs: number) => RetryHandle
  readonly #cancelRetry: (handle: RetryHandle) => void
  readonly #onStatus: (status: NativePreviewStatus) => void
  readonly #onError: (error: unknown) => void
  #pane: ScreenRect | null = null
  #paneRevision = 0
  #appliedPaneRevision = 0
  #resizeActive = false
  #attached = false
  #actualVisible: boolean | null = null
  #closed = false
  #drivePromise: Promise<void> | null = null
  #closePromise: Promise<void> | null = null
  #retryHandle: RetryHandle | null = null
  #retryDelay = INITIAL_PREVIEW_RETRY_DELAY_MS
  #errorReported = false

  constructor(options: NativePreviewControllerOptions<RetryHandle>) {
    this.#sessionId = options.sessionId
    this.#runRevision = options.runRevision
    this.#documentVisible = options.documentVisible
    this.#api = options.api
    this.#scheduleRetry = options.scheduleRetry
    this.#cancelRetry = options.cancelRetry
    this.#onStatus = options.onStatus
    this.#onError = options.onError
    this.#onStatus('connecting')
  }

  /** Accept the newest pane and whether drag-resize has settled. */
  updatePane(pane: ScreenRect, settled: boolean): Promise<void> {
    if (this.#closed) return Promise.resolve()
    this.#pane = Object.freeze({ ...pane })
    this.#paneRevision += 1
    this.#resizeActive = !settled
    return this.#requestDrive()
  }

  setDocumentVisible(visible: boolean): Promise<void> {
    if (this.#closed || this.#documentVisible === visible) {
      return this.#drivePromise ?? Promise.resolve()
    }
    this.#documentVisible = visible
    return this.#requestDrive()
  }

  /** Restore the native window after all already-started effects settle. */
  close(): Promise<void> {
    if (this.#closePromise !== null) return this.#closePromise
    this.#closed = true
    this.#cancelScheduledRetry()
    this.#closePromise = this.#finishClose()
    return this.#closePromise
  }

  async #finishClose(): Promise<void> {
    await this.#drivePromise
    requireAcknowledged(await this.#api.detach())
  }

  #requestDrive(): Promise<void> {
    this.#cancelScheduledRetry()
    if (this.#drivePromise === null) {
      const running = this.#drive()
      this.#drivePromise = running
      void running.finally(() => {
        if (this.#drivePromise === running) this.#drivePromise = null
      })
    }
    return this.#drivePromise
  }

  async #drive(): Promise<void> {
    try {
      while (!this.#closed && this.#pane !== null) {
        if (!this.#attached) {
          await this.#attachCurrentPane()
          continue
        }
        const desiredVisible = this.#documentVisible && !this.#resizeActive
        if (!desiredVisible && this.#actualVisible !== false) {
          await this.#setVisible(false)
          continue
        }
        if (this.#appliedPaneRevision < this.#paneRevision) {
          await this.#followCurrentPane()
          continue
        }
        if (this.#actualVisible !== desiredVisible) {
          await this.#setVisible(desiredVisible)
          continue
        }
        this.#errorReported = false
        this.#retryDelay = INITIAL_PREVIEW_RETRY_DELAY_MS
        this.#onStatus('attached')
        return
      }
    } catch (error: unknown) {
      if (this.#closed || error instanceof StaleNativePreviewOwnerError) return
      this.#onStatus('failed')
      if (!this.#errorReported) {
        this.#errorReported = true
        this.#onError(error)
      }
      this.#scheduleRetryAfterFailure()
    }
  }

  async #attachCurrentPane(): Promise<void> {
    const pane = this.#requirePane()
    const revision = this.#paneRevision
    const session = await this.#api.attach({ paneRect: pane })
    if (session.id !== this.#sessionId || session.run_revision !== this.#runRevision) {
      requireAcknowledged(await this.#api.detach())
      throw new StaleNativePreviewOwnerError()
    }
    if (this.#closed) return
    this.#attached = true
    this.#actualVisible = null
    this.#appliedPaneRevision = revision
  }

  async #followCurrentPane(): Promise<void> {
    const pane = this.#requirePane()
    const revision = this.#paneRevision
    requireAcknowledged(await this.#api.follow(pane))
    if (!this.#closed) this.#appliedPaneRevision = revision
  }

  async #setVisible(visible: boolean): Promise<void> {
    requireAcknowledged(await this.#api.setVisible(visible))
    if (!this.#closed) this.#actualVisible = visible
  }

  #requirePane(): ScreenRect {
    if (this.#pane === null) throw new TypeError('native preview pane is unavailable')
    return this.#pane
  }

  #scheduleRetryAfterFailure(): void {
    if (this.#closed || this.#retryHandle !== null) return
    const delay = this.#retryDelay
    this.#retryDelay = Math.min(this.#retryDelay * 2, MAX_PREVIEW_RETRY_DELAY_MS)
    this.#retryHandle = this.#scheduleRetry(() => {
      this.#retryHandle = null
      if (!this.#closed) void this.#requestDrive()
    }, delay)
  }

  #cancelScheduledRetry(): void {
    if (this.#retryHandle === null) return
    this.#cancelRetry(this.#retryHandle)
    this.#retryHandle = null
  }
}

function requireAcknowledged(result: PreviewAcknowledgement): void {
  if (!result.ok) throw new Error('native preview operation was not acknowledged')
}

class StaleNativePreviewOwnerError extends Error {
  constructor() {
    super('native preview owner was replaced')
    this.name = 'StaleNativePreviewOwnerError'
  }
}
