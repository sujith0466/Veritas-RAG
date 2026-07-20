import { useState, useEffect, useMemo } from 'react'
import { ThemeContext } from '@/contexts/ThemeContext'
import type { ThemeMode } from '@/types'
import { storage, STORAGE_KEYS } from '@/utils/storage'

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(() =>
    storage.get<ThemeMode>(STORAGE_KEYS.THEME, 'dark'),
  )

  const [resolvedMode, setResolvedMode] = useState<'dark' | 'light'>('dark')

  useEffect(() => {
    const root = window.document.documentElement
    root.classList.remove('light', 'dark')

    if (mode === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
      root.classList.add(systemTheme)
      setResolvedMode(systemTheme)
      // Listen for system changes
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      const handleChange = (e: MediaQueryListEvent) => {
        const newSystemTheme = e.matches ? 'dark' : 'light'
        root.classList.remove('light', 'dark')
        root.classList.add(newSystemTheme)
        setResolvedMode(newSystemTheme)
      }
      mediaQuery.addEventListener('change', handleChange)
      return () => mediaQuery.removeEventListener('change', handleChange)
    } else {
      root.classList.add(mode)
      setResolvedMode(mode)
    }
  }, [mode])

  const setMode = (newMode: ThemeMode) => {
    storage.set(STORAGE_KEYS.THEME, newMode)
    setModeState(newMode)
  }

  const value = useMemo(() => ({ mode, resolvedMode, setMode }), [mode, resolvedMode])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
