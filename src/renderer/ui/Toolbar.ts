/** Controls and immutable identity for the selected live game. */

import { jsx, jsxs } from 'react/jsx-runtime'
import { Button, icons, usePluginI18n } from '@hermes/plugin-sdk'
import type { RuntimeIdentityResult } from '../contracts/generated.js'
import type { RuntimeDisplayState } from '../state/runtimePresentation.js'

interface ToolbarProps {
  readonly projectDir: string
  readonly runtime: RuntimeIdentityResult
  readonly processState: RuntimeDisplayState
  readonly canPause: boolean
  readonly paused: boolean
  readonly busy: boolean
  readonly onStop: () => void
  readonly onTogglePause: () => void
}

/** Current live-session facts and controls. */
export function Toolbar(props: ToolbarProps) {
  const t = usePluginI18n('toqraq')
  const pauseLabel = props.paused ? t('toolbar.resumeTitle') : t('toolbar.pauseTitle')
  const stopLabel = props.processState === 'stopping'
    ? t('toolbar.finishStopTitle')
    : t('toolbar.stopTitle')
  return jsxs('div', {
    role: 'toolbar',
    'aria-label': t('toolbar.runtimeControls'),
    className: 'flex items-center gap-1.5 px-2 py-1.5 border-b border-(--ui-stroke-secondary)',
    children: [
      jsxs('div', {
        className: 'flex min-w-0 flex-1 items-baseline gap-2',
        children: [
          jsx('span', {
            className: 'min-w-0 flex-1 truncate text-xs text-(--ui-text-secondary)',
            title: props.projectDir,
            children: props.projectDir,
          }),
          jsx('span', {
            className: 'shrink-0 text-[0.6875rem] text-(--ui-text-tertiary)',
            children: t(
              'toolbar.runtimeIdentity',
              props.runtime.engine,
              props.runtime.version,
            ),
          }),
          jsx('span', {
            className: `shrink-0 text-[0.6875rem] ${props.paused ? 'text-(--ui-accent)' : 'text-(--ui-text-tertiary)'}`,
            children: t(
              'toolbar.processState',
              t(`status.${props.processState}`),
            ),
          }),
        ],
      }),
      props.canPause &&
        jsx(Button, {
          size: 'sm',
          variant: 'ghost',
          disabled: props.busy,
          onClick: props.onTogglePause,
          title: pauseLabel,
          'aria-label': pauseLabel,
          className: props.paused ? 'text-(--ui-accent)' : undefined,
          children: props.paused
            ? jsx(icons.Play, { size: 13 })
            : jsx(icons.Pause, { size: 13 }),
        }),
      jsx(Button, {
        size: 'sm',
        variant: 'ghost',
        disabled: props.busy,
        onClick: props.onStop,
        title: stopLabel,
        'aria-label': stopLabel,
        className: 'text-destructive hover:text-destructive',
        children: jsx(icons.Square, { size: 13 }),
      }),
    ],
  })
}
