export interface InterpolatedMessage {
  (...args: unknown[]): string
  readonly i18nParameters: readonly string[]
}

/** Attach named interpolation parameters to one locale renderer. */
export function interpolated(
  parameters: readonly string[],
  render: (...args: unknown[]) => string,
): InterpolatedMessage {
  Object.defineProperty(render, 'i18nParameters', { value: Object.freeze([...parameters]) })
  return render as InterpolatedMessage
}
