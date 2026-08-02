import React, { useState, useEffect, useMemo } from 'react'
import { ThemeContext } from '@/contexts/ThemeContext'
import type { ThemeMode } from '@/types'

export interface ThemeProviderProps {
  children: React.ReactNode
  initialMode?: ThemeMode
  onModeChange?: (mode: ThemeMode) => void
}

export function ThemeProvider({
  children,
  initialMode = 'light',
  onModeChange
}: ThemeProviderProps) {
  const [mode, setModeState] = useState<ThemeMode>(initialMode)
  const [resolvedMode, setResolvedMode] = useState<'dark' | 'light'>('light')

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

  const setMode = React.useCallback((newMode: ThemeMode) => {
    setModeState(newMode)
    if (onModeChange) {
      onModeChange(newMode)
    }
  }, [onModeChange])

  const value = useMemo(() => ({ mode, resolvedMode, setMode }), [mode, resolvedMode, setMode])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
