import { Shield, Lock, FileKey, Server, Key, Eye, CheckCircle } from 'lucide-react'
import { SectionHeading } from '@/components/landing/SectionHeading'
import { GlassCard } from '@/components/landing/GlassCard'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

const SECURITY_FEATURES = [
  { label: 'Granular RBAC', icon: Key },
  { label: 'End-to-End Encryption', icon: Lock },
  { label: 'Comprehensive Audit Logs', icon: FileKey },
  { label: 'Strict Tenant Isolation', icon: Server },
  { label: 'Secure Hybrid Retrieval', icon: Shield },
  { label: '100% Explainability', icon: Eye },
  { label: 'Enterprise Governance', icon: CheckCircle },
]

export function SecurityCompliance() {
  return (
    <section id="security" className="py-24 relative overflow-hidden bg-background">

      <div className="container mx-auto px-4 md:px-8 max-w-7xl relative z-10">
        <div className="grid lg:grid-cols-2 gap-16 items-center">

          {/* Text Content */}
          <div className="max-w-2xl">
            <FadeUp>
              <SectionHeading
                title="Security First. Always."
                subtitle="Your data is your most valuable asset. Veritas RAG is engineered from the ground up to exceed the strictest enterprise security and compliance requirements."
                align="left"
                className="mb-8"
              />
            </FadeUp>

            <FadeUp delay={0.1}>
              <p className="text-lg text-muted-foreground leading-relaxed mb-8">
                We guarantee that private knowledge never leaks across tenant boundaries. Our strict Role-Based Access Control (RBAC) ensures users only retrieve context they are explicitly authorized to view, completely eliminating cross-contamination in LLM generation.
              </p>
            </FadeUp>

            <FadeUp delay={0.2}>
              <a href="#" className="inline-flex items-center justify-center px-6 py-3 rounded-md bg-surface border border-border text-foreground font-medium hover:bg-muted transition-colors outline-none focus-visible:ring-2 focus-visible:ring-primary shadow-sm">
                View Security Brief
              </a>
            </FadeUp>
          </div>

          {/* Grid of Security Badges */}
          <Stagger className="grid grid-cols-1 sm:grid-cols-2 gap-4" staggerDelay={0.06} initialDelay={0.1}>
            {SECURITY_FEATURES.map((feature) => (
              <GlassCard
                key={feature.label}
                padding="sm"
                interactive
                className="flex items-center space-x-4 bg-surface hover:bg-surface-elevated"
              >
                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary shrink-0">
                  <feature.icon className="w-5 h-5" />
                </div>
                <span className="font-medium text-foreground text-sm">{feature.label}</span>
              </GlassCard>
            ))}
          </Stagger>

        </div>
      </div>
    </section>
  )
}
