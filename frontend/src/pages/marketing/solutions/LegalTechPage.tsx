import {
  Scale,
  FileText,
  ShieldCheck,
  CheckCircle2,
  Gavel,
  CheckCheck,
} from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

export function LegalTechPage() {
  const heroVisual = (
    <div className="w-full max-w-lg rounded-2xl border border-border/70 bg-surface/80 backdrop-blur-md p-6 shadow-xl relative overflow-hidden">
      <div className="flex items-center justify-between pb-4 border-b border-border/50 mb-4">
        <span className="text-xs font-mono text-muted-foreground flex items-center gap-1.5">
          <Scale className="w-3.5 h-3.5 text-primary" />
          <span>Pinpoint Passage Attribution</span>
        </span>
        <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-success/10 text-success font-medium">
          Contract Verified
        </span>
      </div>

      <div className="p-3 rounded-xl border border-border/60 bg-background/80 mb-3 text-xs font-mono text-foreground">
        <p className="text-[11px] text-muted-foreground mb-1">Covenant Analysis Query:</p>
        <p className="font-semibold">&quot;Identify change of control restrictions in the 2023 Credit Facility&quot;</p>
      </div>

      <div className="p-3.5 rounded-xl border border-success/30 bg-success/[0.03] space-y-2 text-xs">
        <div className="flex items-center space-x-2 text-success font-semibold">
          <CheckCircle2 className="w-4 h-4 text-success" />
          <span>Extracted Clause with Verifiable Coordinates:</span>
        </div>
        <p className="text-foreground/90 leading-relaxed text-[11px]">
          &quot;Under Section 8.02(b) <span className="text-primary font-mono font-bold">[Credit Agreement, p.104]</span>, Borrower shall not consummate any Change of Control without prior written consent from 66.7% of Required Lenders <span className="text-primary font-mono font-bold">[Definitions, p.12]</span>.&quot;
        </p>
      </div>
    </div>
  )

  const solutions = [
    {
      icon: FileText,
      title: 'Contract Clause & Covenant Extraction',
      desc: 'Rapidly discover indemnities, non-compete terms, and termination clauses across thousands of complex agreements with character-level passage grounding.',
    },
    {
      icon: Gavel,
      title: 'Litigation Discovery & Case Law Search',
      desc: 'Combine BM25 keyword precision with dense semantic understanding to find relevant precedents without missing exact legal citations.',
    },
    {
      icon: ShieldCheck,
      title: 'Zero Cross-Client Matter Contamination',
      desc: 'Strict multi-tenant architecture ensures that client documents, depositions, and privileged work product remain strictly separated by matter ID.',
    },
    {
      icon: CheckCheck,
      title: 'Auditable Legal Provenance',
      desc: 'Every generated summary includes clickable links directly to exact source PDF pages and paragraphs, empowering counsel to verify quotes in seconds.',
    },
  ]

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="Solutions for Legal & Compliance"
        title={
          <>
            Pinpoint Passage Attribution for{' '}
            <span className="text-primary">High-Stakes Contract Analysis.</span>
          </>
        }
        subtitle="Empower legal counsel with exact clause matching, cross-agreement comparisons, and zero cross-client knowledge leakage."
        secondaryCtaText="See Hybrid Retrieval"
        secondaryCtaLink="/platform/hybrid-retrieval"
        visual={heroVisual}
      />

      {/* Solutions Grid */}
      <section className="py-20 lg:py-28">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <FadeUp className="text-center max-w-3xl mx-auto mb-16" yOffset={20}>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-xs font-semibold text-primary mb-4">
              <Scale className="w-3.5 h-3.5" />
              <span>Legal Precision & Evidentiary Rigor</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
              Built for Attorneys Who Demand Exact Citations
            </h2>
            <p className="text-muted-foreground text-base md:text-lg mt-4">
              Legal review cannot tolerate approximate or hallucinated citations. Veritas RAG provides transparent, verifiable passage coordinates for every claim.
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
        title="Ready to Supercharge Legal Research?"
        description="Experience deterministic clause extraction and zero cross-client data contamination."
      />
    </div>
  )
}
