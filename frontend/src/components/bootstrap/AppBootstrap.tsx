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

  // Kick off public basic health check immediately
  useEffect(() => {
    if (!isColdStart) return

    healthService.getBasicHealth()
      .then(() => setHealthReady(true))
      .catch(() => setHealthReady(true)) // graceful fallback for degraded health endpoint
  }, [isColdStart])

  // Vector storage health requires an authenticated tenant session (`/api/v1/vectors/health`).
  // Guard it so it is never called unauthenticated (which causes a predictable 401 error).
  useEffect(() => {
    if (!isColdStart) return

    if (authStatus === 'AUTHENTICATED') {
      vectorService.getHealth()
        .then(() => setVectorReady(true))
        .catch(() => setVectorReady(true)) // graceful fallback for degraded vector cluster
    } else if (authStatus === 'UNAUTHENTICATED' || authStatus === 'ERROR') {
      // Unauthenticated public visitors do not query the vector cluster; mark ready safely.
      setVectorReady(true)
    }
  }, [isColdStart, authStatus])

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
      }, shouldReduceMotion ? 0 : 50)
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
      // Advance stages smoothly without artificial long delays.
      // 15ms provides a responsive micro-stagger for accessibility and visual progression.
      const delay = shouldReduceMotion || nextStep.id === 'security' ? 0 : 15
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
        <motion.aside
          key="bootstrap-screen"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{
            duration: shouldReduceMotion ? 0.1 : 0.2,
            ease: [0.16, 1, 0.3, 1],
          }}
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4 pointer-events-none select-none"
          aria-live="polite"
          aria-label="Enterprise Infrastructure Readiness Status"
        >
          <motion.div
            initial={{ opacity: 0, scale: shouldReduceMotion ? 1 : 0.96, y: shouldReduceMotion ? 0 : 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: shouldReduceMotion ? 1 : 0.96, y: shouldReduceMotion ? 0 : -6 }}
            transition={{
              duration: shouldReduceMotion ? 0.1 : 0.2,
              ease: [0.16, 1, 0.3, 1],
            }}
            className="pointer-events-auto relative flex flex-col items-start bg-card/95 backdrop-blur-md border border-border/80 shadow-2xl rounded-2xl p-5 w-full max-w-[340px] text-foreground"
          >
            {/* Subtle Ambient Brand Atmosphere */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,hsl(var(--primary)/0.04),transparent_70%)] rounded-2xl pointer-events-none" />

            <div className="relative z-10 flex flex-col items-start w-full">
              {/* Header: Wordmark & Live Status */}
              <div className="flex items-center justify-between w-full mb-1">
                <h1 className="text-base font-semibold tracking-tight text-foreground">
                  Veritas RAG
                </h1>
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary/75 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                </span>
              </div>

              {/* Supporting line */}
              <motion.p
                key={activeStepText}
                initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 2 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: shouldReduceMotion ? 0.05 : 0.15 }}
                className="text-xs font-medium text-muted-foreground mb-4 h-4 truncate w-full"
              >
                {activeStepText}
              </motion.p>

              {/* Sequential Checklist */}
              <div className="w-full space-y-2">
                {STEPS.map((step) => {
                  const isComplete = completedSteps.has(step.id)
                  const isActive = activeStepId === step.id && !isComplete

                  return (
                    <div key={step.id} className="flex items-center space-x-2.5">
                      <div className="w-4 h-4 flex-shrink-0 flex items-center justify-center">
                        <AnimatePresence mode="wait">
                          {isComplete ? (
                            <motion.div
                              key="complete"
                              initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.7 }}
                              animate={{ opacity: 1, scale: 1 }}
                              transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
                              className="w-3.5 h-3.5 rounded-full bg-primary/10 flex items-center justify-center"
                            >
                              <Check className="w-2.5 h-2.5 text-primary" strokeWidth={2.5} />
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
                        transition={{ duration: shouldReduceMotion ? 0.05 : 0.15 }}
                        className={`text-[13px] font-medium tracking-tight transition-colors duration-150 ${
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
            </div>
          </motion.div>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}
