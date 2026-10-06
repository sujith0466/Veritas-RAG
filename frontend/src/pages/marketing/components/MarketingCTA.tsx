import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, ShieldCheck, CheckCircle2 } from 'lucide-react'
import { MagneticButton } from '@/components/motion/MagneticButton'
import { useAuthStore } from '@/stores/authStore'

interface MarketingCTAProps {
  title?: string
  description?: string
  primaryCtaText?: string
}

export function MarketingCTA({
  title = 'Ready to Build AI You Can Trust?',
  description = 'Deploy hallucination-resistant knowledge intelligence across your enterprise. Multi-tenant isolation, verifiable citations, and hybrid retrieval ready out-of-the-box.',
  primaryCtaText = 'Launch Workspace',
}: MarketingCTAProps) {
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((s) => s.status === 'AUTHENTICATED')

  const handleLaunch = () => {
    navigate(isAuthenticated ? '/dashboard' : '/auth/login')
  }

  return (
    <section className="py-20 lg:py-28 relative overflow-hidden border-t border-border/40">
      <div className="container mx-auto px-4 md:px-8 max-w-7xl relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="relative rounded-3xl border border-primary/20 bg-gradient-to-br from-surface via-surface to-primary/5 p-8 md:p-14 lg:p-16 shadow-xl shadow-primary/5 text-center flex flex-col items-center overflow-hidden"
        >
          {/* Subtle glowing halo */}
          <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent" />
          <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-96 h-96 bg-primary/10 rounded-full blur-3xl pointer-events-none" />

          {/* Icon Badge */}
          <div className="w-12 h-12 rounded-2xl bg-primary/10 text-primary border border-primary/20 flex items-center justify-center mb-6 shadow-sm">
            <ShieldCheck className="w-6 h-6" />
          </div>

          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold tracking-tight text-foreground max-w-3xl mb-5">
            {title}
          </h2>

          <p className="text-base md:text-lg text-muted-foreground max-w-2xl leading-relaxed mb-8">
            {description}
          </p>

          <div className="flex flex-col sm:flex-row items-center gap-4 mb-10">
            <MagneticButton
              variant="primary"
              onClick={handleLaunch}
              className="text-sm font-semibold h-12 px-8 rounded-full shadow-[0_0_24px_hsl(var(--primary)/0.3)] flex items-center space-x-2"
            >
              <span>{primaryCtaText}</span>
              <ArrowRight className="w-4 h-4 ml-2" />
            </MagneticButton>
          </div>

          {/* Guarantees */}
          <div className="flex flex-wrap justify-center items-center gap-6 md:gap-10 text-xs md:text-sm text-muted-foreground pt-6 border-t border-border/40 w-full max-w-2xl">
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-primary" />
              <span>Zero Cross-Tenant Contamination</span>
            </div>
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-primary" />
              <span>Autonomous Self-Correction</span>
            </div>
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-primary" />
              <span>Verifiable Passage Citations</span>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
