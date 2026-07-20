/**
 * RAGuard AI Design System — Centralized Design Tokens
 *
 * Single source of truth for all visual design values.
 * CSS custom properties in globals.css mirror these tokens.
 */

// ─── Color Scales ─────────────────────────────────────────────────────────────

export const colorScales = {
  // Indigo — Primary brand
  indigo: {
    50: '#EEF2FF',
    100: '#E0E7FF',
    200: '#C7D2FE',
    300: '#A5B4FC',
    400: '#818CF8',
    500: '#6366F1',
    600: '#4F46E5',
    700: '#4338CA',
    800: '#3730A3',
    900: '#312E81',
  },
  // Violet — Secondary accent
  violet: {
    50: '#F5F3FF',
    100: '#EDE9FE',
    200: '#DDD6FE',
    300: '#C4B5FD',
    400: '#A78BFA',
    500: '#8B5CF6',
    600: '#7C3AED',
    700: '#6D28D9',
    800: '#5B21B6',
    900: '#4C1D95',
  },
  // Emerald — Success
  emerald: {
    50: '#ECFDF5',
    400: '#34D399',
    500: '#10B981',
    600: '#059669',
  },
  // Amber — Warning
  amber: {
    50: '#FFFBEB',
    400: '#FBBF24',
    500: '#F59E0B',
    600: '#D97706',
  },
  // Red — Danger
  red: {
    50: '#FEF2F2',
    400: '#F87171',
    500: '#EF4444',
    600: '#DC2626',
  },
  // Sky — Info
  sky: {
    50: '#F0F9FF',
    400: '#38BDF8',
    500: '#0EA5E9',
    600: '#0284C7',
  },
  // Neutral — Grays
  neutral: {
    50: '#FAFAFA',
    100: '#F5F5F5',
    200: '#E5E5E5',
    300: '#D4D4D4',
    400: '#A3A3A3',
    500: '#737373',
    600: '#525252',
    700: '#404040',
    800: '#262626',
    900: '#171717',
    950: '#0A0A0A',
  },
} as const

// ─── Semantic Tokens ──────────────────────────────────────────────────────────

export const semanticColors = {
  dark: {
    background: '#0A0A0C',
    surface: '#141418',
    surfaceElevated: '#1B1B21',
    border: '#1F1F24',
    borderSubtle: '#2A2A32',
    muted: '#222228',
    mutedForeground: '#7F7F8F',
    foreground: '#EBEBEB',
    primary: '#6366F1',
    primaryHover: '#4F52DB',
    primarySubtle: 'rgba(99,102,241,0.1)',
  },
  light: {
    background: '#FAFAFB',
    surface: '#FFFFFF',
    surfaceElevated: '#F7F7FA',
    border: '#E4E4EA',
    borderSubtle: '#F1F1F5',
    muted: '#F2F2F5',
    mutedForeground: '#6F6F80',
    foreground: '#12121A',
    primary: '#4F46E5',
    primaryHover: '#4338CA',
    primarySubtle: 'rgba(79,70,229,0.08)',
  },
} as const

// ─── Typography ────────────────────────────────────────────────────────────────

export const typography = {
  fontFamilies: {
    sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
    mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
  },
  fontSizes: {
    '2xs': '0.625rem',
    xs: '0.75rem',
    sm: '0.875rem',
    base: '1rem',
    lg: '1.125rem',
    xl: '1.25rem',
    '2xl': '1.5rem',
    '3xl': '1.875rem',
    '4xl': '2.25rem',
    '5xl': '3rem',
  },
  fontWeights: {
    light: 300,
    regular: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
    extrabold: 800,
  },
  letterSpacings: {
    tighter: '-0.04em',
    tight: '-0.02em',
    heading: '-0.011em',
    normal: '0',
    wide: '0.025em',
    wider: '0.05em',
    caps: '0.08em',
  },
} as const

// ─── Spacing (4px grid) ───────────────────────────────────────────────────────

export const spacing = {
  0: '0',
  0.5: '0.125rem',  // 2px
  1: '0.25rem',     // 4px
  1.5: '0.375rem',  // 6px
  2: '0.5rem',      // 8px
  2.5: '0.625rem',  // 10px
  3: '0.75rem',     // 12px
  3.5: '0.875rem',  // 14px
  4: '1rem',        // 16px
  5: '1.25rem',     // 20px
  6: '1.5rem',      // 24px
  7: '1.75rem',     // 28px
  8: '2rem',        // 32px
  9: '2.25rem',     // 36px
  10: '2.5rem',     // 40px
  11: '2.75rem',    // 44px
  12: '3rem',       // 48px
  14: '3.5rem',     // 56px
  16: '4rem',       // 64px
  20: '5rem',       // 80px
  24: '6rem',       // 96px
  32: '8rem',       // 128px
} as const

// ─── Border Radius ────────────────────────────────────────────────────────────

export const radii = {
  none: '0',
  sm: '0.25rem',    // 4px
  DEFAULT: '0.5rem', // 8px
  md: '0.625rem',   // 10px
  lg: '0.75rem',    // 12px
  xl: '1rem',       // 16px
  '2xl': '1.5rem',  // 24px
  '3xl': '2rem',    // 32px
  full: '9999px',
} as const

// ─── Shadows ──────────────────────────────────────────────────────────────────

export const shadows = {
  xs: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
  sm: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  DEFAULT: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
  lg: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
  xl: '0 20px 25px -5px rgb(0 0 0 / 0.15), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
  '2xl': '0 25px 50px -12px rgb(0 0 0 / 0.25)',
  glow: '0 0 0 1px rgba(99,102,241,0.3), 0 0 20px rgba(99,102,241,0.15)',
  'glow-sm': '0 0 0 1px rgba(99,102,241,0.2), 0 0 8px rgba(99,102,241,0.1)',
} as const

// ─── Breakpoints ──────────────────────────────────────────────────────────────

export const breakpoints = {
  xs: '375px',
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1536px',
} as const

// ─── Z-Index Scale ────────────────────────────────────────────────────────────

export const zIndex = {
  below: -1,
  base: 0,
  raised: 10,
  dropdown: 200,
  sticky: 300,
  overlay: 400,
  modal: 500,
  popover: 600,
  toast: 700,
  tooltip: 800,
} as const

// ─── Sidebar Dimensions ───────────────────────────────────────────────────────

export const layout = {
  sidebar: {
    expanded: '16.25rem', // 260px
    collapsed: '4.25rem', // 68px
  },
  header: {
    height: '3.5rem', // 56px
  },
  content: {
    maxWidth: '85rem', // 1360px
  },
} as const
