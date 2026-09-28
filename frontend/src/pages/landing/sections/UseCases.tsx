import { useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import {
  Terminal,
  LayoutTemplate,
  Network,
  ShieldCheck,
  ArrowUpRight,
  Cpu,
  Workflow,
} from 'lucide-react'
import { SectionHeading } from '@/components/landing/SectionHeading'
import { FadeUp } from '@/components/motion/FadeUp'
import { cn } from '@/utils/cn'

interface Persona {
  id: string
  roleNumber: string
  title: string
  tagline: string
  description: string
  capability: string
  subCapabilities: string[]
  icon: typeof Terminal
  accentColor: string
  accentBg: string
  accentBorder: string
  glowColor: string
  gridPosition: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'
}

const PERSONAS: Persona[] = [
  {
    id: 'ai-engineers',
    roleNumber: '01',
    title: 'AI Engineers',
    tagline: 'RETRIEVAL VISIBILITY & OBSERVABILITY',
    description:
      'Focus on building great models, not debugging retrieval pipelines. Veritas RAG provides instant visibility into chunk quality, embedding drift, and hallucination rates.',
    capability: 'Real-Time Vector & Drift Telemetry',
    subCapabilities: ['Chunk Drift Diagnostics', 'Hallucination Pre-Check', 'Retrieval Recall Profiler'],
    icon: Terminal,
    accentColor: 'text-teal-700 dark:text-teal-400',
    accentBg: 'bg-teal-500/10',
    accentBorder: 'border-teal-600/30',
    glowColor: 'rgba(15, 118, 110, 0.15)',
    gridPosition: 'top-left',
  },
  {
    id: 'platform-teams',
    roleNumber: '02',
    title: 'Platform Teams',
    tagline: 'FLEET STANDARDIZATION & SCALE',
    description:
      'Standardize AI deployments across the organization. Deliver a unified, multi-tenant RAG infrastructure that scales effortlessly without creating operational silos.',
    capability: 'Multi-Tenant Orchestration & Fleet Scale',
    subCapabilities: ['Tenant Workspaces', 'Zero-Silo Deployments', 'Deterministic Rate Governance'],
    icon: LayoutTemplate,
    accentColor: 'text-sky-700 dark:text-sky-400',
    accentBg: 'bg-sky-500/10',
    accentBorder: 'border-sky-600/30',
    glowColor: 'rgba(2, 132, 199, 0.15)',
    gridPosition: 'top-right',
  },
  {
    id: 'enterprise-architects',
    roleNumber: '03',
    title: 'Enterprise Architects',
    tagline: 'HEADLESS INTEGRATION & DATA LAKES',
    description:
      'Design future-proof systems. Seamlessly integrate with existing data lakes, identity providers, and compliance frameworks using our headless API architecture.',
    capability: 'Headless API & Enterprise Connectors',
    subCapabilities: ['Lakehouse Connectors', 'OIDC / SAML Identity', 'Stateless REST & SSE'],
    icon: Network,
    accentColor: 'text-indigo-700 dark:text-indigo-400',
    accentBg: 'bg-indigo-500/10',
    accentBorder: 'border-indigo-600/30',
    glowColor: 'rgba(79, 70, 229, 0.15)',
    gridPosition: 'bottom-left',
  },
  {
    id: 'security-teams',
    roleNumber: '04',
    title: 'Security Teams',
    tagline: 'GOVERNANCE & POLICY ISOLATION',
    description:
      'Maintain fine-grained control over enterprise data. Enforce strict RBAC, generate comprehensive audit trails, and ensure tenant isolation across all retrieval vectors.',
    capability: 'Strict RBAC & Verifiable Audit Trails',
    subCapabilities: ['Isolated Collections', 'Immutable Audit Logs', 'Field-Level DLP Redaction'],
    icon: ShieldCheck,
    accentColor: 'text-emerald-700 dark:text-emerald-400',
    accentBg: 'bg-emerald-500/10',
    accentBorder: 'border-emerald-600/30',
    glowColor: 'rgba(5, 150, 105, 0.15)',
    gridPosition: 'bottom-right',
  },
]

export function UseCases() {
  const [activePersonaId, setActivePersonaId] = useState<string | null>(null)
  const shouldReduceMotion = useReducedMotion()

  const activePersona = PERSONAS.find((p) => p.id === activePersonaId) || null

  return (
    <section
      id="enterprise-teams"
      aria-label="Built for Enterprise AI Teams"
      className="py-28 md:py-36 bg-background relative overflow-hidden border-t border-border/70"
    >
      {/* ─── Ambient Atmospheric Background ─── */}
      <div className="absolute inset-0 pointer-events-none -z-10 overflow-hidden">
        {/* Soft radial atmospheric centers */}
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[750px] h-[550px] bg-teal-500/[0.03] rounded-full blur-[130px]" />
        <div className="absolute bottom-1/4 left-1/2 -translate-x-1/2 w-[700px] h-[450px] bg-indigo-500/[0.025] rounded-full blur-[140px]" />

        {/* Engineering dot matrix */}
        <div
          className="absolute inset-0 opacity-[0.025] dark:opacity-[0.05]"
          style={{
            backgroundImage: `radial-gradient(circle at 1px 1px, hsl(var(--foreground)) 1px, transparent 0)`,
            backgroundSize: '36px 36px',
          }}
        />
      </div>

      <div className="container mx-auto px-4 md:px-8 max-w-6xl relative z-10">
        {/* ─── Section Header ─── */}
        <FadeUp>
          <div className="text-center max-w-3xl mx-auto mb-16 md:mb-20">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-surface border border-border/80 shadow-xs mb-4 text-xs font-mono font-medium text-muted-foreground">
              <span className="w-1.5 h-1.5 rounded-full bg-teal-600 animate-pulse" />
              <span>COLLABORATIVE RELIABILITY MATRIX</span>
            </div>
            <SectionHeading
              title="Built for Enterprise AI Teams."
              subtitle="A unified platform that aligns engineering velocity with enterprise governance."
              className="mb-0"
            />
          </div>
        </FadeUp>

        {/* ─── Interactive Enterprise Capability Matrix ─── */}
        <div
          className="relative max-w-5xl mx-auto"
          style={{ perspective: '1100px' }}
        >
          {/* ─── Central "Veritas RAG Core" Platform Node (Desktop Anchor) ─── */}
          <div className="hidden lg:flex absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-20 pointer-events-none items-center justify-center">
            {/* Outer ambient glow based on hovered persona */}
            <motion.div
              className="w-40 h-40 rounded-3xl -z-10 blur-2xl absolute"
              animate={{
                backgroundColor: activePersona ? activePersona.glowColor : 'rgba(15, 118, 110, 0.08)',
                scale: activePersona ? 1.15 : 1,
              }}
              transition={{ duration: 0.4 }}
            />

            {/* Platform Core Housing */}
            <motion.div
              animate={{
                borderColor: activePersona ? 'rgba(15, 118, 110, 0.45)' : 'hsl(var(--border))',
                scale: activePersona ? 1.04 : 1,
              }}
              transition={{ duration: 0.3 }}
              className="w-36 h-36 rounded-3xl bg-surface/90 backdrop-blur-xl border-2 p-3 shadow-[0_8px_32px_rgba(15,23,42,0.08)] flex flex-col items-center justify-center text-center relative overflow-hidden"
            >
              {/* Inner subtle pulse line */}
              <div className="w-8 h-8 rounded-xl bg-teal-500/10 border border-teal-600/30 flex items-center justify-center text-teal-700 dark:text-teal-400 mb-1.5">
                <Cpu className="w-4 h-4" />
              </div>
              <span className="text-xs font-bold font-mono tracking-tight text-foreground leading-none">
                VERITAS RAG
              </span>
              <span className="text-[10px] font-mono text-muted-foreground mt-0.5 leading-tight">
                Reliability Layer
              </span>

              <div className="mt-2 inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-teal-500/10 border border-teal-600/20 text-[9px] font-mono font-medium text-teal-700 dark:text-teal-400">
                <span className="w-1 h-1 rounded-full bg-teal-600 animate-pulse" />
                <span>ACTIVE FLEET</span>
              </div>
            </motion.div>
          </div>

          {/* ─── 2x2 Interactive Roles Grid ─── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 lg:gap-14 relative z-10">
            {PERSONAS.map((persona) => {
              const isHovered = activePersonaId === persona.id
              const isAnyHovered = activePersonaId !== null
              const isQuiet = isAnyHovered && !isHovered
              const IconComponent = persona.icon

              return (
                <motion.div
                  key={persona.id}
                  role="button"
                  tabIndex={0}
                  aria-label={`${persona.title}: ${persona.description}`}
                  onMouseEnter={() => setActivePersonaId(persona.id)}
                  onMouseLeave={() => setActivePersonaId(null)}
                  onFocus={() => setActivePersonaId(persona.id)}
                  onBlur={() => setActivePersonaId(null)}
                  whileHover={
                    shouldReduceMotion
                      ? {}
                      : {
                          scale: 1.015,
                          z: 20,
                          transition: { duration: 0.2 },
                        }
                  }
                  className={cn(
                    'group relative rounded-2xl p-6 md:p-8 text-left transition-all duration-300 select-none cursor-pointer',
                    'bg-surface/85 backdrop-blur-md border',
                    isHovered
                      ? 'border-teal-600/50 shadow-[0_16px_40px_rgba(15,118,110,0.12)] bg-surface'
                      : isQuiet
                      ? 'border-border/60 shadow-xs opacity-85'
                      : 'border-border/80 shadow-card hover:border-border hover:shadow-card-hover'
                  )}
                  style={{
                    transformStyle: 'preserve-3d',
                    transform: shouldReduceMotion
                      ? 'none'
                      : persona.gridPosition === 'top-left'
                      ? 'rotateY(1.5deg) rotateX(1.5deg)'
                      : persona.gridPosition === 'top-right'
                      ? 'rotateY(-1.5deg) rotateX(1.5deg)'
                      : persona.gridPosition === 'bottom-left'
                      ? 'rotateY(1.5deg) rotateX(-1.5deg)'
                      : 'rotateY(-1.5deg) rotateX(-1.5deg)',
                  }}
                >
                  {/* Subtle Inner Ambient Glow on Hover */}
                  {isHovered && (
                    <div
                      className="absolute inset-0 rounded-2xl pointer-events-none -z-10 blur-xl opacity-60"
                      style={{ backgroundColor: persona.glowColor }}
                    />
                  )}

                  {/* Header Row: Stage Number, Tagline & Icon */}
                  <div className="flex items-center justify-between gap-3 mb-5">
                    <div className="flex items-center gap-3">
                      <div
                        className={cn(
                          'w-11 h-11 rounded-xl flex items-center justify-center transition-colors duration-200 border',
                          isHovered
                            ? `${persona.accentBg} ${persona.accentColor} ${persona.accentBorder} shadow-xs`
                            : 'bg-muted/60 text-muted-foreground border-border/50 group-hover:text-foreground'
                        )}
                      >
                        <IconComponent className="w-5 h-5 transition-transform duration-300 group-hover:scale-110" />
                      </div>

                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-2xs font-mono font-bold text-muted-foreground/80">
                            ROLE {persona.roleNumber}
                          </span>
                          <span className="w-1 h-1 rounded-full bg-border" />
                          <span
                            className={cn(
                              'text-[10px] font-mono font-semibold uppercase tracking-wider',
                              isHovered ? persona.accentColor : 'text-muted-foreground'
                            )}
                          >
                            {persona.tagline}
                          </span>
                        </div>
                        <h3 className="text-xl font-bold text-foreground tracking-tight leading-snug">
                          {persona.title}
                        </h3>
                      </div>
                    </div>

                    <div className="w-6 h-6 rounded-full border border-border/60 flex items-center justify-center text-muted-foreground/60 group-hover:text-foreground group-hover:border-border transition-colors">
                      <ArrowUpRight className="w-3.5 h-3.5" />
                    </div>
                  </div>

                  {/* Body Text */}
                  <p className="text-sm text-muted-foreground leading-relaxed mb-6">
                    {persona.description}
                  </p>

                  {/* Capability Badge & Subcapabilities */}
                  <div className="pt-4 border-t border-border/50 flex flex-col gap-2.5">
                    <div className="flex items-center justify-between text-xs font-mono">
                      <span className="text-muted-foreground font-medium">Core Capability:</span>
                      <span
                        className={cn(
                          'font-semibold text-right truncate pl-2',
                          isHovered ? persona.accentColor : 'text-foreground'
                        )}
                      >
                        {persona.capability}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5 pt-1">
                      {persona.subCapabilities.map((sub) => (
                        <span
                          key={sub}
                          className="px-2 py-0.5 rounded-md bg-muted/50 border border-border/50 text-[11px] font-mono text-muted-foreground"
                        >
                          {sub}
                        </span>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )
            })}
          </div>

          {/* ─── Bottom Alignment Banner ─── */}
          <div className="mt-12 md:mt-16 bg-surface/50 backdrop-blur-xs rounded-2xl p-6 border border-border/60 flex flex-col sm:flex-row items-center justify-between gap-4 text-center sm:text-left">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-teal-500/10 border border-teal-600/20 flex items-center justify-center text-teal-700 dark:text-teal-400 flex-shrink-0">
                <Workflow className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-foreground">
                  Cross-Functional Governance Standard
                </h4>
                <p className="text-xs text-muted-foreground">
                  Single control plane uniting engineers, architects, operators, and compliance officers.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground flex-shrink-0">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="font-semibold text-foreground">Multi-Tenant Unified Core</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
