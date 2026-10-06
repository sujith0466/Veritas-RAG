import {
  TrendingUp,
  FileSpreadsheet,
  Building2,
  ShieldCheck,
  CheckCircle2,
  BarChart3,
} from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

export function FinancialServicesPage() {
  const heroVisual = (
    <div className="w-full max-w-lg rounded-2xl border border-border/70 bg-surface/80 backdrop-blur-md p-6 shadow-xl relative overflow-hidden">
      <div className="flex items-center justify-between pb-4 border-b border-border/50 mb-4">
        <span className="text-xs font-mono text-muted-foreground flex items-center gap-1.5">
          <FileSpreadsheet className="w-3.5 h-3.5 text-primary" />
          <span>Filing Synthesis & Verification</span>
        </span>
        <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-success/10 text-success font-medium">
          SEC 10-K Verified
        </span>
      </div>

      <div className="p-3 rounded-xl border border-border/60 bg-background/80 mb-3 text-xs font-mono text-foreground">
        <p className="text-[11px] text-muted-foreground mb-1">Query:</p>
        <p className="font-semibold">&quot;Summarize Q4 FY24 EBITDA margin compression factors&quot;</p>
      </div>

      <div className="p-3.5 rounded-xl border border-success/30 bg-success/[0.03] space-y-2 text-xs">
        <div className="flex items-center space-x-2 text-success font-semibold">
          <CheckCircle2 className="w-4 h-4 text-success" />
          <span>Grounded Financial Synthesis:</span>
        </div>
        <p className="text-foreground/90 leading-relaxed text-[11px]">
          &quot;Operating margin declined by 180 bps YoY to 24.2% <span className="text-primary font-mono font-bold">[10-K, Item 7, p.42]</span> driven by 14% higher supply chain logistics costs <span className="text-primary font-mono font-bold">[Note 14, p.89]</span>.&quot;
        </p>
      </div>
    </div>
  )

  const solutions = [
    {
      icon: FileSpreadsheet,
      title: 'SEC Filing & Earnings Synthesis',
      desc: 'Rapidly parse 10-K, 10-Q, and 8-K filings with zero hallucination on critical financial ratios, table numbers, and footnote disclosures.',
    },
    {
      icon: Building2,
      title: 'M&A Virtual Deal Rooms',
      desc: 'Enforce mathematical multi-tenant separation. Confidential target acquisition documents remain strictly isolated between investment teams.',
    },
    {
      icon: ShieldCheck,
      title: 'Regulatory & Risk Compliance Auditing',
      desc: 'Cross-reference internal trading and lending policies against evolving global regulatory frameworks with transparent passage citations.',
    },
    {
      icon: BarChart3,
      title: 'Equity Research & Macro Trend Analysis',
      desc: 'Synthesize thousands of sell-side research notes and transcripts simultaneously with exact paragraph attribution and confidence scoring.',
    },
  ]

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="Solutions for Financial Services"
        title={
          <>
            Auditable Generative Intelligence for{' '}
            <span className="text-primary">Investment & Risk Teams.</span>
          </>
        }
        subtitle="Extract actionable insights from complex filings and research notes with verifiable numeric citation grounding and zero model fabrication."
        secondaryCtaText="Explore Platform Security"
        secondaryCtaLink="/platform/security"
        visual={heroVisual}
      />

      {/* Solutions Grid */}
      <section className="py-20 lg:py-28">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <FadeUp className="text-center max-w-3xl mx-auto mb-16" yOffset={20}>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-xs font-semibold text-primary mb-4">
              <TrendingUp className="w-3.5 h-3.5" />
              <span>Capital Markets & Banking</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
              Eliminate Financial Hallucination Risk
            </h2>
            <p className="text-muted-foreground text-base md:text-lg mt-4">
              In financial decision-making, a hallucinated decimal point or fabricated margin figure is disastrous. Veritas RAG ensures every number is mathematically grounded.
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
        title="Ready to Transform Financial Research?"
        description="Deploy auditable, hallucination-resistant knowledge intelligence across your investment committees and risk divisions."
      />
    </div>
  )
}
