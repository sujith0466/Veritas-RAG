import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import {
  Layers,
  FileText,
  Binary,
  Boxes,
  ScanSearch,
  BrainCircuit,
  Sparkles,
  ShieldCheck,
  BadgeCheck,
  Check,
  ArrowRight,
  Zap,
  Activity,
} from 'lucide-react'
import { SectionHeading } from '@/components/landing/SectionHeading'
import { FadeUp } from '@/components/motion/FadeUp'
import { cn } from '@/utils/cn'

interface ArchitectureStep {
  id: string
  stepNumber: string
  label: string
  description: string
  phase: string
  phaseGroup: 'representation' | 'retrieval' | 'synthesis' | 'grounding'
  telemetry: string
  icon: typeof Layers
  accentColor: string
  accentBg: string
  accentBorder: string
  glowColor: string
}

const ARCHITECTURE_STEPS: ArchitectureStep[] = [
  {
    id: 'sources',
    stepNumber: '01',
    label: 'Knowledge Sources',
    description: 'APIs, Databases, Documents',
    phase: 'INGESTION',
    phaseGroup: 'representation',
    telemetry: 'Multi-Format Ingestion · S3, Postgres, REST APIs',
    icon: Layers,
    accentColor: 'text-teal-700 dark:text-teal-400',
    accentBg: 'bg-teal-500/10',
    accentBorder: 'border-teal-600/30',
    glowColor: 'rgba(15, 118, 110, 0.15)',
  },
  {
    id: 'processing',
    stepNumber: '02',
    label: 'Document Processing',
    description: 'Intelligent Chunking & Metadata',
    phase: 'PROCESSING',
    phaseGroup: 'representation',
    telemetry: 'Structure-Aware Parser · Token Boundary Guard',
    icon: FileText,
    accentColor: 'text-teal-700 dark:text-teal-400',
    accentBg: 'bg-teal-500/10',
    accentBorder: 'border-teal-600/30',
    glowColor: 'rgba(15, 118, 110, 0.15)',
  },
  {
    id: 'embeddings',
    stepNumber: '03',
    label: 'Embeddings',
    description: 'Dense & Sparse Vectors',
    phase: 'REPRESENTATION',
    phaseGroup: 'representation',
    telemetry: 'Dense 1536d Vectors + BM25 Sparse Index',
    icon: Binary,
    accentColor: 'text-sky-700 dark:text-sky-400',
    accentBg: 'bg-sky-500/10',
    accentBorder: 'border-sky-600/30',
    glowColor: 'rgba(2, 132, 199, 0.15)',
  },
  {
    id: 'vectordb',
    stepNumber: '04',
    label: 'Vector Database',
    description: 'Qdrant / Enterprise Store',
    phase: 'STORAGE',
    phaseGroup: 'representation',
    telemetry: 'HNSW Cosine Index · Tenant-Isolated Collections',
    icon: Boxes,
    accentColor: 'text-sky-700 dark:text-sky-400',
    accentBg: 'bg-sky-500/10',
    accentBorder: 'border-sky-600/30',
    glowColor: 'rgba(2, 132, 199, 0.15)',
  },
  {
    id: 'retrieval',
    stepNumber: '05',
    label: 'Hybrid Retrieval',
    description: 'Keyword + Semantic Search',
    phase: 'RETRIEVAL',
    phaseGroup: 'retrieval',
    telemetry: 'Reciprocal Rank Fusion (RRF) · Cross-Encoder Re-rank',
    icon: ScanSearch,
    accentColor: 'text-indigo-700 dark:text-indigo-400',
    accentBg: 'bg-indigo-500/10',
    accentBorder: 'border-indigo-600/30',
    glowColor: 'rgba(79, 70, 229, 0.15)',
  },
  {
    id: 'reflection',
    stepNumber: '06',
    label: 'Reflection Engine',
    description: 'Query Rewriting & Re-ranking',
    phase: 'REFLECTION',
    phaseGroup: 'retrieval',
    telemetry: 'Self-Correction Loop · Context Decomposition',
    icon: BrainCircuit,
    accentColor: 'text-indigo-700 dark:text-indigo-400',
    accentBg: 'bg-indigo-500/10',
    accentBorder: 'border-indigo-600/30',
    glowColor: 'rgba(79, 70, 229, 0.15)',
  },
  {
    id: 'llm',
    stepNumber: '07',
    label: 'LLM Synthesis',
    description: 'Grounded Generation',
    phase: 'SYNTHESIS',
    phaseGroup: 'synthesis',
    telemetry: 'Attributed Context Injection · Resilient Fallbacks',
    icon: Sparkles,
    accentColor: 'text-amber-700 dark:text-amber-400',
    accentBg: 'bg-amber-500/10',
    accentBorder: 'border-amber-600/30',
    glowColor: 'rgba(217, 119, 6, 0.15)',
  },
  {
    id: 'validation',
    stepNumber: '08',
    label: 'Reliability Validation',
    description: 'Hallucination Checks',
    phase: 'VALIDATION',
    phaseGroup: 'synthesis',
    telemetry: 'NLI Entailment Check · Citation Span Verification',
    icon: ShieldCheck,
    accentColor: 'text-emerald-700 dark:text-emerald-400',
    accentBg: 'bg-emerald-500/10',
    accentBorder: 'border-emerald-600/30',
    glowColor: 'rgba(5, 150, 105, 0.18)',
  },
  {
    id: 'response',
    stepNumber: '09',
    label: 'Grounded Response',
    description: 'Secure, Attributed Output',
    phase: 'GROUNDED ANSWER',
    phaseGroup: 'grounding',
    telemetry: 'Source-Attributed Citations · Streaming SSE Delivery',
    icon: BadgeCheck,
    accentColor: 'text-emerald-700 dark:text-emerald-400',
    accentBg: 'bg-emerald-500/15',
    accentBorder: 'border-emerald-600/40',
    glowColor: 'rgba(5, 150, 105, 0.25)',
  },
]

const PIPELINE_PHASES = [
  { id: 'all', label: 'Complete Pipeline', range: [0, 8] },
  { id: 'representation', label: '1. Ingestion & Storage', range: [0, 3] },
  { id: 'retrieval', label: '2. Retrieval & Reflection', range: [4, 5] },
  { id: 'synthesis', label: '3. Synthesis & Verification', range: [6, 7] },
  { id: 'grounding', label: '4. Grounded Output', range: [8, 8] },
]

const AUTO_CYCLE_INTERVAL = 3200

export function ArchitectureOverview() {
  const [activeStepIndex, setActiveStepIndex] = useState(0)
  const [isHovering, setIsHovering] = useState(false)
  const [selectedPhase, setSelectedPhase] = useState<string>('all')
  const shouldReduceMotion = useReducedMotion()
  const sectionRef = useRef<HTMLElement>(null)

  // Auto-cycle through pipeline stages when not actively hovering
  useEffect(() => {
    if (shouldReduceMotion || isHovering) return

    const timer = setInterval(() => {
      setActiveStepIndex((prev) => (prev + 1) % ARCHITECTURE_STEPS.length)
    }, AUTO_CYCLE_INTERVAL)

    return () => clearInterval(timer)
  }, [shouldReduceMotion, isHovering])

  const handleStepSelect = useCallback((index: number) => {
    setActiveStepIndex(index)
  }, [])

  const handlePhaseFilter = (phaseId: string, range: number[]) => {
    setSelectedPhase(phaseId)
    setActiveStepIndex(range[0])
  }

  const activeStep = ARCHITECTURE_STEPS[activeStepIndex]

  return (
    <section
      id="architecture"
      ref={sectionRef}
      aria-label="How Veritas RAG Works Pipeline Architecture"
      className="py-28 md:py-36 bg-background relative overflow-hidden border-t border-border/70"
    >
      {/* ─── Environmental Atmosphere & Optical Grid ─── */}
      <div className="absolute inset-0 pointer-events-none -z-10 overflow-hidden">
        {/* Soft radial glow centers */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[500px] bg-primary/[0.035] rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-emerald-500/[0.025] rounded-full blur-[140px]" />

        {/* Subtle engineering grid */}
        <div
          className="absolute inset-0 opacity-[0.03] dark:opacity-[0.05]"
          style={{
            backgroundImage: `radial-gradient(circle at 1px 1px, hsl(var(--foreground)) 1px, transparent 0)`,
            backgroundSize: '32px 32px',
          }}
        />
      </div>

      <div className="container mx-auto px-4 md:px-8 max-w-6xl relative z-10">
        {/* ─── Header & Subtitle ─── */}
        <FadeUp>
          <div className="text-center max-w-3xl mx-auto mb-12">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-surface border border-border/80 shadow-xs mb-4 text-xs font-mono font-medium text-muted-foreground">
              <span className="w-1.5 h-1.5 rounded-full bg-teal-600 animate-pulse" />
              <span>DETERMINISTIC VERIFICATION PIPELINE</span>
            </div>
            <SectionHeading
              title="How Veritas RAG Works."
              subtitle="A transparent, end-to-end view of our reliability pipeline."
              className="mb-8"
            />

            {/* ─── Phase Navigator Bar ─── */}
            <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
              {PIPELINE_PHASES.map((phase) => {
                const isCurrentPhase =
                  selectedPhase === phase.id ||
                  (selectedPhase === 'all' &&
                    activeStepIndex >= phase.range[0] &&
                    activeStepIndex <= phase.range[1])

                return (
                  <button
                    key={phase.id}
                    type="button"
                    onClick={() => handlePhaseFilter(phase.id, phase.range)}
                    className={cn(
                      'px-3.5 py-1.5 rounded-full text-xs font-medium transition-all duration-200 border',
                      isCurrentPhase
                        ? 'bg-surface border-teal-600/40 text-foreground shadow-xs'
                        : 'bg-surface/50 border-border/60 text-muted-foreground hover:text-foreground hover:bg-surface'
                    )}
                  >
                    {phase.label}
                  </button>
                )
              })}
            </div>
          </div>
        </FadeUp>

        {/* ─── Live Telemetry Header Banner ─── */}
        <FadeUp delay={0.15}>
          <div className="max-w-4xl mx-auto mb-14 bg-surface/80 backdrop-blur-md rounded-2xl border border-border/80 p-4 shadow-card flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3 w-full sm:w-auto">
              <div className="w-9 h-9 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary flex-shrink-0">
                <Activity className="w-4 h-4 animate-pulse" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-2xs font-mono font-bold uppercase tracking-wider text-muted-foreground">
                    Active Stage {activeStep.stepNumber} of 09
                  </span>
                  <span className="w-1 h-1 rounded-full bg-border" />
                  <span className="text-2xs font-mono font-semibold text-teal-700 dark:text-teal-400">
                    {activeStep.phase}
                  </span>
                </div>
                <p className="text-sm font-semibold text-foreground truncate">
                  {activeStep.label} — <span className="text-xs font-normal text-muted-foreground">{activeStep.description}</span>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4 text-xs font-mono text-muted-foreground self-end sm:self-center border-t sm:border-t-0 border-border/50 pt-2 sm:pt-0 w-full sm:w-auto justify-between sm:justify-end">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span className="text-foreground font-semibold">Grounded Execution</span>
              </div>
              <div className="h-3 w-px bg-border hidden sm:block" />
              <div className="text-right">
                <span className="text-foreground font-semibold">Deterministic</span> Pipeline Flow
              </div>
            </div>
          </div>
        </FadeUp>

        {/* ─── 3D Central Reliability Pipeline ─── */}
        <div
          className="relative max-w-5xl mx-auto"
          onMouseEnter={() => setIsHovering(true)}
          onMouseLeave={() => setIsHovering(false)}
          style={{ perspective: '1200px' }}
        >
          {/* Central Reliability Spine (Rail) - Desktop (center) / Mobile (left) */}
          <div className="absolute top-8 bottom-12 left-6 md:left-1/2 -translate-x-1/2 w-8 flex flex-col items-center pointer-events-none z-0">
            {/* Outer soft track */}
            <div className="w-1 h-full bg-border/60 rounded-full relative overflow-hidden">
              {/* Vertical Laser Pulse Core */}
              <motion.div
                className="absolute left-0 right-0 w-full bg-gradient-to-b from-teal-600 via-sky-500 to-emerald-500 rounded-full"
                style={{
                  height: `${((activeStepIndex + 1) / ARCHITECTURE_STEPS.length) * 100}%`,
                }}
                transition={{ duration: 0.5, ease: 'easeInOut' }}
              />

              {/* Traveling light particle */}
              {!shouldReduceMotion && (
                <motion.div
                  className="absolute left-0 right-0 h-16 w-full bg-gradient-to-b from-transparent via-white to-transparent"
                  animate={{
                    top: ['-10%', '100%'],
                  }}
                  transition={{
                    duration: 3.6,
                    repeat: Infinity,
                    ease: 'linear',
                  }}
                />
              )}
            </div>
          </div>

          {/* ─── Architecture Nodes Sequence ─── */}
          <div className="space-y-6 md:space-y-10 relative z-10">
            {ARCHITECTURE_STEPS.map((step, index) => {
              const isActive = activeStepIndex === index
              const isPast = activeStepIndex > index
              const isEven = index % 2 === 0
              const isFinalStep = index === ARCHITECTURE_STEPS.length - 1
              const IconComponent = step.icon

              return (
                <div
                  key={step.id}
                  className={cn(
                    'relative flex items-center w-full',
                    // Mobile: always left-aligned padding for the spine rail
                    'pl-12 md:pl-0',
                    // Desktop: alternating left / right
                    isEven ? 'md:justify-start' : 'md:justify-end'
                  )}
                >
                  {/* Spine Node Anchor Hub (Circle on the rail) */}
                  <div
                    className={cn(
                      'absolute left-6 md:left-1/2 -translate-x-1/2 w-7 h-7 rounded-full flex items-center justify-center transition-all duration-300 z-20',
                      isActive
                        ? 'bg-surface ring-4 ring-teal-500/20 shadow-md border-2 border-teal-600 scale-110'
                        : isPast
                        ? 'bg-teal-700/90 border-2 border-teal-600/80 text-white shadow-xs'
                        : 'bg-surface border-2 border-border text-muted-foreground'
                    )}
                  >
                    {isPast ? (
                      <Check className="w-3.5 h-3.5 text-white" strokeWidth={3} />
                    ) : (
                      <span className="text-[10px] font-mono font-bold">
                        {step.stepNumber}
                      </span>
                    )}

                    {/* Active pulsing orbital ring */}
                    {isActive && !shouldReduceMotion && (
                      <motion.div
                        className="absolute inset-0 rounded-full border border-teal-600"
                        animate={{ scale: [1, 1.8, 2.2], opacity: [0.8, 0.2, 0] }}
                        transition={{ duration: 1.6, repeat: Infinity, ease: 'easeOut' }}
                      />
                    )}
                  </div>

                  {/* Horizontal Data Connector Line (Desktop) */}
                  <div
                    className={cn(
                      'hidden md:block absolute top-1/2 -translate-y-1/2 h-px transition-all duration-300 pointer-events-none z-10',
                      isEven
                        ? 'right-1/2 w-12 mr-3.5 origin-right'
                        : 'left-1/2 w-12 ml-3.5 origin-left',
                      isActive
                        ? 'bg-gradient-to-r from-teal-600 to-teal-500 shadow-sm'
                        : isPast
                        ? 'bg-teal-600/40'
                        : 'bg-border/60'
                    )}
                  >
                    {/* Flowing energy pulse dot on active connector */}
                    {isActive && !shouldReduceMotion && (
                      <motion.div
                        className="w-2 h-2 rounded-full bg-teal-500 shadow-[0_0_8px_#0F766E] absolute top-1/2 -translate-y-1/2"
                        animate={{
                          left: isEven ? ['100%', '0%'] : ['0%', '100%'],
                        }}
                        transition={{
                          duration: 1.2,
                          repeat: Infinity,
                          ease: 'easeInOut',
                        }}
                      />
                    )}
                  </div>

                  {/* ─── 3D Interactive Card ─── */}
                  <motion.div
                    role="button"
                    tabIndex={0}
                    aria-label={`Pipeline Stage ${step.stepNumber}: ${step.label} - ${step.description}`}
                    aria-selected={isActive}
                    onClick={() => handleStepSelect(index)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        handleStepSelect(index)
                      }
                    }}
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
                      'w-full md:w-[44%] lg:w-[42%] text-left cursor-pointer transition-all duration-300 group rounded-2xl relative select-none',
                      'bg-surface/85 backdrop-blur-md border p-5 md:p-6',
                      isActive
                        ? isFinalStep
                          ? 'border-emerald-600/60 shadow-[0_12px_36px_rgba(5,150,105,0.16)] bg-gradient-to-br from-surface to-emerald-50/20 dark:to-emerald-950/20'
                          : 'border-teal-600/50 shadow-[0_12px_36px_rgba(15,118,110,0.12)] bg-surface'
                        : 'border-border/80 shadow-card hover:border-border hover:shadow-card-hover'
                    )}
                    style={{
                      transformStyle: 'preserve-3d',
                      transform: shouldReduceMotion
                        ? 'none'
                        : isEven
                        ? 'rotateY(2deg)'
                        : 'rotateY(-2deg)',
                    }}
                  >
                    {/* Inner Ambient Glow Accent */}
                    {isActive && (
                      <div
                        className="absolute inset-0 rounded-2xl pointer-events-none -z-10 blur-xl opacity-60"
                        style={{ backgroundColor: step.glowColor }}
                      />
                    )}

                    {/* Top Row: Phase Tag & Stage Number */}
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            'px-2.5 py-0.5 rounded-md text-[10px] font-mono font-bold tracking-wider uppercase border',
                            isActive
                              ? `${step.accentBg} ${step.accentColor} ${step.accentBorder}`
                              : 'bg-muted/70 text-muted-foreground border-transparent'
                          )}
                        >
                          {step.phase}
                        </span>

                        {isFinalStep && (
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-emerald-600/10 text-emerald-700 dark:text-emerald-400 border border-emerald-600/20 flex items-center gap-1">
                            <Check className="w-2.5 h-2.5" /> Attributed
                          </span>
                        )}
                      </div>

                      <span className="text-xs font-mono font-bold text-muted-foreground/70">
                        STAGE {step.stepNumber}
                      </span>
                    </div>

                    {/* Middle Row: Icon, Title & Description */}
                    <div className="flex items-start gap-3.5">
                      <div
                        className={cn(
                          'w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 transition-colors duration-200 border',
                          isActive
                            ? `${step.accentBg} ${step.accentColor} ${step.accentBorder} shadow-xs`
                            : 'bg-muted/50 text-muted-foreground border-border/50 group-hover:text-foreground'
                        )}
                      >
                        <IconComponent className="w-5 h-5 transition-transform duration-300 group-hover:scale-110" />
                      </div>

                      <div className="flex-1 min-w-0">
                        <h4 className="font-semibold text-base md:text-lg text-foreground tracking-tight leading-snug">
                          {step.label}
                        </h4>
                        <p className="text-xs md:text-sm text-muted-foreground mt-0.5 leading-relaxed">
                          {step.description}
                        </p>
                      </div>
                    </div>

                    {/* Bottom Row: Technical Telemetry & Specifications */}
                    <div className="mt-4 pt-3 border-t border-border/50 flex items-center justify-between text-2xs font-mono text-muted-foreground">
                      <div className="flex items-center gap-1.5 truncate">
                        <Zap className={cn('w-3 h-3 flex-shrink-0', isActive ? 'text-teal-600' : 'text-muted-foreground')} />
                        <span className="truncate">{step.telemetry}</span>
                      </div>

                      {isActive && (
                        <div className="flex-shrink-0 text-teal-700 dark:text-teal-400 font-semibold flex items-center gap-1">
                          <span>ACTIVE</span>
                          <ArrowRight className="w-2.5 h-2.5" />
                        </div>
                      )}
                    </div>
                  </motion.div>
                </div>
              )
            })}
          </div>

          {/* ─── Bottom Reliability Outcome Seal ─── */}
          <div className="mt-16 md:mt-20 pt-8 border-t border-border/70 flex flex-col md:flex-row items-center justify-between gap-6 text-center md:text-left bg-surface/50 backdrop-blur-xs rounded-2xl p-6 border border-border/60">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl bg-emerald-600/10 border border-emerald-600/30 flex items-center justify-center text-emerald-600 flex-shrink-0 shadow-xs">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <div>
                <h5 className="font-semibold text-foreground text-base">
                  Rigorous Reliability & Evidence Verification
                </h5>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Generated responses are validated against retrieved source spans and policy guardrails before streaming.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 flex-shrink-0">
              <div className="px-3.5 py-2 rounded-xl bg-surface border border-border text-center shadow-xs">
                <div className="text-xs font-bold text-foreground font-mono">Source-Linked</div>
                <div className="text-[10px] text-muted-foreground">Attributions</div>
              </div>
              <div className="px-3.5 py-2 rounded-xl bg-surface border border-border text-center shadow-xs">
                <div className="text-xs font-bold text-foreground font-mono">Evidence-Grounded</div>
                <div className="text-[10px] text-muted-foreground">Validation</div>
              </div>
              <div className="px-3.5 py-2 rounded-xl bg-surface border border-border text-center shadow-xs">
                <div className="text-xs font-bold text-foreground font-mono">Auditable</div>
                <div className="text-[10px] text-muted-foreground">Telemetry Logs</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
