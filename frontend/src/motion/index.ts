/**
 * RAGuard AI — Centralized Motion System
 *
 * All Framer Motion configurations in one place.
 * Components import from here — never define inline variants.
 */

import type { Variants, Transition } from 'framer-motion'

// ─── Spring Presets ────────────────────────────────────────────────────────────

export const springs = {
  /** Snappy, responsive — for interactive UI elements */
  snappy: { type: 'spring', stiffness: 400, damping: 30 },
  /** Smooth, natural — for layout transitions */
  smooth: { type: 'spring', stiffness: 300, damping: 35 },
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
  instant: { duration: 0.1, ease: 'easeOut' },
  /** Fast UI feedback (button press, focus) */
  fast: { duration: 0.15, ease: [0.4, 0, 0.2, 1] },
  /** Standard element transition */
  normal: { duration: 0.2, ease: [0.4, 0, 0.2, 1] },
  /** Relaxed page-level transition */
  relaxed: { duration: 0.3, ease: [0.4, 0, 0.2, 1] },
  /** Slow, cinematic — for background effects */
  slow: { duration: 0.5, ease: [0.4, 0, 0.2, 1] },
  /** Spring-based sidebar collapse/expand */
  sidebar: springs.smooth,
  /** Spring-based modal/dialog open */
  modal: springs.snappy,
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
