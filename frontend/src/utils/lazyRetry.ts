import { ComponentType, lazy, LazyExoticComponent } from 'react'

/**
 * Key used in sessionStorage to track chunk reload attempts and prevent infinite reload loops.
 */
const RELOAD_STORAGE_KEY = 'raguard_chunk_reload_attempt'
const RELOAD_COOLDOWN_MS = 15000 // 15 seconds cooldown

/**
 * Determines whether an error is caused by a missing/stale dynamically imported chunk.
 */
export function isDynamicImportError(error: unknown): boolean {
  if (!error) return false
  const message = error instanceof Error ? error.message : String(error)
  return (
    message.includes('Failed to fetch dynamically imported module') ||
    message.includes('Importing a module script failed') ||
    message.includes('error loading dynamically imported module') ||
    message.includes('Loading chunk') ||
    message.includes('Failed to load module script')
  )
}

/**
 * Resilient dynamic import loader that recovers from stale/deleted chunks following new deployments.
 * If a dynamic chunk fails to fetch (e.g., HTTP 404 after a rebuild), it triggers a single controlled
 * page reload to fetch the latest index.html and module graph.
 */
export function lazyRetry<T extends ComponentType<any>>(
  componentImport: () => Promise<{ default: T }>,
  componentName = 'LazyComponent'
): LazyExoticComponent<T> {
  return lazy(async () => {
    try {
      const component = await componentImport()
      // Successful load - clear any lingering reload marker
      try {
        sessionStorage.removeItem(RELOAD_STORAGE_KEY)
      } catch {
        // Safe fallback for environments with restricted storage
      }
      return component
    } catch (error) {
      if (isDynamicImportError(error)) {
        let hasReloadedRecently = false
        try {
          const lastReloadTime = sessionStorage.getItem(RELOAD_STORAGE_KEY)
          if (lastReloadTime) {
            const timeSinceLastReload = Date.now() - parseInt(lastReloadTime, 10)
            if (timeSinceLastReload < RELOAD_COOLDOWN_MS) {
              hasReloadedRecently = true
            }
          }
        } catch {
          // Safe fallback
        }

        if (!hasReloadedRecently && typeof window !== 'undefined' && window.location) {
          console.warn(
            `[lazyRetry] Detected stale chunk failure for ${componentName}. Performing single controlled page reload.`
          )
          try {
            sessionStorage.setItem(RELOAD_STORAGE_KEY, String(Date.now()))
          } catch {
            // Safe fallback
          }

          // Trigger controlled reload to fetch new HTML & asset graph
          window.location.reload()

          // Return a pending promise so React Suspense remains suspended during reload transition
          return new Promise<{ default: T }>(() => {})
        } else {
          console.error(
            `[lazyRetry] Chunk load failed for ${componentName} after a reload attempt. Forwarding to ErrorBoundary to prevent infinite loops.`
          )
          try {
            sessionStorage.removeItem(RELOAD_STORAGE_KEY)
          } catch {
            // Safe fallback
          }
        }
      }

      // Re-throw if not a dynamic chunk error or if loop-protection limit reached
      throw error
    }
  })
}
