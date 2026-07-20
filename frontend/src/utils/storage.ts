/**
 * Type-safe localStorage wrapper with namespace isolation.
 */

const NAMESPACE = 'raguard:'

function buildKey(key: string): string {
  return `${NAMESPACE}${key}`
}

export const storage = {
  get<T>(key: string, fallback: T): T {
    try {
      const raw = localStorage.getItem(buildKey(key))
      if (raw === null) return fallback
      return JSON.parse(raw) as T
    } catch {
      return fallback
    }
  },

  set<T>(key: string, value: T): void {
    try {
      localStorage.setItem(buildKey(key), JSON.stringify(value))
    } catch {
      // Storage quota exceeded — fail silently
    }
  },

  remove(key: string): void {
    localStorage.removeItem(buildKey(key))
  },

  clear(): void {
    Object.keys(localStorage)
      .filter((k) => k.startsWith(NAMESPACE))
      .forEach((k) => localStorage.removeItem(k))
  },
}

// ─── Well-known storage keys ───────────────────────────────────────────────────
export const STORAGE_KEYS = {
  THEME: 'theme_preference',
  SIDEBAR_COLLAPSED: 'sidebar_collapsed',
} as const
