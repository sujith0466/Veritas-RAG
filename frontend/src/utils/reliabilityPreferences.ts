import { storage, STORAGE_KEYS } from '@/utils/storage'

export const VALID_RELIABILITY_INTERVALS = ['hourly', 'daily', 'weekly'] as const
export type ReliabilityInterval = (typeof VALID_RELIABILITY_INTERVALS)[number]

export interface ReliabilityPreferences {
  interval: ReliabilityInterval
  liveSync: boolean
}

export const DEFAULT_RELIABILITY_INTERVAL: ReliabilityInterval = 'daily'
export const DEFAULT_RELIABILITY_LIVE_SYNC: boolean = false

export function getScopedReliabilityStorageKey(userId?: string | null): string {
  const scope = userId ? `user:${userId}` : 'anonymous'
  return `${STORAGE_KEYS.RELIABILITY_PREFERENCES}:${scope}`
}

export function validateReliabilityInterval(value: unknown): ReliabilityInterval {
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    if (VALID_RELIABILITY_INTERVALS.includes(normalized as ReliabilityInterval)) {
      return normalized as ReliabilityInterval
    }
  }
  return DEFAULT_RELIABILITY_INTERVAL
}

export function validateReliabilityLiveSync(value: unknown): boolean {
  if (typeof value === 'boolean') {
    return value
  }
  return DEFAULT_RELIABILITY_LIVE_SYNC
}

export function getReliabilityPreferences(userId?: string | null): ReliabilityPreferences {
  const key = getScopedReliabilityStorageKey(userId)
  const stored = storage.get<Partial<ReliabilityPreferences> | null>(key, null)

  return {
    interval: validateReliabilityInterval(stored?.interval),
    liveSync: validateReliabilityLiveSync(stored?.liveSync),
  }
}

export function saveReliabilityPreferences(
  userId: string | null | undefined,
  updates: Partial<ReliabilityPreferences>
): ReliabilityPreferences {
  const current = getReliabilityPreferences(userId)
  const updated: ReliabilityPreferences = {
    interval: updates.interval !== undefined
      ? validateReliabilityInterval(updates.interval)
      : current.interval,
    liveSync: updates.liveSync !== undefined
      ? validateReliabilityLiveSync(updates.liveSync)
      : current.liveSync,
  }

  const key = getScopedReliabilityStorageKey(userId)
  storage.set(key, updated)
  return updated
}
