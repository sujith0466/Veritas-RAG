import { motion } from 'framer-motion'
import { useState, useEffect } from 'react'
import { CheckCircle2, Loader2 } from 'lucide-react'

const STEPS = [
  'Verifying Identity',
  'Connecting Workspace',
  'Loading Knowledge Base',
  'Preparing AI Services',
  'Opening Dashboard'
]

interface WorkspaceLoaderProps {
  onComplete?: () => void
}

export function WorkspaceLoader({ onComplete }: WorkspaceLoaderProps) {
  const [currentStep, setCurrentStep] = useState(0)
  
  useEffect(() => {
    const runSequence = async () => {
      for (let i = 0; i < STEPS.length; i++) {
        await new Promise(resolve => setTimeout(resolve, 600)) // 600ms per step
        setCurrentStep(i + 1)
      }
      await new Promise(resolve => setTimeout(resolve, 400))
      if (onComplete) {
        onComplete()
      }
    }
    runSequence()
  }, [onComplete])

  return (
    <div className="flex flex-col items-center justify-center space-y-8 w-full">
      <div className="text-center">
        <h2 className="text-2xl font-semibold text-foreground tracking-tight mb-2">
          Preparing Workspace
        </h2>
        <p className="text-sm text-muted-foreground">
          Establishing secure environment
        </p>
      </div>

      <div className="w-full max-w-xs space-y-4">
        {STEPS.map((step, idx) => {
          const isComplete = currentStep > idx
          const isActive = currentStep === idx
          const isPending = currentStep < idx

          return (
            <motion.div
              key={step}
              initial={{ opacity: 0, x: -10 }}
              animate={{ 
                opacity: isPending ? 0.4 : 1, 
                x: 0,
                color: isComplete ? 'var(--foreground)' : isActive ? 'var(--primary)' : 'var(--muted-foreground)'
              }}
              className="flex items-center space-x-3 text-sm font-medium"
            >
              <div className="w-5 h-5 flex items-center justify-center shrink-0">
                {isComplete ? (
                  <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring' }}>
                    <CheckCircle2 className="w-5 h-5 text-primary" />
                  </motion.div>
                ) : isActive ? (
                  <Loader2 className="w-4 h-4 animate-spin text-primary" />
                ) : (
                  <div className="w-2 h-2 rounded-full bg-muted-foreground/30" />
                )}
              </div>
              <span className={isComplete ? "text-foreground" : isActive ? "text-primary" : "text-muted-foreground"}>
                {step}
              </span>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
