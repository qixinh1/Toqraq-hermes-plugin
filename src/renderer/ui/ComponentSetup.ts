/** Compose the managed-component plan with its mounted lifecycle controller. */

import { jsx, jsxs } from 'react/jsx-runtime'
import { Button, usePluginI18n } from '@hermes/plugin-sdk'
import type { ReactNode } from 'react'
import type { PluginContext, PluginTranslate } from '@hermes/plugin-sdk'
import type { SetupResult } from '../contracts/generated.js'
import {
  ToqraqApiError,
  localizeApiError,
} from '../bridge/errorBoundary.js'
import { useComponentSetup } from '../hooks/useComponentSetup.js'
import { resolveSetupComponentPlan } from '../state/componentSetup.js'
import { ComponentCard } from './ComponentCard.js'

interface ComponentSetupProps {
  readonly ctx: PluginContext
  readonly setup: SetupResult
  readonly onTerminal: () => Promise<void>
}

export function ComponentSetup({ ctx, setup, onTerminal }: ComponentSetupProps) {
  const t = usePluginI18n('toqraq')
  const requiredReleaseIds = setup.engine?.required_component_release_ids ?? []
  const controller = useComponentSetup(
    ctx,
    true,
    requiredReleaseIds,
    onTerminal,
  )
  const releases = resolveSetupComponentPlan(setup, controller.components)
  const componentsError = visibleApiError(t, controller.componentsError)
  const jobReadError = visibleApiError(t, controller.jobError)
  const requestError = controller.requestError
    ? localizeApiError(t, controller.requestError)
    : null

  if (controller.componentsPending) {
    return jsx(ComponentMessage, { children: t('component.loading') })
  }
  if (componentsError) {
    return jsx(RefreshableComponentError, {
      message: componentsError,
      refreshing: controller.componentsRefreshing,
      onRetry: controller.refreshComponents,
    })
  }
  if (!releases) {
    return jsx(RefreshableComponentError, {
      message: t('component.planUnavailable'),
      refreshing: controller.componentsRefreshing,
      onRetry: controller.refreshComponents,
    })
  }

  return jsxs('section', {
    className: 'space-y-2 pt-1',
    'aria-label': t('component.heading'),
    children: [
      jsx('h3', {
        className: 'text-xs font-medium text-(--ui-text-primary)',
        children:
          setup.action === 'install'
            ? t('component.headingRequired')
            : t('component.headingReady'),
      }),
      releases.map((release) =>
        jsx(
          ComponentCard,
          {
            release,
            setupAction: setup.action,
            job: controller.job,
            requesting: controller.requesting,
            onStart: controller.start,
            onCancel: controller.cancel,
            onRetry: controller.retry,
          },
          release.release_id,
        ),
      ),
      (requestError || jobReadError) &&
        jsx('p', {
          className: 'text-xs text-destructive',
          role: 'alert',
          'aria-atomic': true,
          children: requestError ?? jobReadError,
        }),
    ],
  })
}

interface RefreshableComponentErrorProps {
  readonly message: string
  readonly refreshing: boolean
  readonly onRetry: () => Promise<void>
}

function RefreshableComponentError({
  message,
  refreshing,
  onRetry,
}: RefreshableComponentErrorProps) {
  const t = usePluginI18n('toqraq')
  return jsxs('div', {
    className: 'space-y-2 pt-1',
    children: [
      jsx(ComponentMessage, { tone: 'error', children: message }),
      jsx(Button, {
        size: 'sm',
        variant: 'default',
        disabled: refreshing,
        onClick: () => void onRetry(),
        children: refreshing
          ? t('component.action.refreshing')
          : t('component.action.retry'),
      }),
    ],
  })
}

interface ComponentMessageProps {
  readonly children: ReactNode
  readonly tone?: 'normal' | 'error'
}

function ComponentMessage({ children, tone = 'normal' }: ComponentMessageProps) {
  return jsx('p', {
    className: `pt-1 text-xs ${tone === 'error' ? 'text-destructive' : 'text-(--ui-text-tertiary)'}`,
    ...(tone === 'error'
      ? { role: 'alert', 'aria-atomic': true }
      : { role: 'status', 'aria-live': 'polite', 'aria-atomic': true }),
    children,
  })
}

function visibleApiError(t: PluginTranslate, error: unknown): string | null {
  if (!error) return null
  return error instanceof ToqraqApiError
    ? localizeApiError(t, error)
    : t('failure.transportUnavailable')
}
