import { ShieldCheck } from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'

export function TermsPage() {
  const sections = [
    {
      title: '1. Acceptance of Terms & Workspace Onboarding',
      content: `By creating an account, accessing a workspace via Join Code, or utilizing the Veritas RAG APIs, you agree to be bound by these Enterprise Terms of Service. 
If you are entering into this agreement on behalf of a company or other legal entity, you represent that you have the authority to bind such entity to these terms.`,
    },
    {
      title: '2. Workspace Administration & Ephemeral Join Access',
      content: `Workspace Administrators are responsible for the management of member roles (Admin, Member, Viewer) and the configuration of Join Code expiration lifecycles. 
Administrators must ensure that Join Codes are shared solely with authorized personnel. 
Veritas RAG reserves the right to terminate access if unauthorized credential sharing compromises multi-tenant integrity.`,
    },
    {
      title: '3. Acceptable Use Policy',
      content: `You agree not to use Veritas RAG to:
• Ingest or process malicious payloads, malware, or illegal content.
• Attempt prompt injection attacks designed to extract cross-tenant vector embeddings.
• Reverse-engineer, decompile, or disassemble the proprietary cross-encoder or reflection loop algorithms.
• Violate the intellectual property or confidentiality rights of any third party.`,
    },
    {
      title: '4. Intellectual Property & Customer Ownership',
      content: `All intellectual property rights in your uploaded documents, customer vector databases, and private embeddings remain exclusively yours. 
Veritas RAG retains all intellectual property rights in the software platform, user interface designs, algorithmic workflows, and related trademarks.`,
    },
    {
      title: '5. Limitation of Liability & Disclaimers',
      content: `Veritas RAG provides high-accuracy retrieval and hallucination mitigation guardrails; however, generative outputs must be reviewed by qualified human personnel for mission-critical legal, medical, or financial execution. 
Except where prohibited by law, Veritas RAG shall not be liable for indirect, incidental, or consequential damages resulting from generative model responses.`,
    },
    {
      title: '6. Modifications to Terms',
      content: `We may revise these Terms from time to time. If a revision meaningfully impacts your tenant rights, we will notify administrators via the workspace dashboard or email at least 30 days prior to the effective date.`,
    },
  ]

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="Enterprise Terms & Conditions"
        title={
          <>
            Terms of Service &{' '}
            <span className="text-primary">Master Subscription Agreement.</span>
          </>
        }
        subtitle="Governing your use of the Veritas RAG platform, software components, and enterprise APIs."
        secondaryCtaText="Review Privacy Policy"
        secondaryCtaLink="/privacy"
      />

      {/* Terms Content */}
      <section className="py-20 lg:py-28 border-t border-border/40">
        <div className="container mx-auto px-4 md:px-8 max-w-4xl">
          <div className="p-8 md:p-12 rounded-3xl border border-border/60 bg-surface/80 shadow-sm space-y-10">
            <div className="border-b border-border/50 pb-6">
              <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">Version 2.1 &bull; Effective Date: October 2026</span>
              <p className="text-sm text-foreground/80 mt-2 leading-relaxed">
                These terms govern your access to the Veritas RAG software platform, cloud instances, and local deployments.
              </p>
            </div>

            {sections.map((s) => (
              <div key={s.title} className="space-y-3">
                <h3 className="text-xl font-bold text-foreground tracking-tight">{s.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-line">
                  {s.content}
                </p>
              </div>
            ))}

            <div className="pt-6 border-t border-border/50 flex flex-col sm:flex-row items-center justify-between text-xs text-muted-foreground gap-4">
              <span>Questions regarding licensing? Contact legal@veritas-rag.ai</span>
              <div className="flex items-center space-x-2 text-primary font-medium">
                <ShieldCheck className="w-4 h-4" />
                <span>Legally Binding</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <MarketingCTA
        title="Ready to Build AI You Can Trust?"
        description="Launch your workspace with enterprise-grade security, deterministic citations, and complete data ownership."
      />
    </div>
  )
}
