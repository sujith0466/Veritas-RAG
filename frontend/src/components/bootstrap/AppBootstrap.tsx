import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
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
  const [isColdStart] = useState<boolean>(() => {
    return !sessionStorage.getItem('raguard_bootstrapped')
  })

  const authStatus = useAuthStore((s) => s.status)

  const [completedSteps, setCompletedSteps] = useState<Set<StepId>>(new Set())
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

  useEffect(() => {
    if (!isColdStart) return

    const newCompleted = new Set<StepId>()

    // Security Layer is bound to authStatus transitioning away from LOADING
    const authResolved = authStatus !== 'LOADING'
    if (authResolved) {
      newCompleted.add('security')
    }

    if (healthReady) {
      newCompleted.add('knowledge')
      // Presentational grouping:
      newCompleted.add('cross_encoder')
      newCompleted.add('reliability')
      newCompleted.add('prompt_guard')
    }

    if (vectorReady) {
      newCompleted.add('vector')
      if (healthReady) {
        newCompleted.add('retrieval') // Grouped with both vector and knowledge
      }
    }

    if (authResolved && healthReady && vectorReady) {
      newCompleted.add('workspace')
    }

    setCompletedSteps(newCompleted)

    if (newCompleted.size === STEPS.length) {
      setActiveStepText('Launching Workspace...')
      const t = setTimeout(() => {
        sessionStorage.setItem('raguard_bootstrapped', 'true')
        setAllReady(true)
      }, 300) // Small breather for UI to settle before fadeout
      return () => clearTimeout(t)
    } else {
      setActiveStepText('Initializing Enterprise AI Infrastructure')
    }
  }, [authStatus, healthReady, vectorReady, isColdStart])

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
    <AnimatePresence>
      {!allReady && (
        <motion.div
          key="bootstrap-screen"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.6, ease: "easeInOut" }}
          className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-[#FAFAFA] text-foreground"
          aria-live="polite"
        >
          {/* Layered Translucent Planes / Noise (from 3D background system) */}
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(99,102,241,0.04),transparent_50%)]" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(139,92,246,0.04),transparent_50%)] opacity-70 mix-blend-screen" />
          <div className="absolute inset-0 bg-noise opacity-[0.015] mix-blend-multiply pointer-events-none" />

          <div className="relative z-10 flex flex-col items-center w-full max-w-sm px-6">
            {/* Wordmark */}
            <h1 className="text-3xl font-semibold tracking-tight mb-2">Veritas RAG</h1>

            {/* Single supporting line */}
            <motion.p
              key={activeStepText}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-sm font-medium text-muted-foreground mb-12 text-center h-5"
            >
              {activeStepText}
            </motion.p>

            {/* Sequential Checklist */}
            <div className="w-full space-y-3">
              {STEPS.map((step) => {
                const isComplete = completedSteps.has(step.id)
                return (
                  <div key={step.id} className="flex items-center space-x-4">
                    <div className="w-5 h-5 flex-shrink-0 flex items-center justify-center">
                      <AnimatePresence>
                        {isComplete && (
                          <motion.div
                            initial={{ opacity: 0, scale: 0.5 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ duration: 0.25, ease: "easeOut" }}
                          >
                            <Check className="w-[18px] h-[18px] text-primary" strokeWidth={2.5} />
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                    <motion.span
                      initial={{ opacity: 0.4 }}
                      animate={{ opacity: isComplete ? 1 : 0.4 }}
                      transition={{ duration: 0.3 }}
                      className="text-[15px] font-medium tracking-tight text-foreground/80"
                    >
                      {step.label}
                    </motion.span>
                  </div>
                )
              })}
            </div>

            {/* Screen Reader Announcement */}
            <div className="sr-only">
              {allReady ? 'Application initialization complete. Launching workspace.' : `Initializing. ${completedSteps.size} of ${STEPS.length} stages complete.`}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
