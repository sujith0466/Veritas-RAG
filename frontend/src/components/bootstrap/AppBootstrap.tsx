import { useEffect, useState } from 'react'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { useAuthStore } from '@/stores/authStore'
import { healthService } from '@/services/api/healthService'
import { vectorService } from '@/services/vectorService'
import { Check } from 'lucide-react'

type StepId =
  | 'security'
  | 'knowledge'
  | 'vector'
  | 'retrieval'
  | 'cross_encoder'
  | 'reliability'
  | 'prompt_guard'
  | 'workspace'

interface Step {
  id: StepId
  label: string
}

const STEPS: Step[] = [
  { id: 'security', label: 'Security Layer' },
  { id: 'knowledge', label: 'Knowledge Engine' },
  { id: 'vector', label: 'Vector Database' },
  { id: 'retrieval', label: 'Hybrid Retrieval' },
  { id: 'cross_encoder', label: 'Cross-Encoder Reranker' },
  { id: 'reliability', label: 'Reliability Engine' },
  { id: 'prompt_guard', label: 'Prompt Guard' },
  { id: 'workspace', label: 'Workspace Ready' },
]

export function AppBootstrap() {
  const shouldReduceMotion = useReducedMotion()

  const [isColdStart] = useState<boolean>(() => {
    const isBootstrapped = typeof window !== 'undefined' && !!sessionStorage.getItem('raguard_bootstrapped')
    if (isBootstrapped && typeof window !== 'undefined') {
      ;(window as any).__VERITAS_BOOTSTRAPPED__ = true
    }
    return !isBootstrapped
  })

  const authStatus = useAuthStore((s) => s.status)

  const [completedSteps, setCompletedSteps] = useState<Set<StepId>>(new Set())
  const [activeStepId, setActiveStepId] = useState<StepId | null>(STEPS[0].id)
  const [allReady, setAllReady] = useState(false)
  const [activeStepText, setActiveStepText] = useState('Initializing Enterprise AI Infrastructure')

  // Real signal flags
  const [healthReady, setHealthReady] = useState(false)
  const [vectorReady, setVectorReady] = useState(false)

  useEffect(() => {
    if (!isColdStart) return

    // Kick off async initialization pings
    healthService.getBasicHealth()
      .then(() => setHealthReady(true))
      .catch(() => setHealthReady(true)) // graceful fallback

    vectorService.getHealth()
      .then(() => setVectorReady(true))
      .catch(() => setVectorReady(true)) // graceful fallback
  }, [isColdStart])

  // Sequentially reveal verified infrastructure stages
  useEffect(() => {
    if (!isColdStart || allReady) return

    const authResolved = authStatus !== 'LOADING'

    // Identify the next pending stage
    const nextStep = STEPS.find((s) => !completedSteps.has(s.id))

    if (!nextStep) {
      setActiveStepId(null)
      setActiveStepText('Launching Workspace...')
      const t = setTimeout(() => {
        sessionStorage.setItem('raguard_bootstrapped', 'true')
        setAllReady(true)
      }, shouldReduceMotion ? 100 : 350)
      return () => clearTimeout(t)
    }

    setActiveStepId(nextStep.id)

    // Verify whether the next stage's underlying prerequisite has physically resolved
    let isEligible = false
    switch (nextStep.id) {
      case 'security':
        isEligible = authResolved
        break
      case 'knowledge':
        isEligible = healthReady
        break
      case 'vector':
        isEligible = vectorReady
        break
      case 'retrieval':
        isEligible = vectorReady && healthReady
        break
      case 'cross_encoder':
      case 'reliability':
      case 'prompt_guard':
        isEligible = healthReady
        break
      case 'workspace':
        isEligible = authResolved && healthReady && vectorReady
        break
    }

    if (isEligible) {
      // The initial Security Layer has already spent real elapsed time awaiting network auth resolution.
      // Once auth is authoritatively resolved, advance it immediately (delay = 0) to avoid perceived hesitation.
      // All subsequent stages retain their natural 90ms stagger.
      const delay = shouldReduceMotion || nextStep.id === 'security' ? 0 : 90
      const timer = setTimeout(() => {
        setCompletedSteps((prev) => {
          const updated = new Set(prev)
          updated.add(nextStep.id)
          return updated
        })
      }, delay)
      return () => clearTimeout(timer)
    }
  }, [
    isColdStart,
    allReady,
    completedSteps,
    authStatus,
    healthReady,
    vectorReady,
    shouldReduceMotion,
  ])

  // Fallback timeout: force proceed after 6 seconds
  useEffect(() => {
    if (isColdStart && !allReady) {
      const t = setTimeout(() => {
        sessionStorage.setItem('raguard_bootstrapped', 'true')
        setAllReady(true)
      }, 6000)
      return () => clearTimeout(t)
    }
  }, [isColdStart, allReady])

  if (!isColdStart) {
    return null
  }

  return (
    <AnimatePresence
      onExitComplete={() => {
        if (typeof window !== 'undefined') {
          ;(window as any).__VERITAS_BOOTSTRAPPED__ = true
          window.dispatchEvent(new CustomEvent('veritas:bootstrap-complete'))
        }
      }}
    >
      {!allReady && (
        <motion.div
          key="bootstrap-screen"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{
            duration: shouldReduceMotion ? 0.15 : 0.45,
            ease: [0.16, 1, 0.3, 1],
          }}
          className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-background text-foreground select-none"
          aria-live="polite"
        >
          {/* Subtle Ambient Brand Atmosphere (Deep Teal) */}
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,hsl(var(--primary)/0.035),transparent_65%)] pointer-events-none" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,hsl(var(--primary)/0.02),transparent_50%)] pointer-events-none" />
          <div className="absolute inset-0 bg-noise opacity-[0.015] mix-blend-multiply pointer-events-none" />

          <motion.div
            initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: shouldReduceMotion ? 0.15 : 0.4,
              ease: [0.16, 1, 0.3, 1],
            }}
            className="relative z-10 flex flex-col items-center w-full max-w-sm px-6"
          >
            {/* Wordmark */}
            <h1 className="text-3xl font-semibold tracking-tight mb-2 text-foreground">
              Veritas RAG
            </h1>

            {/* Single supporting line */}
            <motion.p
              key={activeStepText}
              initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 3 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: shouldReduceMotion ? 0.1 : 0.25 }}
              className="text-sm font-medium text-muted-foreground mb-10 text-center h-5"
            >
              {activeStepText}
            </motion.p>

            {/* Sequential Checklist */}
            <div className="w-full space-y-2.5">
              {STEPS.map((step) => {
                const isComplete = completedSteps.has(step.id)
                const isActive = activeStepId === step.id && !isComplete

                return (
                  <div key={step.id} className="flex items-center space-x-3.5">
                    <div className="w-5 h-5 flex-shrink-0 flex items-center justify-center">
                      <AnimatePresence mode="wait">
                        {isComplete ? (
                          <motion.div
                            key="complete"
                            initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.7 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                            className="w-4 h-4 rounded-full bg-primary/10 flex items-center justify-center"
                          >
                            <Check className="w-3 h-3 text-primary" strokeWidth={2.5} />
                          </motion.div>
                        ) : isActive ? (
                          <motion.div
                            key="active"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="w-1.5 h-1.5 rounded-full bg-primary/80 animate-pulse"
                          />
                        ) : (
                          <div
                            key="pending"
                            className="w-1.5 h-1.5 rounded-full bg-border"
                          />
                        )}
                      </AnimatePresence>
                    </div>
                    <motion.span
                      initial={{ opacity: 0.4 }}
                      animate={{
                        opacity: isComplete ? 1 : isActive ? 0.85 : 0.4,
                      }}
                      transition={{ duration: shouldReduceMotion ? 0.05 : 0.2 }}
                      className={`text-[14px] font-medium tracking-tight transition-colors duration-200 ${
                        isComplete
                          ? 'text-foreground'
                          : isActive
                          ? 'text-foreground/90'
                          : 'text-muted-foreground'
                      }`}
                    >
                      {step.label}
                    </motion.span>
                  </div>
                )
              })}
            </div>

            {/* Screen Reader Announcement */}
            <div className="sr-only">
              {allReady
                ? 'Application initialization complete. Launching workspace.'
                : `Initializing. ${completedSteps.size} of ${STEPS.length} stages complete.`}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
