import {
  HeartPulse,
  Activity,
  ShieldCheck,
  CheckCircle2,
  Stethoscope,
  Microscope,
} from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

export function HealthcarePage() {
  const heroVisual = (
    <div className="w-full max-w-lg rounded-2xl border border-border/70 bg-surface/80 backdrop-blur-md p-6 shadow-xl relative overflow-hidden">
      <div className="flex items-center justify-between pb-4 border-b border-border/50 mb-4">
        <span className="text-xs font-mono text-muted-foreground flex items-center gap-1.5">
          <Stethoscope className="w-3.5 h-3.5 text-primary" />
          <span>Protocol & Formulary Grounding</span>
        </span>
        <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-success/10 text-success font-medium">
          Source Faithfulness: 99.1%
        </span>
      </div>

      <div className="p-3 rounded-xl border border-border/60 bg-background/80 mb-3 text-xs font-mono text-foreground">
        <p className="text-[11px] text-muted-foreground mb-1">Clinical Protocol Query:</p>
        <p className="font-semibold">&quot;First-line dosage protocol for pediatric acute asthma exacerbation&quot;</p>
      </div>

      <div className="p-3.5 rounded-xl border border-success/30 bg-success/[0.03] space-y-2 text-xs">
        <div className="flex items-center space-x-2 text-success font-semibold">
          <CheckCircle2 className="w-4 h-4 text-success" />
          <span>Grounded Clinical Guidance:</span>
        </div>
        <p className="text-foreground/90 leading-relaxed text-[11px]">
          &quot;Administer Albuterol 2.5 mg via nebulizer every 20 min x 3 doses <span className="text-primary font-mono font-bold">[NIH Guidelines, Tab 4, p.12]</span>. Concurrently administer systemic corticosteroids (Prednisone 1-2 mg/kg) <span className="text-primary font-mono font-bold">[Formulary 2024, p.88]</span>.&quot;
        </p>
      </div>
    </div>
  )

  const solutions = [
    {
      icon: Stethoscope,
      title: 'Clinical Protocol & Standard of Care Retrieval',
      desc: 'Ground clinical staff responses in approved hospital care pathways, triage protocols, and standard operating procedures with clickable citations.',
    },
    {
      icon: Microscope,
      title: 'Pharmacological & Biomedical Literature Discovery',
      desc: 'Accelerate medical researcher literature reviews across thousands of peer-reviewed journals with zero unverified extrapolation.',
    },
    {
      icon: ShieldCheck,
      title: 'Strict Patient Privacy & Tenant Partitioning',
      desc: 'Isolated vector spaces guarantee that department-specific and institution-specific clinical records never mix or leak into cross-tenant queries.',
    },
    {
      icon: HeartPulse,
      title: 'Continuous Institutional Knowledge Retention',
      desc: 'Maintain centralized, updated institutional knowledge across distributed medical networks, ensuring rapid onboarding for clinical residents.',
    },
  ]

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="Solutions for Healthcare & Life Sciences"
        title={
          <>
            Grounded Clinical & Research Intelligence{' '}
            <span className="text-primary">You Can Verify.</span>
          </>
        }
        subtitle="Accelerate biomedical literature discovery and clinical protocol navigation with mathematical confidence scores and explicit source passage attribution."
        secondaryCtaText="Review Reliability Engine"
        secondaryCtaLink="/platform/reliability-engine"
        visual={heroVisual}
      />

      {/* Solutions Grid */}
      <section className="py-20 lg:py-28">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <FadeUp className="text-center max-w-3xl mx-auto mb-16" yOffset={20}>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-xs font-semibold text-primary mb-4">
              <Activity className="w-3.5 h-3.5" />
              <span>Evidence-Based Healthcare</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
              Zero Guesswork in Clinical Knowledge
            </h2>
            <p className="text-muted-foreground text-base md:text-lg mt-4">
              When patient outcomes are on the line, generative AI must provide verifiable provenance. Veritas RAG guarantees that every clinical reference links to verified guidelines.
            </p>
          </FadeUp>

          <Stagger className="grid grid-cols-1 md:grid-cols-2 gap-8" staggerDelay={0.1}>
            {solutions.map((s) => (
              <FadeUp key={s.title} className="p-8 rounded-2xl border border-border/60 bg-surface/70 hover:bg-surface-elevated/80 transition-all shadow-sm" yOffset={20}>
                <div className="w-12 h-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-6">
                  <s.icon className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold text-foreground mb-3">{s.title}</h3>
                <p className="text-muted-foreground leading-relaxed">{s.desc}</p>
              </FadeUp>
            ))}
          </Stagger>
        </div>
      </section>

      <MarketingCTA
        title="Ready to Elevate Healthcare AI Reliability?"
        description="Empower your medical teams with verifiable, evidence-grounded AI on sovereign infrastructure."
      />
    </div>
  )
}
