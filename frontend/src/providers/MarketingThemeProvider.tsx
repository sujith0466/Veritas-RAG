import { ThemeProvider } from './ThemeProvider'

/**
 * MarketingThemeProvider provides the theme context exclusively for marketing pages.
 * It enforces the Light theme and ignores localStorage and system preferences.
 */
export function MarketingThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider initialMode="light">
      {children}
    </ThemeProvider>
  )
}
