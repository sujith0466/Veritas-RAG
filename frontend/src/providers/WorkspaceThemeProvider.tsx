import { ThemeProvider } from './ThemeProvider'
import { storage, STORAGE_KEYS } from '@/utils/storage'
import type { ThemeMode } from '@/types'

/**
 * WorkspaceThemeProvider provides the theme context for the authenticated application.
 * It reads the user's initial preference from storage and persists any changes.
 */
export function WorkspaceThemeProvider({ children }: { children: React.ReactNode }) {
  const initialMode = storage.get<ThemeMode>(STORAGE_KEYS.THEME, 'dark')

  const handleModeChange = (mode: ThemeMode) => {
    storage.set(STORAGE_KEYS.THEME, mode)
  }

  return (
    <ThemeProvider initialMode={initialMode} onModeChange={handleModeChange}>
      {children}
    </ThemeProvider>
  )
}
