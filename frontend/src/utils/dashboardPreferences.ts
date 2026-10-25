import { storage, STORAGE_KEYS } from '@/utils/storage'

export const VALID_TIME_WINDOWS = ['1h', '24h', '7d', '30d', 'all'] as const
export type DashboardTimeWindow = (typeof VALID_TIME_WINDOWS)[number]

export const VALID_AUTO_REFRESH_INTERVALS = [0, 10, 30, 60] as const
export type DashboardAutoRefreshInterval = (typeof VALID_AUTO_REFRESH_INTERVALS)[number]

export interface DashboardPreferences {
  timeWindow: DashboardTimeWindow
  autoRefreshInterval: number
}

export const DEFAULT_DASHBOARD_TIME_WINDOW: DashboardTimeWindow = '24h'
export const DEFAULT_DASHBOARD_AUTO_REFRESH: number = 0

export function getScopedDashboardStorageKey(userId?: string | null): string {
  const scope = userId ? `user:${userId}` : 'anonymous'
  return `${STORAGE_KEYS.DASHBOARD_PREFERENCES}:${scope}`
}

export function validateTimeWindow(value: unknown): DashboardTimeWindow {
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    if (VALID_TIME_WINDOWS.includes(normalized as DashboardTimeWindow)) {
      return normalized as DashboardTimeWindow
    }
  }
  return DEFAULT_DASHBOARD_TIME_WINDOW
}

export function validateAutoRefreshInterval(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    if (VALID_AUTO_REFRESH_INTERVALS.includes(value as DashboardAutoRefreshInterval)) {
      return value
    }
  }
  return DEFAULT_DASHBOARD_AUTO_REFRESH
}

export function getDashboardPreferences(userId?: string | null): DashboardPreferences {
  const key = getScopedDashboardStorageKey(userId)
  const stored = storage.get<Partial<DashboardPreferences> | null>(key, null)

  // Fallback to individual legacy keys if present for backward compatibility
  const legacyTimeWindow = userId
    ? storage.get<unknown>(`dashboard_time_window:user:${userId}`, null)
    : null
  const legacyInterval = userId
    ? storage.get<unknown>(`dashboard_auto_refresh:user:${userId}`, null)
    : null

  const rawWindow = stored?.timeWindow ?? legacyTimeWindow
  const rawInterval = stored?.autoRefreshInterval ?? legacyInterval

  return {
    timeWindow: validateTimeWindow(rawWindow),
    autoRefreshInterval: validateAutoRefreshInterval(rawInterval),
  }
}

export function saveDashboardPreferences(
  userId: string | null | undefined,
  updates: Partial<DashboardPreferences>
): DashboardPreferences {
  const current = getDashboardPreferences(userId)
  const updated: DashboardPreferences = {
    timeWindow: updates.timeWindow !== undefined
      ? validateTimeWindow(updates.timeWindow)
      : current.timeWindow,
    autoRefreshInterval: updates.autoRefreshInterval !== undefined
      ? validateAutoRefreshInterval(updates.autoRefreshInterval)
      : current.autoRefreshInterval,
  }

  const key = getScopedDashboardStorageKey(userId)
  storage.set(key, updated)
  return updated
}
