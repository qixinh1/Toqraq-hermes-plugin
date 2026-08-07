/** First-run readiness summary shown inside the empty viewport. */

import { jsx, jsxs } from 'react/jsx-runtime'
import { Button, icons, usePluginI18n } from '@hermes/plugin-sdk'
import type { PluginContext } from '@hermes/plugin-sdk'
import type { SetupResult } from '../contracts/generated.js'
import type { deriveSetupView } from '../state/setupView.js'
import { ComponentSetup } from './ComponentSetup.js'

interface SetupGuideProps {
  readonly ctx: PluginContext
  readonly setup: SetupResult | null
  readonly view: ReturnType<typeof deriveSetupView>
  readonly retrying: boolean
  readonly busy: boolean
  readonly onStart: () => void
  readonly onRetry: () => void
  readonly onComponentTerminal: () => Promise<void>
}

export function SetupGuide({
  ctx,
  setup,
  view,
  retrying,
  busy,
  onStart,
  onRetry,
  onComponentTerminal,
}: SetupGuideProps) {
  const t = usePluginI18n('toqraq')
  return jsxs('div', {
    className: 'flex w-full max-w-md flex-col gap-3 px-6 text-left',
    children: [
      jsxs('div', {
        role: 'status',
        'aria-live': 'polite',
        'aria-atomic': true,
        className: 'space-y-1',
        children: [
          jsx('h2', {
            className: 'text-sm font-medium text-(--ui-text-primary)',
            children: t(`setup.headline.${view.headline}`),
          }),
          jsx('div', {
            className: 'text-xs text-(--ui-text-tertiary)',
            children: t(`setup.description.${view.headline}`),
          }),
        ],
      }),
      view.showReadiness &&
        jsxs('dl', {
          className: 'grid gap-1.5',
          children: [
            jsx(SetupRow, {
              label: t('setup.item.session'),
              value: t(`setup.state.session.${view.session}`),
              ready: view.session === 'ready',
            }),
            jsx(SetupRow, {
              label: t('setup.item.host'),
              value: t(`setup.state.host.${view.host}`),
              ready: view.host === 'ready',
            }),
            jsx(SetupRow, {
              label: t('setup.item.project'),
              value: t(`setup.state.project.${view.project}`),
              ready: view.project === 'ready',
            }),
            setup?.engine &&
              jsx(SetupRow, {
                label: t('setup.item.engine'),
                value: setup.engine.id,
                ready: true,
              }),
            jsx(SetupRow, {
              label: t('setup.item.runtime'),
              value: t(`setup.state.runtime.${view.runtime}`),
              ready: view.runtime === 'ready',
            }),
          ],
        }),
      view.showComponentPlan &&
        setup?.engine &&
        setup.engine.required_component_release_ids.length > 0 &&
        jsx(ComponentSetup, {
          ctx,
          setup,
          onTerminal: onComponentTerminal,
        }),
      view.startable &&
        jsxs(Button, {
          size: 'sm',
          variant: 'default',
          disabled: busy,
          onClick: onStart,
          className: 'self-start',
          children: [
            jsx(icons.Play, { size: 13 }),
            jsx('span', {
              children: busy ? t('setup.action.starting') : t('setup.action.start'),
            }),
          ],
        }),
      view.retryable &&
        jsx(Button, {
          size: 'sm',
          variant: 'default',
          disabled: retrying,
          onClick: onRetry,
          className: 'self-start',
          children: retrying ? t('setup.action.retrying') : t('setup.action.retry'),
        }),
    ],
  })
}

interface SetupRowProps {
  readonly label: string
  readonly value: string
  readonly ready: boolean
}

function SetupRow({ label, value, ready }: SetupRowProps) {
  return jsxs('div', {
    className: 'flex items-center gap-2 rounded px-2 py-1.5 bg-(--ui-bg-secondary)',
    children: [
      jsx('span', {
        'aria-hidden': true,
        className: `size-1.5 rounded-full ${ready ? 'bg-(--ui-accent)' : 'bg-(--ui-text-tertiary)'}`,
      }),
      jsx('dt', {
        className: 'w-20 text-(--ui-text-secondary)',
        children: label,
      }),
      jsx('dd', {
        className: 'min-w-0 flex-1 truncate text-(--ui-text-primary)',
        children: value,
      }),
    ],
  })
}
