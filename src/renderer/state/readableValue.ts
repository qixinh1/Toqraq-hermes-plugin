/** Minimal public Hermes state value consumed by plugin-lifetime synchronizers. */

export interface ReadableValue<Value> {
  get(): Value
  subscribe(listener: (value: Value) => void): () => void
}
