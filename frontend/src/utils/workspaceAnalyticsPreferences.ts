import { storage, STORAGE_KEYS } from '@/utils/storage'

export const VALID_ANALYTICS_TIME_RANGES = ['24h', '7d', '30d', '90d', 'all'] as const
export type AnalyticsTimeRange = (typeof VALID_ANALYTICS_TIME_RANGES)[number]

export interface WorkspaceAnalyticsPreferences {
  timeRange: AnalyticsTimeRange
}

export const DEFAULT_ANALYTICS_TIME_RANGE: AnalyticsTimeRange = '30d'

export function getScopedAnalyticsStorageKey(userId?: string | null): string {
  const scope = userId ? `user:${userId}` : 'anonymous'
  return `${STORAGE_KEYS.WORKSPACE_ANALYTICS_PREFERENCES}:${scope}`
}

export function validateAnalyticsTimeRange(value: unknown): AnalyticsTimeRange {
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    if (normalized === 'all time') {
      return 'all'
    }
    if (VALID_ANALYTICS_TIME_RANGES.includes(normalized as AnalyticsTimeRange)) {
      return normalized as AnalyticsTimeRange
    }
  }
  return DEFAULT_ANALYTICS_TIME_RANGE
}

export function getWorkspaceAnalyticsPreferences(userId?: string | null): WorkspaceAnalyticsPreferences {
  const key = getScopedAnalyticsStorageKey(userId)
  const stored = storage.get<Partial<WorkspaceAnalyticsPreferences> | null>(key, null)

  return {
    timeRange: validateAnalyticsTimeRange(stored?.timeRange),
  }
}

export function saveWorkspaceAnalyticsPreferences(
  userId: string | null | undefined,
  updates: Partial<WorkspaceAnalyticsPreferences>
): WorkspaceAnalyticsPreferences {
  const current = getWorkspaceAnalyticsPreferences(userId)
  const updated: WorkspaceAnalyticsPreferences = {
    timeRange: updates.timeRange !== undefined
      ? validateAnalyticsTimeRange(updates.timeRange)
      : current.timeRange,
  }

  const key = getScopedAnalyticsStorageKey(userId)
  storage.set(key, updated)
  return updated
}
