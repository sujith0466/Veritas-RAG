/**
 * Veritas RAG — Centralized Motion System
 *
 * All Framer Motion configurations in one place.
 * Components import from here — never define inline variants.
 */

import type { Variants, Transition, TargetAndTransition } from 'framer-motion'

// ─── Spring Presets ────────────────────────────────────────────────────────────

export const springs = {
  /** Snappy, responsive — for interactive UI elements */
  snappy: { type: 'spring', stiffness: 400, damping: 30 },
  /** Smooth, natural — for layout transitions */
  smooth: { type: 'spring', stiffness: 350, damping: 35 },
  /** Bouncy — for playful interactions (toasts, badges) */
  bouncy: { type: 'spring', stiffness: 500, damping: 25 },
  /** Gentle — for subtle fades and background animations */
  gentle: { type: 'spring', stiffness: 200, damping: 40 },
  /** Stiff — for instant-feeling responses (buttons) */
  stiff: { type: 'spring', stiffness: 600, damping: 35 },
} as const

// ─── Transition Presets ───────────────────────────────────────────────────────

export const transitions = {
  /** Ultra-fast micro-interaction (hover states) */
  instant: { duration: 0.1, ease: 'easeOut' }, // 100ms
  /** Fast UI feedback (button press, focus, cards, dialogs) */
  fast: { duration: 0.15, ease: [0.4, 0, 0.2, 1] }, // 150ms
  /** Standard element transition (page nav) */
  normal: { duration: 0.2, ease: [0.4, 0, 0.2, 1] }, // 200ms
  /** Relaxed page-level transition */
  relaxed: { duration: 0.25, ease: [0.4, 0, 0.2, 1] }, // 250ms
  /** Slow, cinematic — for background effects */
  slow: { duration: 0.5, ease: [0.4, 0, 0.2, 1] },
  /** Spring-based sidebar collapse/expand */
  sidebar: { duration: 0.18, ease: [0.4, 0, 0.2, 1] }, // 180ms
  /** Spring-based modal/dialog open */
  modal: { duration: 0.15, ease: [0.4, 0, 0.2, 1] }, // 150ms
} as const satisfies Record<string, Transition>

// ─── Page Transition Variants ─────────────────────────────────────────────────

/** Standard page entry/exit with subtle slide-up */
export const pageTransitionVariants: Variants = {
  initial: { opacity: 0, y: 8 },
  enter: { opacity: 1, y: 0, transition: transitions.relaxed },
  exit: { opacity: 0, y: -4, transition: transitions.fast },
}

/** Fade-only page transition — for rapid navigations */
export const pageFadeVariants: Variants = {
  initial: { opacity: 0 },
  enter: { opacity: 1, transition: transitions.normal },
  exit: { opacity: 0, transition: transitions.fast },
}

/** Restrained enterprise workspace page transition */
export const workspacePageVariants: Variants = {
  initial: { opacity: 0, y: 6 },
  enter: { opacity: 1, y: 0, transition: { duration: 0.2, ease: [0.4, 0, 0.2, 1] } },
  exit: { opacity: 0, transition: { duration: 0.12, ease: 'easeOut' } },
}

/** Workspace card group container for subtle staggered reveal */
export const workspaceCardGroupVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.04,
      delayChildren: 0.02,
    },
  },
}

/** Workspace card child item for restrained reveal */
export const workspaceCardItemVariants: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.2, ease: [0.4, 0, 0.2, 1] },
  },
}

/** Dashboard analytical tier group container for coordinated staggered reveal */
export const dashboardAnalyticalGroupVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.08,
    },
  },
}

/** Dashboard analytical child card item for refined entrance */
export const dashboardAnalyticalItemVariants: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.22, ease: [0.4, 0, 0.2, 1] },
  },
}

/** Dashboard forensic flight recorder entrance variants */
export const dashboardFlightRecorderVariants: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.22, ease: [0.4, 0, 0.2, 1] },
  },
}

/** Subtle enterprise card hover elevation */
export const dashboardCardHover: TargetAndTransition = {
  y: -2,
  transition: { duration: 0.18, ease: 'easeOut' },
}

/** Workspace tab panel cross-fade for seamless section switching */
export const workspaceTabPanelVariants: Variants = {
  initial: { opacity: 0.88, y: 3 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.15, ease: 'easeOut' },
  },
  exit: { opacity: 0, transition: { duration: 0.08 } },
}

// ─── Common Element Variants ──────────────────────────────────────────────────

export const fadeVariants: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: transitions.normal },
  exit: { opacity: 0, transition: transitions.fast },
}

export const slideUpVariants: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: transitions.relaxed },
  exit: { opacity: 0, y: -8, transition: transitions.fast },
}

export const slideDownVariants: Variants = {
  hidden: { opacity: 0, y: -16 },
  visible: { opacity: 1, y: 0, transition: transitions.relaxed },
  exit: { opacity: 0, y: 8, transition: transitions.fast },
}

export const slideRightVariants: Variants = {
  hidden: { opacity: 0, x: -16 },
  visible: { opacity: 1, x: 0, transition: transitions.relaxed },
  exit: { opacity: 0, x: -8, transition: transitions.fast },
}

export const scaleVariants: Variants = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1, transition: springs.snappy },
  exit: { opacity: 0, scale: 0.97, transition: transitions.fast },
}

// ─── Sidebar Variants ─────────────────────────────────────────────────────────

export const sidebarVariants = {
  expanded: { width: '16.25rem', transition: springs.smooth },
  collapsed: { width: '4.25rem', transition: springs.smooth },
} as const

export const sidebarLabelVariants: Variants = {
  expanded: { opacity: 1, width: 'auto', transition: { ...transitions.normal, delay: 0.05 } },
  collapsed: { opacity: 0, width: 0, transition: transitions.fast },
}

// ─── Toast / Notification Variants ───────────────────────────────────────────

export const toastVariants: Variants = {
  initial: { opacity: 0, y: 16, scale: 0.96 },
  animate: { opacity: 1, y: 0, scale: 1, transition: springs.bouncy },
  exit: { opacity: 0, y: -8, scale: 0.97, transition: transitions.fast },
}

// ─── Dynamic Island Variants ──────────────────────────────────────────────────

export const dynamicIslandVariants: Variants = {
  initial: {
    opacity: 0,
    scale: 0.88,
    y: -20,
    width: 156,
    height: 38,
    borderRadius: 24,
  },
  pill: {
    opacity: 1,
    scale: 1,
    y: 0,
    width: 156,
    height: 38,
    borderRadius: 24,
    transition: {
      type: 'spring',
      stiffness: 340,
      damping: 26,
      mass: 0.9,
    },
  },
  expanded: (custom?: { hasMessage?: boolean }) => ({
    opacity: 1,
    scale: 1,
    y: 0,
    width: 'auto',
    height: 'auto',
    minWidth: custom?.hasMessage ? 280 : 180,
    maxWidth: 440,
    minHeight: custom?.hasMessage ? 56 : 38,
    borderRadius: 20,
    transition: {
      type: 'spring',
      stiffness: 260,
      damping: 25,
      mass: 0.85,
    },
  }),
  suppressed: {
    opacity: 0,
    scale: 0.92,
    y: -10,
    pointerEvents: 'none',
    transition: { duration: 0.18, ease: 'easeOut' },
  },
  collapsing: {
    opacity: 0,
    scale: 0.88,
    y: -16,
    width: 156,
    height: 38,
    borderRadius: 24,
    pointerEvents: 'none',
    transition: {
      width: { type: 'spring', stiffness: 300, damping: 28, mass: 0.8 },
      height: { type: 'spring', stiffness: 300, damping: 28, mass: 0.8 },
      borderRadius: { type: 'spring', stiffness: 300, damping: 28, mass: 0.8 },
      opacity: { duration: 0.28, delay: 0.08, ease: [0.4, 0, 0.2, 1] },
      scale: { duration: 0.32, ease: [0.4, 0, 0.2, 1] },
      y: { duration: 0.32, ease: [0.4, 0, 0.2, 1] },
    },
  },
}

export const dynamicIslandPillVariants: Variants = {
  initial: {
    opacity: 0,
    scale: 0.9,
  },
  pill: {
    opacity: 1,
    scale: 1,
    transition: { duration: 0.2, ease: 'easeOut' },
  },
  expanded: {
    opacity: 0,
    scale: 0.88,
    transition: { duration: 0.14, ease: 'easeIn' },
  },
  suppressed: {
    opacity: 0,
    scale: 0.88,
    transition: { duration: 0.14 },
  },
  collapsing: {
    opacity: 0,
    scale: 0.88,
    transition: { duration: 0.14 },
  },
}

export const dynamicIslandContentVariants: Variants = {
  initial: {
    opacity: 0,
    scale: 0.96,
    y: 4,
  },
  pill: {
    opacity: 0,
    scale: 0.94,
    y: 4,
    transition: { duration: 0.12 },
  },
  expanded: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: {
      duration: 0.26,
      delay: 0.14,
      ease: [0.16, 1, 0.3, 1],
    },
  },
  suppressed: {
    opacity: 0,
    scale: 0.96,
    y: -4,
    transition: { duration: 0.15 },
  },
  collapsing: {
    opacity: 0,
    scale: 0.94,
    transition: { duration: 0.12 },
  },
}

// ─── Card Variants ────────────────────────────────────────────────────────────

export const cardVariants: Variants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: transitions.relaxed },
  exit: { opacity: 0, y: -4, transition: transitions.fast },
}

/** Hover state — applied via whileHover on <motion.div> */
export const cardHover = {
  scale: 1.015,
  transition: springs.snappy,
}

// ─── List Stagger Variants ────────────────────────────────────────────────────

/** Parent container — triggers stagger for children */
export const listContainerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.05 },
  },
}

/** Individual list item */
export const listItemVariants: Variants = {
  hidden: { opacity: 0, x: -8 },
  visible: { opacity: 1, x: 0, transition: springs.gentle },
}

// ─── Modal / Dialog Variants ──────────────────────────────────────────────────

export const overlayVariants: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: transitions.normal },
  exit: { opacity: 0, transition: transitions.fast },
}

export const modalVariants: Variants = {
  hidden: { opacity: 0, scale: 0.96, y: 8 },
  visible: { opacity: 1, scale: 1, y: 0, transition: springs.snappy },
  exit: { opacity: 0, scale: 0.97, y: 4, transition: transitions.fast },
}

// ─── Skeleton Loading ─────────────────────────────────────────────────────────

export const skeletonVariants: Variants = {
  loading: {
    backgroundPosition: ['200% 0', '-200% 0'],
    transition: { repeat: Infinity, duration: 1.5, ease: 'linear' },
  },
}

// ─── Dropdown Variants ────────────────────────────────────────────────────────

export const dropdownVariants: Variants = {
  hidden: { opacity: 0, scale: 0.97, y: -4 },
  visible: { opacity: 1, scale: 1, y: 0, transition: springs.snappy },
  exit: { opacity: 0, scale: 0.97, y: -4, transition: transitions.fast },
}

// ─── Global Loading Overlay ───────────────────────────────────────────────────

export const loadingOverlayVariants: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: transitions.fast },
  exit: { opacity: 0, transition: transitions.slow },
}
