/**
 * Status bar chip showing the Toqraq game state at a glance.
 */

import { jsx, jsxs } from 'react/jsx-runtime'
import { StatusDot, usePluginI18n, useValue } from '@hermes/plugin-sdk'
import type { ComponentProps } from 'react'
import type { RendererSessionStore } from '../state/rendererSessionStore.js'
import { projectGameRuntimeState } from '../state/runtimePresentation.js'

interface StatusChipProps {
  readonly sessionStore: RendererSessionStore
}

/** Render the status chip. */
export function StatusChip({ sessionStore }: StatusChipProps) {
  const t = usePluginI18n('toqraq')
  const processState = projectGameRuntimeState(useValue(sessionStore.gameState))
  const tone = processState === 'running' || processState === 'paused'
    ? 'good'
    : processState === 'stopping'
      ? 'warn'
      : processState === 'idle'
        ? 'muted'
        : 'bad'
  const dotProps = { tone } satisfies ComponentProps<typeof StatusDot>
  return jsxs('span', {
    role: 'status',
    'aria-live': 'polite',
    'aria-atomic': true,
    className: 'flex items-center gap-1 px-1.5 text-[0.6875rem] text-(--ui-text-tertiary)',
    title: t('status.title'),
    children: [
      jsx(StatusDot, dotProps),
      t('status.value', t(`status.${processState}`)),
    ],
  })
}
