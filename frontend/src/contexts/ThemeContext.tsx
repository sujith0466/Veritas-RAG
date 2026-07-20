import { createContext } from 'react'
import type { ThemeMode } from '@/types'

export interface ThemeContextType {
  mode: ThemeMode
  resolvedMode: 'dark' | 'light'
  setMode: (mode: ThemeMode) => void
}

export const ThemeContext = createContext<ThemeContextType | undefined>(undefined)
