import { Terminal, LayoutTemplate, Network, ShieldCheck } from 'lucide-react'
import { SectionHeading } from '@/components/landing/SectionHeading'
import { GlassCard } from '@/components/landing/GlassCard'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

const PERSONAS = [
  {
    title: 'AI Engineers',
    icon: Terminal,
    description: 'Focus on building great models, not debugging retrieval pipelines. RAGuard provides instant visibility into chunk quality, embedding drift, and hallucination rates.'
  },
  {
    title: 'Platform Teams',
    icon: LayoutTemplate,
    description: 'Standardize AI deployments across the organization. Deliver a unified, multi-tenant RAG infrastructure that scales effortlessly without creating operational silos.'
  },
  {
    title: 'Enterprise Architects',
    icon: Network,
    description: 'Design future-proof systems. Seamlessly integrate with existing data lakes, identity providers, and compliance frameworks using our headless API architecture.'
  },
  {
    title: 'Security Teams',
    icon: ShieldCheck,
    description: 'Maintain absolute control over enterprise data. Enforce strict RBAC, generate comprehensive audit trails, and guarantee tenant isolation by default.'
  }
]

export function UseCases() {
  return (
    <section className="py-24 relative overflow-hidden bg-background">
      <div className="container mx-auto px-4 md:px-8 max-w-7xl">
        <FadeUp>
          <SectionHeading
            title="Built for Enterprise AI Teams."
            subtitle="A unified platform that aligns engineering velocity with enterprise governance."
            className="mb-16"
          />
        </FadeUp>

        <Stagger className="grid md:grid-cols-2 gap-6 lg:gap-8" staggerDelay={0.1}>
          {PERSONAS.map((persona) => (
            <FadeUp key={persona.title} yOffset={20}>
              <GlassCard padding="lg" interactive className="h-full group hover:border-primary/30 transition-colors cursor-default">
                <div className="flex items-start space-x-6">
                  <div className="w-12 h-12 rounded-xl bg-surface-elevated border border-border/40 flex items-center justify-center text-foreground group-hover:text-primary transition-colors shrink-0">
                    <persona.icon className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-foreground mb-3">{persona.title}</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {persona.description}
                    </p>
                  </div>
                </div>
              </GlassCard>
            </FadeUp>
          ))}
        </Stagger>
      </div>
    </section>
  )
}
