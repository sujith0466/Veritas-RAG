import { useEffect, useState } from 'react'
import { ArrowRight, Sparkles } from 'lucide-react'
import { motion, useReducedMotion } from 'framer-motion'
import { HeroPipeline } from '../components/HeroPipeline'
import { TrustStrip } from './TrustStrip'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { MagneticButton } from '@/components/motion/MagneticButton'
import { AnimatedUnderline } from '@/components/motion/AnimatedUnderline'

import type { Variants } from 'framer-motion'

const isBootstrapped = () => {
  if (typeof window === 'undefined') return true
  try {
    return Boolean(
      (window as any).__VERITAS_BOOTSTRAPPED__ ||
      sessionStorage.getItem('raguard_bootstrapped')
    )
  } catch {
    return true
  }
}

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.05,
    },
  },
}

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: 'spring' as const, stiffness: 300, damping: 28 },
  },
}

const reducedItemVariants: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { duration: 0.15 },
  },
}

export function HeroSection() {
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((s) => s.status === 'AUTHENTICATED')
  const shouldReduceMotion = useReducedMotion()

  const [isReady, setIsReady] = useState<boolean>(() => isBootstrapped())

  useEffect(() => {
    if (isReady) return

    const handleComplete = () => {
      setIsReady(true)
    }

    window.addEventListener('veritas:bootstrap-complete', handleComplete, { once: true })

    // Safety fallback: reveal after timeout in case bootstrap was skipped or timed out
    const timer = setTimeout(() => {
      setIsReady(true)
    }, 6500)

    return () => {
      window.removeEventListener('veritas:bootstrap-complete', handleComplete)
      clearTimeout(timer)
    }
  }, [isReady])

  const handleLaunch = () => {
    navigate(isAuthenticated ? '/dashboard' : '/auth/login')
  }

  return (
    <section className="relative pt-28 pb-16 lg:pt-40 lg:pb-24 overflow-hidden">
      {/* Top gradient line */}
      <div className="absolute top-0 w-full h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      <div className="container mx-auto px-4 md:px-8 max-w-7xl relative z-10">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">

          {/* ── Left Column: Text & CTAs ── */}
          <motion.div
            className="flex flex-col items-start space-y-7 max-w-2xl"
            variants={shouldReduceMotion ? {
              hidden: { opacity: 0 },
              show: { opacity: 1, transition: { staggerChildren: 0 } },
            } : containerVariants}
            initial="hidden"
            animate={isReady ? "show" : "hidden"}
          >
            {/* Pill badge */}
            <motion.div variants={shouldReduceMotion ? reducedItemVariants : itemVariants}>
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-primary/30 bg-primary/5 text-xs font-semibold text-primary shadow-sm">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Trusted AI Infrastructure for Enterprise RAG</span>
              </div>
            </motion.div>

            {/* Headline */}
            <motion.div variants={shouldReduceMotion ? reducedItemVariants : itemVariants}>
              <h1 className="text-5xl md:text-6xl lg:text-[4.5rem] font-bold tracking-tight text-foreground leading-[1.05]">
                Build AI You Can{' '}
                <AnimatedUnderline color="hsl(175 84% 26% / 0.4)">
                  <span className="text-primary">Trust.</span>
                </AnimatedUnderline>
              </h1>
            </motion.div>

            {/* Sub-headline */}
            <motion.div variants={shouldReduceMotion ? reducedItemVariants : itemVariants}>
              <p className="text-lg md:text-xl text-muted-foreground leading-relaxed">
                The unified platform for{' '}
                <span className="text-foreground font-medium">secure</span>,{' '}
                <span className="text-foreground font-medium">explainable</span>, and{' '}
                <span className="text-foreground font-medium">hallucination-resistant</span>{' '}
                LLM applications. Ground your models in private knowledge with confidence.
              </p>
            </motion.div>

            {/* CTAs */}
            <motion.div variants={shouldReduceMotion ? reducedItemVariants : itemVariants} className="flex flex-col sm:flex-row items-start gap-3 w-full pt-1">
              <MagneticButton
                variant="primary"
                onClick={handleLaunch}
                className="w-full sm:w-auto text-base h-12 px-7 rounded-xl shadow-lg shadow-primary/20"
              >
                Launch Workspace
                <ArrowRight className="w-4 h-4 ml-2" />
              </MagneticButton>

              <MagneticButton
                variant="outline"
                className="w-full sm:w-auto text-base h-12 px-7 rounded-xl"
              >
                Request Enterprise Demo
              </MagneticButton>
            </motion.div>


            {/* Social proof numbers */}
            <motion.div
              variants={shouldReduceMotion ? reducedItemVariants : itemVariants}
              className="flex items-center gap-6 pt-2 border-t border-border/40 w-full"
            >
              {[
                { value: '10k+', label: 'Documents indexed' },
                { value: '99.2%', label: 'Grounding accuracy' },
                { value: '<250ms', label: 'P99 latency' },
              ].map((stat) => (
                <div key={stat.label} className="flex flex-col">
                  <span className="text-xl font-bold text-foreground">{stat.value}</span>
                  <span className="text-xs text-muted-foreground">{stat.label}</span>
                </div>
              ))}
            </motion.div>
          </motion.div>

          {/* ── Right Column: Pipeline Visualization ── */}
          <motion.div
            initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, x: 24 }}
            animate={isReady ? { opacity: 1, x: 0 } : { opacity: 0, x: shouldReduceMotion ? 0 : 24 }}
            transition={
              shouldReduceMotion
                ? { duration: 0.15 }
                : { duration: 0.7, delay: 0.2, ease: [0.16, 1, 0.3, 1] }
            }
            className="w-full flex items-start justify-center lg:justify-end"
          >
            <HeroPipeline className="w-full max-w-[440px]" />
          </motion.div>
        </div>

        {/* Trust strip */}
        <motion.div
          className="mt-20 pt-10 border-t border-border/40"
          initial={{ opacity: 0 }}
          animate={isReady ? { opacity: 1 } : { opacity: 0 }}
          transition={
            shouldReduceMotion
              ? { duration: 0.15 }
              : { duration: 0.6, delay: 0.45, ease: 'easeOut' }
          }
        >
          <TrustStrip />
        </motion.div>
      </div>
    </section>
  )
}
