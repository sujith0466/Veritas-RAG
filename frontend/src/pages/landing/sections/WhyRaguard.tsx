import { CheckCircle2, XCircle } from 'lucide-react'
import { motion } from 'framer-motion'
import { SectionHeading } from '@/components/landing/SectionHeading'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

const COMPARISON_DATA = [
  { traditional: 'Basic Retrieval', raguard: 'Hybrid Retrieval' },
  { traditional: 'Generic Responses', raguard: 'Grounded Responses' },
  { traditional: 'Limited Explainability', raguard: 'Source Attribution' },
  { traditional: 'Static Pipelines', raguard: 'Reflection Engine' },
  { traditional: 'Minimal Monitoring', raguard: 'Reliability Dashboard' },
  { traditional: 'Basic Security', raguard: 'Enterprise RBAC & Audit Logs' },
]

export function WhyRaguard() {
  return (
    <section className="py-24 border-t border-border relative overflow-hidden bg-background">
      <div className="container mx-auto px-4 md:px-8 max-w-5xl relative z-10">
        <FadeUp>
          <SectionHeading
            title="Why RAGuard AI?"
            subtitle="Differentiate your infrastructure with enterprise-grade reliability."
            className="mb-16"
          />
        </FadeUp>

        <div className="grid md:grid-cols-2 gap-0 rounded-2xl overflow-hidden border border-border shadow-md">

          {/* Traditional RAG Column */}
          <div className="bg-surface p-8 md:p-10 border-b md:border-b-0 md:border-r border-border">
            <h3 className="text-xl font-medium text-muted-foreground mb-8 text-center md:text-left">
              Traditional RAG
            </h3>
            <Stagger className="space-y-6" staggerDelay={0.05}>
              {COMPARISON_DATA.map((row, i) => (
                <motion.li
                  key={`trad-${i}`}
                  variants={{ hidden: {opacity:0, x:-10}, show: {opacity:1, x:0} }}
                  className="flex items-center space-x-3 text-muted-foreground"
                >
                  <XCircle className="w-5 h-5 opacity-50 shrink-0" />
                  <span>{row.traditional}</span>
                </motion.li>
              ))}
            </Stagger>
          </div>

          {/* RAGuard AI Column */}
          <div className="bg-surface-elevated p-8 md:p-10 relative">
            <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-transparent via-primary/50 to-transparent md:hidden" />
            <h3 className="text-xl font-bold text-foreground mb-8 text-center md:text-left flex items-center justify-center md:justify-start space-x-2">
              <span className="w-2 h-2 rounded-full bg-primary" />
              <span>RAGuard AI</span>
            </h3>
            <Stagger className="space-y-6" staggerDelay={0.05}>
              {COMPARISON_DATA.map((row, i) => (
                <motion.li
                  key={`raguard-${i}`}
                  variants={{ hidden: {opacity:0, x:10}, show: {opacity:1, x:0} }}
                  className="flex items-center space-x-3 text-foreground font-medium"
                >
                  <CheckCircle2 className="w-5 h-5 text-primary shrink-0" />
                  <span>{row.raguard}</span>
                </motion.li>
              ))}
            </Stagger>
          </div>

        </div>
      </div>
    </section>
  )
}
