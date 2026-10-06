import { FileCheck } from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'

export function PrivacyPolicyPage() {
  const sections = [
    {
      title: '1. Customer Data Ownership & Non-Training Guarantee',
      content: `Veritas RAG operates on an absolute principle: your proprietary data belongs exclusively to you. 
We strictly guarantee that your documents, extracted chunks, dense vector embeddings, and user chat conversations are NEVER used to train, retrain, fine-tune, or calibrate public or foundation LLM models. 
Any interactions with third-party LLM providers (e.g., OpenRouter or Google Gemini) use zero-data-retention enterprise API contracts.`,
    },
    {
      title: '2. Multi-Tenant Logical & Physical Isolation',
      content: `Every enterprise workspace in Veritas RAG is logically and physically partitioned. 
Vector embeddings are indexed in tenant-dedicated collections (raguard_knowledge_{tenant_id}). 
Database tables enforce strict tenant_id constraints on every SQL execution. 
Under no circumstances can an authenticated user from one tenant view, search, or retrieve vectors belonging to another tenant.`,
    },
    {
      title: '3. Data Ingestion, Storage, and Lifecycle',
      content: `Uploaded files are parsed into semantic chunks and stored within your designated storage backend (e.g., MinIO or AWS S3). 
When an administrator requests document purging or deletion, our pipeline performs atomic synchronization: 
the document record is deleted from PostgreSQL, the corresponding vector points are purged from Qdrant, and the raw object artifact is removed from object storage.`,
    },
    {
      title: '4. Ephemeral Credentials & Authentication Data',
      content: `User authentication credentials, passwords, and API secrets are never stored in plaintext. 
Passwords are encrypted using industry-standard bcrypt hashing. 
Workspace Join Codes are cryptographically signed with admin-configured expiration dates (1–60 days or Never) and can be revoked instantaneously.`,
    },
    {
      title: '5. Telemetry, Audit Logs, and Analytics',
      content: `Operational logs are collected solely for system health, error monitoring, and tenant auditing. 
All logs containing request traces redact personal identifiable information (PII) and bearer authentication tokens. 
Tenants have full visibility into their own audit logs without telemetry sharing.`,
    },
    {
      title: '6. Self-Hosted & Private Cloud Deployments',
      content: `For organizations with strict data residency mandates (such as HIPAA, GDPR, or financial regulations), Veritas RAG supports self-hosted deployment via Docker Compose on your own private cloud or sovereign data center. 
In self-hosted configurations, zero data leaves your local network perimeter.`,
    },
  ]

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="Enterprise Privacy & Data Protection"
        title={
          <>
            Privacy Policy &{' '}
            <span className="text-primary">Customer Data Commitments.</span>
          </>
        }
        subtitle="Effective October 2026. Veritas RAG guarantees complete customer data sovereignty, non-training commitments, and physical tenant isolation."
        secondaryCtaText="Review Terms of Service"
        secondaryCtaLink="/terms"
      />

      {/* Policy Content */}
      <section className="py-20 lg:py-28 border-t border-border/40">
        <div className="container mx-auto px-4 md:px-8 max-w-4xl">
          <div className="p-8 md:p-12 rounded-3xl border border-border/60 bg-surface/80 shadow-sm space-y-10">
            <div className="border-b border-border/50 pb-6">
              <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">Version 2.4 &bull; Last Revised: October 2026</span>
              <p className="text-sm text-foreground/80 mt-2 leading-relaxed">
                This Enterprise Privacy Policy outlines the strict data handling practices of Veritas RAG, Inc. governing all interactions with our software platform, vector services, and APIs.
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
              <span>Have privacy questions? Reach out to privacy@veritas-rag.ai</span>
              <div className="flex items-center space-x-2 text-primary font-medium">
                <FileCheck className="w-4 h-4" />
                <span>Enterprise Verified</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <MarketingCTA
        title="Ready to Build with Full Data Sovereignty?"
        description="Deploy Veritas RAG on your private infrastructure and guarantee complete privacy for your sensitive enterprise knowledge."
      />
    </div>
  )
}
