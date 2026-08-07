/** Physical native-window pane measurement for the Toqraq renderer. */

export type ScreenRect = Readonly<{
  x: number
  y: number
  width: number
  height: number
}>

export interface MeasurableElement {
  getBoundingClientRect(): Pick<DOMRect, 'left' | 'top' | 'width' | 'height'>
}

const WINDOWS_MINIMIZED_COORDINATE = -30_000

/** Return whether a rectangle is outside the Windows minimized sentinel area. */
export function isUsableScreenRect(rect: ScreenRect): boolean {
  return rect.x > WINDOWS_MINIMIZED_COORDINATE && rect.y > WINDOWS_MINIMIZED_COORDINATE
}

/**
 * Compute an element's screen-absolute rect in physical pixels.
 *
 * CSS coordinates are converted with the window's outer offset and scaled
 * by devicePixelRatio. Outer/inner deltas estimate the side border and top
 * chrome independently, avoiding the bottom border being counted as titlebar.
 */
export function elementScreenRect(element: MeasurableElement): ScreenRect {
  const rect = element.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  const sideBorder = Math.max(0, (window.outerWidth - window.innerWidth) / 2)
  const chromeTop = Math.max(0, window.outerHeight - window.innerHeight - sideBorder)
  return {
    x: Math.round((window.screenX + sideBorder + rect.left) * dpr),
    y: Math.round((window.screenY + chromeTop + rect.top) * dpr),
    width: Math.round(rect.width * dpr),
    height: Math.round(rect.height * dpr),
  }
}
