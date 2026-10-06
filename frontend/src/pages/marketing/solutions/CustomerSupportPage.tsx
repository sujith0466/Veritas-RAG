import {
  Headphones,
  MessageSquare,
  ShieldAlert,
  CheckCircle2,
  Bot,
  RefreshCw,
} from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

export function CustomerSupportPage() {
  const heroVisual = (
    <div className="w-full max-w-lg rounded-2xl border border-border/70 bg-surface/80 backdrop-blur-md p-6 shadow-xl relative overflow-hidden">
      <div className="flex items-center justify-between pb-4 border-b border-border/50 mb-4">
        <span className="text-xs font-mono text-muted-foreground flex items-center gap-1.5">
          <Bot className="w-3.5 h-3.5 text-primary" />
          <span>Agent Assist & Knowledge Verification</span>
        </span>
        <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-success/10 text-success font-medium">
          Confidence: 99.4%
        </span>
      </div>

      <div className="p-3 rounded-xl border border-border/60 bg-background/80 mb-3 text-xs font-mono text-foreground">
        <p className="text-[11px] text-muted-foreground mb-1">Customer Inquiry:</p>
        <p className="font-semibold">&quot;How do I configure SAML 2.0 SSO with Okta in my enterprise tenant?&quot;</p>
      </div>

      <div className="p-3.5 rounded-xl border border-success/30 bg-success/[0.03] space-y-2 text-xs">
        <div className="flex items-center space-x-2 text-success font-semibold">
          <CheckCircle2 className="w-4 h-4 text-success" />
          <span>Grounded Answer for Support Agent:</span>
        </div>
        <p className="text-foreground/90 leading-relaxed text-[11px]">
          &quot;Navigate to Workspace Settings &gt; Authentication &gt; SSO. Enter your Okta Entity ID and upload your X.509 certificate <span className="text-primary font-mono font-bold">[Doc-12, p.4]</span>. Attribute mappings require email and firstName <span className="text-primary font-mono font-bold">[Doc-12, p.6]</span>.&quot;
        </p>
      </div>
    </div>
  )

  const solutions = [
    {
      icon: MessageSquare,
      title: 'Automated Tier-1 Ticket Deflection',
      desc: 'Answer frequent technical and policy questions instantly using responses grounded directly in current product documentation.',
    },
    {
      icon: ShieldAlert,
      title: 'Graceful Fallback & Zero Fabrication',
      desc: 'When an answer is not present in approved documentation, Veritas RAG honestly flags missing knowledge instead of inventing instructions.',
    },
    {
      icon: RefreshCw,
      title: 'Real-Time Knowledge Base Synchronization',
      desc: 'Documentation updates and release notes reflect immediately in retrieval indexes, preventing stale support answers.',
    },
    {
      icon: Headphones,
      title: 'Agent-Assist Copilot with Verified Coordinates',
      desc: 'Equip human support agents with suggested answers and clickable source links, accelerating resolution times by 4x.',
    },
  ]

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="Solutions for Customer Support & Operations"
        title={
          <>
            Support Answers Grounded Exclusively in{' '}
            <span className="text-primary">Your Official Documentation.</span>
          </>
        }
        subtitle="Eliminate outdated answers and generative drift. If an answer cannot be grounded in approved knowledge, Veritas RAG admits knowledge absence instead of guessing."
        secondaryCtaText="See Knowledge Intelligence"
        secondaryCtaLink="/platform/knowledge-intelligence"
        visual={heroVisual}
      />

      {/* Solutions Grid */}
      <section className="py-20 lg:py-28">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <FadeUp className="text-center max-w-3xl mx-auto mb-16" yOffset={20}>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-xs font-semibold text-primary mb-4">
              <Headphones className="w-3.5 h-3.5" />
              <span>Customer Success & Operations</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
              Turn Documentation into Trustworthy Automation
            </h2>
            <p className="text-muted-foreground text-base md:text-lg mt-4">
              Incorrect customer support answers erode brand trust and create liabilities. Veritas RAG guarantees that automated replies stay 100% faithful to current product docs.
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
        title="Ready to Automate Customer Support Safely?"
        description="Deploy grounded knowledge assistance that respects document boundaries and eliminates customer hallucinations."
      />
    </div>
  )
}
