/** Opaque ownership for asynchronous lifecycle actions, keyed by Hermes session. */

export type SessionOperationToken = Readonly<{
  owner: string
  sequence: number
}>

export class SessionOperations {
  #selected: string | null = null
  readonly #active = new Map<string, SessionOperationToken>()
  #nextSequence = 1
  #disposed = false

  select(sessionId: string | null): boolean {
    if (this.#disposed) return false
    if (this.#selected === sessionId) return false
    this.#selected = sessionId
    return true
  }

  begin(sessionId: string): SessionOperationToken | null {
    if (this.#disposed || !sessionId || this.#active.has(sessionId)) return null
    const token = Object.freeze({ owner: sessionId, sequence: this.#nextSequence })
    this.#nextSequence += 1
    this.#active.set(sessionId, token)
    return token
  }

  owns(token: SessionOperationToken): boolean {
    return !this.#disposed && this.#active.get(token.owner) === token
  }

  finish(token: SessionOperationToken): boolean {
    if (!this.owns(token)) return false
    this.#active.delete(token.owner)
    return true
  }

  accepts(sessionId: string): boolean {
    return !this.#disposed && this.#selected === sessionId
  }

  busy(): boolean {
    return !this.#disposed && this.#selected !== null && this.#active.has(this.#selected)
  }

  dispose(): void {
    if (this.#disposed) return
    this.#disposed = true
    this.#selected = null
    this.#active.clear()
  }
}
