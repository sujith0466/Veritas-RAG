import {
  Shield,
  Lock,
  KeyRound,
  Users,
  Database,
  Eye,
  CheckCircle2,
  FileText,
  Clock,
  Server,
} from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

export function EnterpriseSecurityPage() {
  const heroVisual = (
    <div className="w-full max-w-lg rounded-2xl border border-border/70 bg-surface/80 backdrop-blur-md p-6 shadow-xl relative overflow-hidden">
      <div className="flex items-center justify-between pb-4 border-b border-border/50 mb-4">
        <div className="flex items-center space-x-2">
          <Shield className="w-4 h-4 text-primary" />
          <span className="text-xs font-semibold text-foreground">Multi-Tenant Isolation Fortress</span>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
          Zero Leakage SLA
        </span>
      </div>

      {/* Layered Security Diagram */}
      <div className="space-y-3">
        <div className="p-3 rounded-xl border border-border/50 bg-background/50 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Lock className="w-4 h-4 text-primary" />
            <div>
              <p className="text-xs font-semibold text-foreground">Layer 1: JWT & Session Integrity</p>
              <p className="text-[11px] text-muted-foreground">Short-lived access tokens with secure refresh</p>
            </div>
          </div>
          <span className="text-[10px] font-mono text-muted-foreground">TLS 1.3</span>
        </div>

        <div className="p-3 rounded-xl border border-border/50 bg-background/50 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <KeyRound className="w-4 h-4 text-info" />
            <div>
              <p className="text-xs font-semibold text-foreground">Layer 2: Ephemeral Join Codes</p>
              <p className="text-[11px] text-muted-foreground">Admin-controlled 1–60 day auto-expiration</p>
            </div>
          </div>
          <span className="text-[10px] font-mono text-info font-medium">Active</span>
        </div>

        <div className="p-3 rounded-xl border border-border/50 bg-background/50 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Users className="w-4 h-4 text-warning" />
            <div>
              <p className="text-xs font-semibold text-foreground">Layer 3: Granular RBAC</p>
              <p className="text-[11px] text-muted-foreground">Admin, Member, and Viewer enforcement</p>
            </div>
          </div>
          <span className="text-[10px] font-mono text-warning font-medium">Enforced</span>
        </div>

        <div className="p-3 rounded-xl border border-success/30 bg-success/5 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Database className="w-4 h-4 text-success" />
            <div>
              <p className="text-xs font-semibold text-foreground">Layer 4: Vector Collection Isolation</p>
              <p className="text-[11px] text-muted-foreground">Dedicated Qdrant collections per tenant ID</p>
            </div>
          </div>
          <span className="text-[10px] font-mono text-success font-semibold">Isolated</span>
        </div>
      </div>
    </div>
  )

  const securityPillars = [
    {
      icon: Database,
      title: 'Physical & Logical Tenant Isolation',
      desc: 'Vectors are stored in isolated Qdrant collections named raguard_knowledge_{tenant_id}. Database tables enforce tenant_id constraints on every SQL execution.',
    },
    {
      icon: KeyRound,
      title: 'Ephemeral Join Credentials',
      desc: 'Admins invite team members using cryptographically verified Join Codes with custom expiration windows (1, 7, 30, 60 days, or Never) and instant regeneration.',
    },
    {
      icon: Users,
      title: 'Strict Role-Based Access Control (RBAC)',
      desc: 'Admins control ingestion, purge, and workspace settings. Members can interact with grounded chat. Viewers have read-only access with zero configuration privileges.',
    },
    {
      icon: Eye,
      title: 'Credential Masking & Reveal Security',
      desc: 'Join codes and sensitive credentials remain masked by default to prevent shoulder-surfing and accidental screen-share leakage.',
    },
    {
      icon: FileText,
      title: 'Audit Logging & Delivery Tracking',
      desc: 'Every document operation, membership change, and vector synchronization is logged with correlation IDs for comprehensive SOC/security audits.',
    },
    {
      icon: Server,
      title: 'Private VPC & On-Premises Ready',
      desc: 'Deployable on your own private cloud or sovereign data center with Docker Compose, MinIO, PostgreSQL, Redis, and Qdrant under your full control.',
    },
  ]

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="Enterprise-Grade Security & Isolation"
        title={
          <>
            Zero Cross-Tenant Contamination{' '}
            <span className="text-primary">by Design.</span>
          </>
        }
        subtitle="Every tenant's vector collections and database records are strictly partitioned. Cryptographically signed credentials and RBAC enforce least-privilege access across every layer."
        secondaryCtaText="Review API Reference"
        secondaryCtaLink="/resources/api-reference"
        visual={heroVisual}
      />

      {/* Security Pillars */}
      <section className="py-20 lg:py-28">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <FadeUp className="text-center max-w-3xl mx-auto mb-16" yOffset={20}>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-xs font-semibold text-primary mb-4">
              <Shield className="w-3.5 h-3.5" />
              <span>Architectural Defensibility</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
              Security Built Into the Data Pipeline
            </h2>
            <p className="text-muted-foreground text-base md:text-lg mt-4">
              Security cannot be a prompt afterthought. In Veritas RAG, multi-tenancy is enforced at the database query planner and vector collection level.
            </p>
          </FadeUp>

          <Stagger className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" staggerDelay={0.08}>
            {securityPillars.map((p) => (
              <FadeUp key={p.title} className="p-6 rounded-2xl border border-border/60 bg-surface/60 hover:bg-surface-elevated/80 transition-all duration-300 shadow-sm" yOffset={20}>
                <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-5">
                  <p.icon className="w-5 h-5" />
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-2">{p.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{p.desc}</p>
              </FadeUp>
            ))}
          </Stagger>
        </div>
      </section>

      {/* Join Code Security Deep-Dive */}
      <section className="py-20 bg-surface/20 border-t border-border/40">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <FadeUp yOffset={20}>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-xs font-semibold text-primary mb-4">
                <Clock className="w-3.5 h-3.5" />
                <span>Zero Trust Onboarding</span>
              </div>
              <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground mb-4">
                Ephemeral Workspace Join Access
              </h2>
              <p className="text-muted-foreground leading-relaxed mb-6">
                Never distribute permanent workspace invitation links. Veritas RAG enables administrators to configure automated expiration windows, regenerate codes on demand, and immediately revoke compromised access keys.
              </p>
              <div className="space-y-3">
                <div className="flex items-center space-x-3 text-sm text-foreground">
                  <CheckCircle2 className="w-4 h-4 text-primary flex-shrink-0" />
                  <span>Configurable 1, 7, 30, 60-day or indefinite expirations</span>
                </div>
                <div className="flex items-center space-x-3 text-sm text-foreground">
                  <CheckCircle2 className="w-4 h-4 text-primary flex-shrink-0" />
                  <span>Instant credential revocation without restarting containers</span>
                </div>
                <div className="flex items-center space-x-3 text-sm text-foreground">
                  <CheckCircle2 className="w-4 h-4 text-primary flex-shrink-0" />
                  <span>Single-click secure clipboard copy with masked visual displays</span>
                </div>
              </div>
            </FadeUp>

            <FadeUp yOffset={20}>
              <div className="p-6 rounded-2xl border border-border/70 bg-surface/80 shadow-md">
                <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-3">Admin Credential Preview</p>
                <div className="p-4 rounded-xl border border-border/60 bg-background/80 flex items-center justify-between mb-4">
                  <div>
                    <span className="text-xs text-muted-foreground">Active Join Code:</span>
                    <p className="text-sm font-mono font-bold text-foreground tracking-wider">VR-9482-KLAX</p>
                  </div>
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-primary/10 text-primary">Expires: 30 Days</span>
                </div>
                <div className="p-4 rounded-xl border border-border/60 bg-background/80 flex items-center justify-between">
                  <div>
                    <span className="text-xs text-muted-foreground">Direct Join Link:</span>
                    <p className="text-xs font-mono text-muted-foreground truncate max-w-[240px]">https://veritas.ai/join?code=VR-9482-KLAX</p>
                  </div>
                  <span className="text-[11px] text-muted-foreground">Masked</span>
                </div>
              </div>
            </FadeUp>
          </div>
        </div>
      </section>

      <MarketingCTA
        title="Ready to Secure Your Enterprise Knowledge?"
        description="Experience tenant-isolated vector storage and verifiable RBAC in your own environment."
      />
    </div>
  )
}
