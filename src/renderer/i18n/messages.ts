/** Locale bundle assembly for Hermes plugin registration. */

import type { PluginLocaleBundles } from '@hermes/plugin-sdk'
import { en } from './locales/en.js'
import { zh } from './locales/zh.js'

export const bundles = Object.freeze({ en, zh }) satisfies PluginLocaleBundles
