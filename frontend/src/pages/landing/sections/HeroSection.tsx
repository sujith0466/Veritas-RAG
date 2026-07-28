import { ArrowRight, ChevronRight, Github, Sparkles } from 'lucide-react'
import { motion } from 'framer-motion'
import { HeroPipeline } from '../components/HeroPipeline'
import { TrustStrip } from './TrustStrip'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { MagneticButton } from '@/components/motion/MagneticButton'
import { AnimatedUnderline } from '@/components/motion/AnimatedUnderline'

import type { Variants } from 'framer-motion'

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.12,
      delayChildren: 0.1,
    },
  },
}

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 24 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: 'spring' as const, stiffness: 300, damping: 28 },
  },
}

export function HeroSection() {
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((s) => s.status === 'AUTHENTICATED')

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
            variants={containerVariants}
            initial="hidden"
            animate="show"
          >
            {/* Pill badge */}
            <motion.div variants={itemVariants}>
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-primary/30 bg-primary/5 text-xs font-semibold text-primary shadow-sm">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Trusted AI Infrastructure for Enterprise RAG</span>
              </div>
            </motion.div>

            {/* Headline */}
            <motion.div variants={itemVariants}>
              <h1 className="text-5xl md:text-6xl lg:text-[4.5rem] font-bold tracking-tight text-foreground leading-[1.05]">
                Build AI You Can{' '}
                <AnimatedUnderline color="hsl(175 84% 26% / 0.4)">
                  <span className="text-primary">Trust.</span>
                </AnimatedUnderline>
              </h1>
            </motion.div>

            {/* Sub-headline */}
            <motion.div variants={itemVariants}>
              <p className="text-lg md:text-xl text-muted-foreground leading-relaxed">
                The unified platform for{' '}
                <span className="text-foreground font-medium">secure</span>,{' '}
                <span className="text-foreground font-medium">explainable</span>, and{' '}
                <span className="text-foreground font-medium">hallucination-resistant</span>{' '}
                LLM applications. Ground your models in private knowledge with confidence.
              </p>
            </motion.div>

            {/* CTAs */}
            <motion.div variants={itemVariants} className="flex flex-col sm:flex-row items-start gap-3 w-full pt-1">
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

            {/* Quick links */}
            <motion.div variants={itemVariants} className="flex items-center gap-6 text-sm text-muted-foreground">
              <a
                href="#"
                className="flex items-center gap-1 hover:text-primary transition-colors group"
              >
                <ChevronRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
                Documentation
              </a>
              <a
                href="#"
                className="flex items-center gap-1.5 hover:text-primary transition-colors"
              >
                <Github className="w-4 h-4" />
                GitHub
              </a>
            </motion.div>

            {/* Social proof numbers */}
            <motion.div
              variants={itemVariants}
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
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, delay: 0.4, ease: 'easeOut' }}
            className="w-full flex items-start justify-center lg:justify-end"
          >
            <HeroPipeline className="w-full max-w-[440px]" />
          </motion.div>
        </div>

        {/* Trust strip */}
        <motion.div
          className="mt-20 pt-10 border-t border-border/40"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.9 }}
        >
          <TrustStrip />
        </motion.div>
      </div>
    </section>
  )
}
