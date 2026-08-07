/** Present one managed-component release and its available user intents. */

import { jsx, jsxs } from 'react/jsx-runtime'
import { Button, usePluginI18n } from '@hermes/plugin-sdk'
import type { ReactNode } from 'react'
import type { PluginTranslate } from '@hermes/plugin-sdk'
import type {
  ComponentJobAction,
  ComponentJobResult,
  ComponentReleaseResult,
  SetupAction,
} from '../contracts/generated.js'
import type { ComponentActions } from '../state/componentSetup.js'
import {
  componentPrepareActionKey,
  deriveComponentCardState,
} from '../state/componentSetup.js'
import { ComponentProgress } from './ComponentProgress.js'
import {
  componentReleaseIdentity,
  componentReleaseTarget,
  formatExactBytes,
} from './componentText.js'

interface ComponentCardProps {
  readonly release: ComponentReleaseResult
  readonly setupAction: SetupAction
  readonly job: ComponentJobResult | null
  readonly requesting: boolean
  readonly onStart: (releaseId: string, action: ComponentJobAction) => Promise<void>
  readonly onCancel: () => Promise<void>
  readonly onRetry: () => Promise<void>
}

export function ComponentCard({
  release,
  setupAction,
  job,
  requesting,
  onStart,
  onCancel,
  onRetry,
}: ComponentCardProps) {
  const t = usePluginI18n('toqraq')
  const view = deriveComponentCardState(release, job, requesting)

  return jsxs('article', {
    className: 'space-y-2 rounded border border-(--ui-stroke-secondary) bg-(--ui-bg-secondary) p-2.5',
    children: [
      jsxs('div', {
        className: 'flex items-start justify-between gap-3',
        children: [
          jsxs('div', {
            className: 'min-w-0',
            children: [
              jsx('div', {
                className: 'truncate text-xs font-medium text-(--ui-text-primary)',
                children: release.label,
              }),
              jsx('div', {
                className: 'truncate text-[0.6875rem] text-(--ui-text-tertiary)',
                children: componentReleaseIdentity(release),
              }),
            ],
          }),
          jsx('span', {
            className: 'shrink-0 text-[0.6875rem] text-(--ui-text-secondary)',
            children: t(`component.readiness.${release.readiness}`),
          }),
        ],
      }),
      jsxs('dl', {
        className: 'grid grid-cols-[6rem_minmax(0,1fr)] gap-x-2 gap-y-1 text-[0.6875rem]',
        children: [
          jsx(Detail, {
            label: t('component.detail.target'),
            children: componentReleaseTarget(release),
          }),
          jsx(Detail, {
            label: t('component.detail.size'),
            children: t(
              'component.sizeValue',
              formatExactBytes(release.package_bytes),
              formatExactBytes(release.installed_bytes),
            ),
          }),
          jsx(Detail, {
            label: t('component.detail.source'),
            children: jsxs('span', {
              className: 'inline-flex min-w-0 flex-wrap gap-x-2',
              children: [
                externalLink(release.source.provenance_url, release.source.publisher),
                externalLink(release.source.package_url, t('component.packageLink')),
              ],
            }),
          }),
          jsx(Detail, {
            label: t('component.detail.license'),
            children: jsxs('span', {
              className: 'inline-flex min-w-0 flex-wrap gap-x-1',
              children: [
                externalLink(
                  release.license.url,
                  `${release.license.name} (${release.license.identifier})`,
                ),
                release.license.acceptance_required && t('component.requiredMarker'),
              ],
            }),
          }),
          jsx(Detail, {
            label: t('component.detail.authentication'),
            children: release.authentication_required
              ? t('component.authenticationRequired')
              : t('component.authenticationNotRequired'),
          }),
        ],
      }),
      view.job && jsx(ComponentProgress, { job: view.job, progress: view.progress }),
      release.in_use && release.readiness === 'ready' &&
        jsx('p', {
          className: 'text-[0.6875rem] text-(--ui-text-tertiary)',
          children: t('component.removeBlocked'),
        }),
      jsx('div', {
        className: 'flex flex-wrap justify-end gap-1.5',
        children: componentActionButtons({
          t,
          release,
          setupAction,
          actions: view.actions,
          actionDisabled: view.actionDisabled,
          onStart,
          onCancel,
          onRetry,
        }),
      }),
    ],
  })
}

interface ComponentActionButtonsInput {
  readonly t: PluginTranslate
  readonly release: ComponentReleaseResult
  readonly setupAction: SetupAction
  readonly actions: ComponentActions
  readonly actionDisabled: boolean
  readonly onStart: (releaseId: string, action: ComponentJobAction) => Promise<void>
  readonly onCancel: () => Promise<void>
  readonly onRetry: () => Promise<void>
}

function componentActionButtons(input: ComponentActionButtonsInput): ReactNode[] {
  const buttons: ReactNode[] = []
  if (input.actions.canCancel) {
    buttons.push(
      jsx(Button, {
        size: 'sm',
        variant: 'ghost',
        disabled: input.actionDisabled,
        onClick: () => void input.onCancel(),
        children: input.t('component.action.cancel'),
      }, 'cancel'),
    )
  }
  if (input.actions.canRetry) {
    buttons.push(
      jsx(Button, {
        size: 'sm',
        variant: 'default',
        disabled: input.actionDisabled,
        onClick: () => void input.onRetry(),
        children: input.t('component.action.retry'),
      }, 'retry'),
    )
  } else if (input.setupAction === 'install' && input.actions.canPrepare) {
    buttons.push(
      jsx(Button, {
        size: 'sm',
        variant: 'default',
        disabled: input.actionDisabled,
        onClick: () => void input.onStart(input.release.release_id, 'prepare'),
        children: input.t(componentPrepareActionKey(input.release)),
      }, 'prepare'),
    )
  }
  if (input.actions.canRemove) {
    buttons.push(
      jsx(Button, {
        size: 'sm',
        variant: 'ghost',
        disabled: input.actionDisabled,
        onClick: () => void input.onStart(input.release.release_id, 'remove'),
        children: input.t('component.action.remove'),
      }, 'remove'),
    )
  }
  return buttons
}

interface DetailProps {
  readonly label: string
  readonly children: ReactNode
}

function Detail({ label, children }: DetailProps) {
  return jsxs('div', {
    className: 'contents',
    children: [
      jsx('dt', { className: 'text-(--ui-text-tertiary)', children: label }),
      jsx('dd', { className: 'min-w-0 text-(--ui-text-secondary)', children }),
    ],
  })
}

function externalLink(url: string, label: string) {
  return jsx('a', {
    href: url,
    target: '_blank',
    rel: 'noreferrer noopener',
    className: 'min-w-0 truncate text-(--ui-accent) hover:underline',
    title: url,
    children: label,
  })
}
