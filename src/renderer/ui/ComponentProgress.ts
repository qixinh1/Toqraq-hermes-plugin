/** Present one component job's localized phase, byte progress, and public failure. */

import { jsx, jsxs } from 'react/jsx-runtime'
import { usePluginI18n } from '@hermes/plugin-sdk'
import type { ComponentJobResult } from '../contracts/generated.js'
import { localizePublicError } from '../bridge/errorBoundary.js'
import { formatExactBytes } from './componentText.js'

interface ComponentProgressProps {
  readonly job: ComponentJobResult
  readonly progress: number | null
}

export function ComponentProgress({ job, progress }: ComponentProgressProps) {
  const t = usePluginI18n('toqraq')
  return jsxs('div', {
    className: 'space-y-1',
    children: [
      jsxs('div', {
        className: 'flex justify-between gap-2 text-[0.6875rem] text-(--ui-text-secondary)',
        children: [
          jsx('span', {
            role: 'status',
            'aria-live': 'polite',
            'aria-atomic': true,
            children: t(
              'component.statePhase',
              t(`component.state.${job.state}`),
              t(`component.phase.${job.phase}`),
            ),
          }),
          job.total_bytes > 0 &&
            jsx('span', {
              children: t(
                'component.progressValue',
                formatExactBytes(job.completed_bytes),
                formatExactBytes(job.total_bytes),
              ),
            }),
        ],
      }),
      jsx('progress', {
        className: 'h-1.5 w-full accent-(--ui-accent)',
        max: 1,
        ...(progress === null ? {} : { value: progress }),
        'aria-label': t('component.progressLabel'),
      }),
      job.error &&
        jsx('p', {
          className: 'text-xs text-destructive',
          role: 'alert',
          'aria-atomic': true,
          children: localizePublicError(t, job.error),
        }),
    ],
  })
}
