import React from 'react'
import { motion, type Variants } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Sparkles } from 'lucide-react'
import { MagneticButton } from '@/components/motion/MagneticButton'
import { Button } from '@/components/common/Button'
import { useAuthStore } from '@/stores/authStore'

interface MarketingHeroProps {
  badge: string
  title: React.ReactNode
  subtitle: string
  primaryCtaText?: string
  secondaryCtaText?: string
  secondaryCtaLink?: string
  visual?: React.ReactNode
}

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
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: 'spring', stiffness: 300, damping: 28 },
  },
}

export function MarketingHero({
  badge,
  title,
  subtitle,
  primaryCtaText = 'Launch Workspace',
  secondaryCtaText,
  secondaryCtaLink,
  visual,
}: MarketingHeroProps) {
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((s) => s.status === 'AUTHENTICATED')

  const handlePrimaryClick = () => {
    navigate(isAuthenticated ? '/dashboard' : '/auth/login')
  }

  const handleSecondaryClick = () => {
    if (secondaryCtaLink) {
      if (secondaryCtaLink.startsWith('#')) {
        const el = document.getElementById(secondaryCtaLink.replace('#', ''))
        el?.scrollIntoView({ behavior: 'smooth' })
      } else {
        navigate(secondaryCtaLink)
      }
    }
  }

  return (
    <section className="relative pt-32 pb-16 lg:pt-40 lg:pb-24 overflow-hidden">
      {/* Top gradient divider */}
      <div className="absolute top-0 w-full h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      <div className="container mx-auto px-4 md:px-8 max-w-7xl relative z-10">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* Left Column: Headline and CTAs */}
          <motion.div
            className="flex flex-col items-start space-y-7 max-w-2xl"
            variants={containerVariants}
            initial="hidden"
            animate="show"
          >
            {/* Badge */}
            <motion.div variants={itemVariants}>
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-primary/30 bg-primary/5 text-xs font-semibold text-primary shadow-sm">
                <Sparkles className="w-3.5 h-3.5" />
                <span>{badge}</span>
              </div>
            </motion.div>

            {/* Title */}
            <motion.div variants={itemVariants}>
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight text-foreground leading-[1.1]">
                {title}
              </h1>
            </motion.div>

            {/* Subtitle */}
            <motion.div variants={itemVariants}>
              <p className="text-lg md:text-xl text-muted-foreground leading-relaxed">
                {subtitle}
              </p>
            </motion.div>

            {/* Actions */}
            <motion.div variants={itemVariants} className="flex flex-wrap items-center gap-4 pt-2">
              <MagneticButton
                variant="primary"
                onClick={handlePrimaryClick}
                className="text-sm font-semibold h-11 px-7 rounded-full shadow-[0_0_20px_hsl(var(--primary)/0.25)] flex items-center space-x-2"
              >
                <span>{primaryCtaText}</span>
                <ArrowRight className="w-4 h-4 ml-1.5" />
              </MagneticButton>

              {secondaryCtaText && (
                <Button
                  variant="outline"
                  onClick={handleSecondaryClick}
                  className="rounded-full px-6 h-11 border-border/80 text-foreground hover:bg-surface-elevated transition-colors"
                >
                  {secondaryCtaText}
                </Button>
              )}
            </motion.div>
          </motion.div>

          {/* Right Column: Custom Visual Diagram / Product Abstraction */}
          {visual && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ duration: 0.6, ease: 'easeOut', delay: 0.2 }}
              className="w-full flex justify-center lg:justify-end"
            >
              {visual}
            </motion.div>
          )}
        </div>
      </div>
    </section>
  )
}
