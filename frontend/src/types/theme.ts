export type ThemeMode = 'dark' | 'light' | 'system'

export interface ThemeState {
  mode: ThemeMode
  resolvedMode: 'dark' | 'light'
}
