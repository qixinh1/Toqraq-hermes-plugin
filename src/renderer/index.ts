/**
 * Toqraq desktop plugin entry point.
 *
 * Embeds one game engine viewport into a Hermes pane and exposes the bridge
 * backend at `/api/plugins/toqraq`.
 */

import type { HermesPlugin } from '@hermes/plugin-sdk'
import { bundles } from './i18n/messages.js'
import { registerContributions } from './contributions/main.js'

const plugin = {
  id: 'toqraq',
  name: 'Toqraq',
  register(ctx) {
    ctx.i18n.register(bundles)
    return registerContributions(ctx)
  },
} satisfies HermesPlugin

export default plugin
