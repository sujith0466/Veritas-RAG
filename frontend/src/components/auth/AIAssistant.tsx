import { useEffect, useState, useRef } from 'react'
import {
  motion,
  useMotionValue,
  useSpring,
  useTransform,
  AnimatePresence,
  type Variants,
} from 'framer-motion'
import { cn } from '@/utils/cn'

export type AIAssistantState =
  | 'idle'
  | 'greeting'
  | 'email_focus'
  | 'password_focus'
  | 'password_visible'
  | 'loading'
  | 'success'
  | 'error'

interface AIAssistantProps {
  state: AIAssistantState
  className?: string
}

// Privacy state — password field is focused and password is hidden
function isPrivacyMode(state: AIAssistantState) {
  return state === 'password_focus'
}

export function AIAssistant({ state, className }: AIAssistantProps) {
  // Mouse parallax motion values
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)

  // Reduced motion detection
  const [isReducedMotion, setIsReducedMotion] = useState(false)
  // Self-managed inactivity sleep
  const [isSleeping, setIsSleeping] = useState(false)
  const sleepTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Layered spring configs
  // Heavy chassis — physical mass with inertia
  const chassisSpring = { damping: 36, stiffness: 85, mass: 1.4 }
  // Medium head
  const headSpring = { damping: 28, stiffness: 110, mass: 1.0 }
  // Agile optics — fast response, light
  const opticsSpring = { damping: 20, stiffness: 180, mass: 0.7 }

  const smoothChassisX = useSpring(mouseX, chassisSpring)
  const smoothChassisY = useSpring(mouseY, chassisSpring)
  const smoothHeadX = useSpring(mouseX, headSpring)
  const smoothHeadY = useSpring(mouseY, headSpring)
  const smoothOpticsX = useSpring(mouseX, opticsSpring)
  const smoothOpticsY = useSpring(mouseY, opticsSpring)

  // 3D rotation (chassis-level)
  const rotateX = useTransform(smoothChassisY, [-1, 1], [12, -12])
  const rotateY = useTransform(smoothChassisX, [-1, 1], [-15, 15])

  // Visor glass specular shift (head-level, slightly faster)
  const specularX = useTransform(smoothHeadX, [-1, 1], [-20, 20])
  const specularY = useTransform(smoothHeadY, [-1, 1], [-12, 12])

  // Optical sensor gaze tracking (fastest layer)
  const sensorTrackX = useTransform(smoothOpticsX, [-1, 1], [-7, 7])
  const sensorTrackY = useTransform(smoothOpticsY, [-1, 1], [-4.5, 4.5])

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    setIsReducedMotion(mediaQuery.matches)

    const resetSleep = () => {
      setIsSleeping(false)
      if (sleepTimerRef.current) clearTimeout(sleepTimerRef.current)
      sleepTimerRef.current = setTimeout(() => setIsSleeping(true), 60_000)
    }

    const handleMouseMove = (e: MouseEvent) => {
      resetSleep()
      if (mediaQuery.matches) return
      mouseX.set((e.clientX / window.innerWidth) * 2 - 1)
      mouseY.set((e.clientY / window.innerHeight) * 2 - 1)
    }

    const handleMouseLeave = () => {
      if (mediaQuery.matches) return
      mouseX.set(0)
      mouseY.set(0)
    }

    // Start sleep timer on mount
    sleepTimerRef.current = setTimeout(() => setIsSleeping(true), 60_000)

    window.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseleave', handleMouseLeave)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseleave', handleMouseLeave)
      if (sleepTimerRef.current) clearTimeout(sleepTimerRef.current)
    }
  }, [mouseX, mouseY])

  // ─── State flags ────────────────────────────────────────────────────────────
  const inPrivacy = isPrivacyMode(state)
  const isError = state === 'error'
  const isSuccess = state === 'success'
  const isLoading = state === 'loading'
  const isEmailFocus = state === 'email_focus'

  // ─── HEAD CHASSIS VARIANTS ──────────────────────────────────────────────────
  const headVariants: Variants = {
    idle: {
      y: [0, -3.5, -3.5, 0.5, 0],
      rotateZ: [0, 0.35, 0, -0.35, 0],
      rotateX: [0, 1, 0.4, -0.6, 0],
      transition: {
        y: { repeat: Infinity, duration: 5.8, times: [0, 0.4, 0.55, 0.9, 1], ease: 'easeInOut' as const },
        rotateZ: { repeat: Infinity, duration: 8.2, ease: 'easeInOut' as const },
        rotateX: { repeat: Infinity, duration: 9.4, ease: 'easeInOut' as const },
      },
    },
    email_focus: {
      y: 4,
      rotateX: 8,
      rotateZ: -0.6,
      transition: { type: 'spring' as const, stiffness: 210, damping: 22 },
    },
    password_focus: {
      y: 5,
      rotateX: 6,
      rotateZ: 0,
      transition: { type: 'spring' as const, stiffness: 200, damping: 24 },
    },
    password_visible: {
      y: 2,
      rotateX: 3.5,
      rotateZ: 1.8,
      transition: { type: 'spring' as const, stiffness: 220, damping: 20 },
    },
    loading: {
      y: [0, -2.5, 0],
      rotateZ: [0, 0.7, 0, -0.7, 0],
      rotateX: [1, 3.5, 1],
      transition: {
        y: { repeat: Infinity, duration: 1.6, ease: 'easeInOut' as const },
        rotateZ: { repeat: Infinity, duration: 2.0, ease: 'easeInOut' as const },
        rotateX: { repeat: Infinity, duration: 1.6, ease: 'easeInOut' as const },
      },
    },
    success: {
      y: -5,
      rotateX: -4,
      rotateZ: 0,
      transition: { type: 'spring' as const, stiffness: 280, damping: 18 },
    },
    error: {
      x: [0, -3.5, 3.5, -2.5, 2.5, 0],
      y: 1.5,
      rotateZ: [0, -1.2, 1.2, -0.8, 0.8, 0],
      transition: { duration: 0.42, ease: 'easeInOut' as const },
    },
  }

  // ─── OPTICAL SENSOR — LEFT ──────────────────────────────────────────────────
  // In privacy mode, sensors are physically covered by hands — no squash needed.
  // We only use opacity and a slight scale reduction to signal natural relaxation.
  const leftSensorVariants: Variants = {
    idle: {
      scaleY: [1, 1, 0.1, 1, 1],
      scaleX: 1,
      opacity: 0.95,
      transition: {
        scaleY: {
          repeat: Infinity,
          duration: 5.4,
          times: [0, 0.88, 0.91, 0.94, 1],
          ease: 'easeInOut' as const,
        },
        opacity: { repeat: Infinity, duration: 3.8, ease: 'easeInOut' as const },
      },
    },
    email_focus: {
      scaleY: 1.12,
      scaleX: 1.12,
      opacity: 1,
      transition: { type: 'spring' as const, stiffness: 280, damping: 18, delay: 0.02 },
    },
    // PASSWORD FOCUS: sensors simply look down + dim.
    // No horizontal scaleY squash — hands will cover them.
    password_focus: {
      scaleY: 0.85,
      scaleX: 0.85,
      opacity: 0.45,
      transition: { type: 'spring' as const, stiffness: 200, damping: 22, delay: 0.05 },
    },
    password_visible: {
      scaleY: 1,
      scaleX: 1.05,
      opacity: 0.95,
      transition: { type: 'spring' as const, stiffness: 240, damping: 20 },
    },
    loading: {
      scaleY: [0.9, 1.1, 0.9],
      scaleX: [1.1, 0.9, 1.1],
      opacity: [0.8, 1, 0.8],
      transition: { repeat: Infinity, duration: 1.1, ease: 'easeInOut' as const },
    },
    success: {
      scaleY: [1, 1.2, 1.1],
      scaleX: [1, 1.2, 1.1],
      opacity: 1,
      transition: { duration: 0.55, times: [0, 0.4, 1], ease: 'easeOut' as const },
    },
    error: {
      scaleY: 0.7,
      scaleX: 1.1,
      opacity: 0.9,
      transition: { type: 'spring' as const, stiffness: 380, damping: 18 },
    },
  }

  // ─── OPTICAL SENSOR — RIGHT ─────────────────────────────────────────────────
  // Phase-offset by ~0.18s vs left for authentic asynchronous optical behaviour
  const rightSensorVariants: Variants = {
    idle: {
      scaleY: [1, 1, 0.1, 1, 1],
      scaleX: 1,
      opacity: 0.95,
      transition: {
        scaleY: {
          repeat: Infinity,
          duration: 5.4,
          times: [0, 0.89, 0.92, 0.95, 1],
          ease: 'easeInOut' as const,
        },
        opacity: { repeat: Infinity, duration: 3.8, delay: 0.28, ease: 'easeInOut' as const },
      },
    },
    email_focus: {
      scaleY: 1.12,
      scaleX: 1.12,
      opacity: 1,
      transition: { type: 'spring' as const, stiffness: 280, damping: 18, delay: 0.05 },
    },
    password_focus: {
      scaleY: 0.85,
      scaleX: 0.85,
      opacity: 0.45,
      transition: { type: 'spring' as const, stiffness: 200, damping: 22, delay: 0.08 },
    },
    password_visible: {
      scaleY: 1,
      scaleX: 1.05,
      opacity: 0.95,
      transition: { type: 'spring' as const, stiffness: 240, damping: 20, delay: 0.03 },
    },
    loading: {
      scaleY: [0.9, 1.1, 0.9],
      scaleX: [1.1, 0.9, 1.1],
      opacity: [0.8, 1, 0.8],
      transition: { repeat: Infinity, duration: 1.1, delay: 0.09, ease: 'easeInOut' as const },
    },
    success: {
      scaleY: [1, 1.2, 1.1],
      scaleX: [1, 1.2, 1.1],
      opacity: 1,
      transition: { duration: 0.55, times: [0, 0.4, 1], delay: 0.04, ease: 'easeOut' as const },
    },
    error: {
      scaleY: 0.7,
      scaleX: 1.1,
      opacity: 0.9,
      transition: { type: 'spring' as const, stiffness: 380, damping: 18 },
    },
  }

  // ─── APERTURE COLOR ─────────────────────────────────────────────────────────
  const getApertureColor = () => {
    if (isError) return 'from-rose-500 via-red-600 to-amber-500'
    if (isSuccess) return 'from-emerald-400 via-teal-500 to-emerald-600'
    if (isLoading) return 'from-cyan-400 via-sky-500 to-blue-600'
    return 'from-teal-400 via-emerald-500 to-cyan-500'
  }

  const getGlowShadow = () => {
    if (isError) return 'rgba(244, 63, 94, 0.65)'
    if (isSuccess) return 'rgba(16, 185, 129, 0.7)'
    if (isLoading) return 'rgba(14, 165, 233, 0.65)'
    return 'rgba(20, 184, 166, 0.55)'
  }

  // ─── LEFT HAND — physical covering hand ─────────────────────────────────────
  // The hand is a rounded "palm" element that slides UP from below the visor
  // to cover the left optical sensor.  No bars, no overlays.
  const leftHandVariants: Variants = {
    idle: {
      y: 36,
      x: -18,
      opacity: 0,
      rotate: -12,
      transition: { type: 'spring' as const, stiffness: 140, damping: 22 },
    },
    email_focus: {
      y: 36,
      x: -18,
      opacity: 0,
      rotate: -12,
      transition: { type: 'spring' as const, stiffness: 140, damping: 22 },
    },
    // Hands move UP to cover sensors
    password_focus: {
      y: -2,
      x: -14,
      opacity: 1,
      rotate: -6,
      transition: { type: 'spring' as const, stiffness: 130, damping: 26, delay: 0.12 },
    },
    // Hands stay but tilt when password is revealed
    password_visible: {
      y: 36,
      x: -18,
      opacity: 0,
      rotate: -12,
      transition: { type: 'spring' as const, stiffness: 150, damping: 24 },
    },
    loading: {
      y: 36,
      x: -18,
      opacity: 0,
      rotate: -12,
      transition: { type: 'spring' as const, stiffness: 150, damping: 22 },
    },
    success: {
      y: 36,
      x: -18,
      opacity: 0,
      rotate: -12,
      transition: { type: 'spring' as const, stiffness: 150, damping: 22 },
    },
    error: {
      y: 36,
      x: -18,
      opacity: 0,
      rotate: -12,
      transition: { type: 'spring' as const, stiffness: 150, damping: 22 },
    },
  }

  const rightHandVariants: Variants = {
    idle: {
      y: 36,
      x: 18,
      opacity: 0,
      rotate: 12,
      transition: { type: 'spring' as const, stiffness: 140, damping: 22 },
    },
    email_focus: {
      y: 36,
      x: 18,
      opacity: 0,
      rotate: 12,
      transition: { type: 'spring' as const, stiffness: 140, damping: 22 },
    },
    password_focus: {
      y: -2,
      x: 14,
      opacity: 1,
      rotate: 6,
      transition: { type: 'spring' as const, stiffness: 130, damping: 26, delay: 0.16 },
    },
    password_visible: {
      y: 36,
      x: 18,
      opacity: 0,
      rotate: 12,
      transition: { type: 'spring' as const, stiffness: 150, damping: 24 },
    },
    loading: {
      y: 36,
      x: 18,
      opacity: 0,
      rotate: 12,
      transition: { type: 'spring' as const, stiffness: 150, damping: 22 },
    },
    success: {
      y: 36,
      x: 18,
      opacity: 0,
      rotate: 12,
      transition: { type: 'spring' as const, stiffness: 150, damping: 22 },
    },
    error: {
      y: 36,
      x: 18,
      opacity: 0,
      rotate: 12,
      transition: { type: 'spring' as const, stiffness: 150, damping: 22 },
    },
  }

  // ─── SLEEP / WAKE ────────────────────────────────────────────────────────────
  const sleepOffset = isSleeping && !isReducedMotion ? 4 : 0

  return (
    <div
      className={cn(
        'relative flex flex-col items-center justify-center w-64 h-52 select-none pointer-events-none',
        className
      )}
      role="img"
      aria-label="Veritas-RAG AI Sentinel Agent"
    >
      <motion.div
        style={{
          perspective: 1400,
          rotateX: isReducedMotion ? 0 : rotateX,
          rotateY: isReducedMotion ? 0 : rotateY,
          transformStyle: 'preserve-3d',
          y: sleepOffset,
        }}
        animate={{ y: sleepOffset }}
        transition={{ type: 'spring', stiffness: 60, damping: 30 }}
        className="relative w-48 h-44 flex items-center justify-center"
      >
        {/* Ambient Floor Shadow — breathes inversely with chassis altitude */}
        <motion.div
          className="absolute -bottom-2 w-36 h-5 bg-slate-950/20 dark:bg-black/40 blur-xl rounded-[100%]"
          style={{ transform: 'translateZ(-40px)', transformStyle: 'preserve-3d' }}
          animate={
            isReducedMotion
              ? { opacity: 0.22 }
              : {
                  scale: isLoading ? [1, 1.08, 1] : isSleeping ? 0.88 : [1, 0.93, 1],
                  opacity: isLoading ? [0.25, 0.4, 0.25] : isSleeping ? 0.14 : [0.24, 0.16, 0.24],
                }
          }
          transition={{ repeat: Infinity, duration: 5.8, ease: 'easeInOut' }}
        />

        {/* Telemetry Aura Ring — slows during sleep */}
        <motion.div
          className="absolute -inset-4 rounded-full border border-teal-500/10 dark:border-teal-400/10 pointer-events-none"
          style={{ transform: 'translateZ(-30px) rotateX(65deg)', transformStyle: 'preserve-3d' }}
          animate={isReducedMotion ? {} : { rotateZ: 360 }}
          transition={{ repeat: Infinity, duration: isSleeping ? 48 : 28, ease: 'linear' }}
        >
          <motion.div
            className="absolute top-0 left-1/2 w-1.5 h-1.5 bg-teal-400/60 rounded-full shadow-[0_0_8px_rgba(45,212,191,0.8)] -translate-x-1/2 -translate-y-1/2"
            animate={{ opacity: isSleeping ? [0.15, 0.3, 0.15] : [0.4, 0.9, 0.4] }}
            transition={{ repeat: Infinity, duration: isSleeping ? 5 : 3.2, ease: 'easeInOut' }}
          />
        </motion.div>

        {/* Chassis Neck Mount & Lower Radiator */}
        <div
          className="absolute w-20 h-10 rounded-b-2xl bg-gradient-to-b from-slate-200 via-slate-300 to-slate-400 dark:from-slate-800 dark:via-slate-850 dark:to-slate-900 border border-slate-300 dark:border-slate-700/60 shadow-lg"
          style={{ transform: 'translateZ(-20px) translateY(38px)', transformStyle: 'preserve-3d' }}
        >
          <div className="flex justify-center items-center gap-1.5 pt-4">
            <span className="w-1 h-2.5 rounded-full bg-slate-400 dark:bg-slate-700" />
            <motion.span
              className="w-1 h-3.5 rounded-full bg-teal-500/60 shadow-[0_0_4px_rgba(20,184,166,0.6)]"
              animate={
                isReducedMotion
                  ? { opacity: 0.7 }
                  : {
                      opacity: isLoading ? [0.5, 1, 0.5] : isSleeping ? [0.2, 0.35, 0.2] : [0.4, 0.85, 0.4],
                      scaleY: isLoading ? [0.9, 1.15, 0.9] : 1,
                    }
              }
              transition={{
                repeat: Infinity,
                duration: isLoading ? 1.2 : isSleeping ? 6 : 4,
                ease: 'easeInOut',
              }}
            />
            <span className="w-1 h-2.5 rounded-full bg-slate-400 dark:bg-slate-700" />
          </div>
        </div>

        {/* Lateral Ear Nodes */}
        <div
          className="absolute -left-3 w-5 h-12 rounded-l-xl bg-gradient-to-r from-slate-300 via-slate-200 to-slate-100 dark:from-slate-900 dark:via-slate-800 dark:to-slate-700 border-y border-l border-slate-300 dark:border-slate-700 shadow-md flex items-center justify-center"
          style={{ transform: 'translateZ(-5px)', transformStyle: 'preserve-3d' }}
        >
          <span className="w-1 h-5 rounded-full bg-slate-400/80 dark:bg-slate-600" />
        </div>
        <div
          className="absolute -right-3 w-5 h-12 rounded-r-xl bg-gradient-to-l from-slate-300 via-slate-200 to-slate-100 dark:from-slate-900 dark:via-slate-800 dark:to-slate-700 border-y border-r border-slate-300 dark:border-slate-700 shadow-md flex items-center justify-center"
          style={{ transform: 'translateZ(-5px)', transformStyle: 'preserve-3d' }}
        >
          <span className="w-1 h-5 rounded-full bg-slate-400/80 dark:bg-slate-600" />
        </div>

        {/* ── PHYSICAL PRIVACY HANDS ─────────────────────────────────────────────
            These are rounded palm elements that physically slide up to cover
            the visor during password_focus — no horizontal lines, no overlays.
        ──────────────────────────────────────────────────────────────────────── */}
        <motion.div
          variants={leftHandVariants}
          initial="idle"
          animate={state}
          className="absolute z-20 w-12 h-10 rounded-[1.2rem] bg-gradient-to-br from-slate-200 via-slate-300 to-slate-400 dark:from-slate-700 dark:via-slate-800 dark:to-slate-900 border border-slate-300/80 dark:border-slate-600/60 shadow-xl"
          style={{ transformOrigin: 'bottom center' }}
        >
          {/* Knuckle detail lines */}
          <div className="absolute inset-x-2 top-2 flex flex-col gap-1 pointer-events-none">
            <span className="h-px w-full rounded-full bg-slate-400/40 dark:bg-slate-600/40" />
            <span className="h-px w-3/4 rounded-full bg-slate-400/30 dark:bg-slate-600/30" />
          </div>
          {/* Palm highlight */}
          <div className="absolute inset-x-1 top-1 h-3 rounded-t-xl bg-gradient-to-b from-white/30 to-transparent pointer-events-none" />
        </motion.div>

        <motion.div
          variants={rightHandVariants}
          initial="idle"
          animate={state}
          className="absolute z-20 w-12 h-10 rounded-[1.2rem] bg-gradient-to-bl from-slate-200 via-slate-300 to-slate-400 dark:from-slate-700 dark:via-slate-800 dark:to-slate-900 border border-slate-300/80 dark:border-slate-600/60 shadow-xl"
          style={{ transformOrigin: 'bottom center' }}
        >
          {/* Knuckle detail lines */}
          <div className="absolute inset-x-2 top-2 flex flex-col gap-1 pointer-events-none">
            <span className="h-px w-full rounded-full bg-slate-400/40 dark:bg-slate-600/40" />
            <span className="h-px w-3/4 ml-auto rounded-full bg-slate-400/30 dark:bg-slate-600/30" />
          </div>
          {/* Palm highlight */}
          <div className="absolute inset-x-1 top-1 h-3 rounded-t-xl bg-gradient-to-b from-white/30 to-transparent pointer-events-none" />
        </motion.div>

        {/* ── MAIN HEAD CHASSIS ──────────────────────────────────────────────── */}
        <motion.div
          variants={headVariants}
          initial="idle"
          animate={state}
          className="relative w-44 h-28 rounded-[2.25rem] bg-gradient-to-b from-white via-slate-50 to-slate-200 dark:from-slate-900 dark:via-slate-900 dark:to-slate-950 border border-white/90 dark:border-slate-750 flex flex-col items-center justify-center overflow-visible"
          style={{
            transformStyle: 'preserve-3d',
            boxShadow: `
              0 24px 48px -12px rgba(15, 23, 42, 0.18),
              inset 0 2px 4px rgba(255, 255, 255, 0.9),
              inset 0 -6px 12px rgba(15, 23, 42, 0.08),
              0 0 0 1px rgba(255, 255, 255, 0.4)
            `,
          }}
        >
          {/* Top Telemetry Crown & Diagnostic LED */}
          <div className="absolute top-2 inset-x-8 flex items-center justify-between px-1 pointer-events-none">
            <span className="w-3 h-0.5 rounded-full bg-slate-300 dark:bg-slate-700" />
            <motion.div
              className="flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-slate-200/80 dark:bg-slate-800/80 border border-slate-300/60 dark:border-slate-700"
              animate={
                isReducedMotion
                  ? { opacity: 0.8 }
                  : {
                      opacity: isError
                        ? [0.55, 1, 0.55]
                        : isLoading
                          ? [0.5, 1, 0.5]
                          : isSleeping
                            ? [0.4, 0.6, 0.4]
                            : [0.75, 1, 0.75],
                    }
              }
              transition={{
                repeat: Infinity,
                duration: isError ? 0.38 : isLoading ? 1.1 : isSleeping ? 4.5 : 3,
                ease: 'easeInOut',
              }}
            >
              <motion.span
                className="w-1.5 h-1.5 rounded-full transition-colors duration-300"
                style={{
                  backgroundColor: isError
                    ? '#f43f5e'
                    : isSuccess
                      ? '#10b981'
                      : isLoading
                        ? '#0ea5e9'
                        : isSleeping
                          ? '#475569'
                          : '#14b8a6',
                  boxShadow: `0 0 6px ${getGlowShadow()}`,
                }}
                animate={
                  isSuccess
                    ? { scale: [1, 1.45, 1], boxShadow: ['0 0 4px #10b981', '0 0 12px #10b981', '0 0 4px #10b981'] }
                    : {}
                }
                transition={{ duration: 0.75, ease: 'easeOut' }}
              />
            </motion.div>
            <span className="w-3 h-0.5 rounded-full bg-slate-300 dark:bg-slate-700" />
          </div>

          {/* ── OBSIDIAN GLASS VISOR ──────────────────────────────────────────── */}
          <div
            className="relative w-36 h-16 rounded-[1.35rem] bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 border border-slate-800/90 dark:border-slate-700/80 overflow-hidden flex items-center justify-center shadow-inner"
            style={{
              transformStyle: 'preserve-3d',
              boxShadow: `
                inset 0 4px 12px rgba(0, 0, 0, 0.9),
                inset 0 -2px 6px rgba(255, 255, 255, 0.08),
                0 4px 12px rgba(0, 0, 0, 0.25)
              `,
            }}
          >
            {/* Dynamic Glass Specular Curvature — mouse parallax driven */}
            <motion.div
              className="absolute inset-0 bg-gradient-to-tr from-transparent via-white/[0.08] to-transparent pointer-events-none"
              style={{
                x: isReducedMotion ? 0 : specularX,
                y: isReducedMotion ? 0 : specularY,
              }}
            />
            {/* Slow ambient photon sweep across visor */}
            <motion.div
              className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.035] to-transparent pointer-events-none"
              animate={isReducedMotion || isSleeping ? { opacity: 0 } : { x: ['-100%', '100%'] }}
              transition={{ repeat: Infinity, duration: 11, ease: 'easeInOut' }}
            />
            {/* Curved anti-reflective coating sheen */}
            <div className="absolute top-0.5 inset-x-3 h-2.5 rounded-full bg-gradient-to-b from-cyan-400/[0.07] to-transparent pointer-events-none" />

            {/* ── DUAL OPTICAL SENSORS (gaze tracked) ────────────────────────── */}
            <motion.div
              className="flex items-center justify-center gap-7 w-full h-full relative z-10"
              style={{
                x: isReducedMotion ? 0 : sensorTrackX,
                y: isReducedMotion ? 0 : sensorTrackY,
              }}
            >
              {/* Left Optical Sensor */}
              <motion.div
                variants={leftSensorVariants}
                initial="idle"
                animate={state}
                className="relative w-8 h-8 rounded-full bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-700/70 p-0.5 flex items-center justify-center shadow-[inset_0_2px_4px_rgba(0,0,0,0.8)]"
              >
                <div className="absolute inset-0 rounded-full border border-teal-500/20 dark:border-teal-400/20" />
                <div
                  className={cn(
                    'w-5 h-5 rounded-full bg-gradient-to-tr flex items-center justify-center relative overflow-hidden transition-colors duration-300',
                    getApertureColor()
                  )}
                  style={{ boxShadow: `0 0 12px ${getGlowShadow()}` }}
                >
                  <motion.div
                    className="w-2.5 h-2.5 rounded-full bg-slate-950 flex items-center justify-center"
                    animate={
                      isReducedMotion
                        ? {}
                        : { scale: isLoading ? [0.82, 1.18, 0.82] : isSleeping ? 0.7 : [1, 0.9, 1] }
                    }
                    transition={{
                      repeat: Infinity,
                      duration: isLoading ? 1.1 : isSleeping ? 6 : 5,
                      ease: 'easeInOut',
                    }}
                  >
                    <span className="w-1 h-1 rounded-full bg-white shadow-[0_0_4px_#fff]" />
                  </motion.div>
                  <div className="absolute top-0.5 right-1 w-1.5 h-1 rounded-full bg-white/70 transform -rotate-45" />
                </div>
              </motion.div>

              {/* Right Optical Sensor */}
              <motion.div
                variants={rightSensorVariants}
                initial="idle"
                animate={state}
                className="relative w-8 h-8 rounded-full bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-700/70 p-0.5 flex items-center justify-center shadow-[inset_0_2px_4px_rgba(0,0,0,0.8)]"
              >
                <div className="absolute inset-0 rounded-full border border-teal-500/20 dark:border-teal-400/20" />
                <div
                  className={cn(
                    'w-5 h-5 rounded-full bg-gradient-to-tr flex items-center justify-center relative overflow-hidden transition-colors duration-300',
                    getApertureColor()
                  )}
                  style={{ boxShadow: `0 0 12px ${getGlowShadow()}` }}
                >
                  <motion.div
                    className="w-2.5 h-2.5 rounded-full bg-slate-950 flex items-center justify-center"
                    animate={
                      isReducedMotion
                        ? {}
                        : { scale: isLoading ? [0.82, 1.18, 0.82] : isSleeping ? 0.7 : [1, 0.9, 1] }
                    }
                    transition={{
                      repeat: Infinity,
                      duration: isLoading ? 1.1 : isSleeping ? 6 : 5,
                      delay: 0.15,
                      ease: 'easeInOut',
                    }}
                  >
                    <span className="w-1 h-1 rounded-full bg-white shadow-[0_0_4px_#fff]" />
                  </motion.div>
                  <div className="absolute top-0.5 right-1 w-1.5 h-1 rounded-full bg-white/70 transform -rotate-45" />
                </div>
              </motion.div>
            </motion.div>

            {/* Optical Processing Sweep — loading only */}
            <AnimatePresence>
              {isLoading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 pointer-events-none"
                >
                  <motion.div
                    className="w-full h-[1.5px] bg-gradient-to-r from-transparent via-cyan-400 to-transparent shadow-[0_0_6px_rgba(14,165,233,0.9)]"
                    animate={isReducedMotion ? { opacity: 0.4 } : { y: [-4, 64, -4] }}
                    transition={{ repeat: Infinity, duration: 1.55, ease: 'linear' }}
                  />
                  <div className="absolute inset-0 bg-cyan-500/[0.03]" />
                </motion.div>
              )}
            </AnimatePresence>

            {/* Success confirmation glint */}
            <AnimatePresence>
              {isSuccess && (
                <motion.div
                  initial={{ opacity: 0, x: '-100%' }}
                  animate={{ opacity: [0, 0.35, 0], x: ['−100%', '100%'] }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.7, ease: 'easeOut' }}
                  className="absolute inset-0 bg-gradient-to-r from-transparent via-emerald-400/20 to-transparent pointer-events-none"
                />
              )}
            </AnimatePresence>

            {/* Lower visor horizon reflection */}
            <div className="absolute bottom-0 inset-x-4 h-1 rounded-t-full bg-gradient-to-t from-white/[0.04] to-transparent pointer-events-none" />
          </div>

          {/* Email focus gaze indicator — subtle downward arc under sensors */}
          <AnimatePresence>
            {isEmailFocus && !isReducedMotion && (
              <motion.div
                initial={{ opacity: 0, scaleX: 0 }}
                animate={{ opacity: 1, scaleX: 1 }}
                exit={{ opacity: 0, scaleX: 0 }}
                transition={{ type: 'spring', stiffness: 300, damping: 28 }}
                className="absolute bottom-2.5 inset-x-10 h-px rounded-full bg-teal-400/30 pointer-events-none"
              />
            )}
          </AnimatePresence>

          {/* Privacy mode sensor cover — subtle visor-interior dimming behind hands */}
          <AnimatePresence>
            {inPrivacy && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.35, ease: 'easeInOut' }}
                className="absolute inset-0 rounded-[2.25rem] bg-slate-950/10 pointer-events-none"
              />
            )}
          </AnimatePresence>

          {/* Chin Seam & Mic Array Accent */}
          <div className="absolute bottom-1.5 flex items-center gap-1 pointer-events-none">
            <span className="w-1 h-1 rounded-full bg-slate-300 dark:bg-slate-700" />
            <span className="w-4 h-0.5 rounded-full bg-slate-300/80 dark:bg-slate-700/80" />
            <span className="w-1 h-1 rounded-full bg-slate-300 dark:bg-slate-700" />
          </div>
        </motion.div>
      </motion.div>
    </div>
  )
}
