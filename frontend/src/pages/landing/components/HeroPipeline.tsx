import { useState, useEffect } from 'react'
import { motion, useReducedMotion, AnimatePresence } from 'framer-motion'
import {
  FileText, Scissors, Binary, Database,
  Search, BrainCircuit, ShieldCheck, CheckCircle2,
} from 'lucide-react'
import { cn } from '@/utils/cn'

const PIPELINE_NODES = [
  {
    id: 1,
    label: 'Documents',
    description: 'Ingest PDFs, DOCX, URLs',
    icon: FileText,
    color: 'hsl(215 83% 53%)',
    colorSubtle: 'hsl(215 83% 53% / 0.12)',
  },
  {
    id: 2,
    label: 'Chunking',
    description: 'Semantic text segmentation',
    icon: Scissors,
    color: 'hsl(250 70% 60%)',
    colorSubtle: 'hsl(250 70% 60% / 0.12)',
  },
  {
    id: 3,
    label: 'Embeddings',
    description: 'Dense vector representations',
    icon: Binary,
    color: 'hsl(280 65% 60%)',
    colorSubtle: 'hsl(280 65% 60% / 0.12)',
  },
  {
    id: 4,
    label: 'Vector Store',
    description: 'Qdrant semantic index',
    icon: Database,
    color: 'hsl(175 84% 32%)',
    colorSubtle: 'hsl(175 84% 32% / 0.12)',
  },
  {
    id: 5,
    label: 'Hybrid Retrieval',
    description: 'BM25 + dense fusion',
    icon: Search,
    color: 'hsl(175 84% 32%)',
    colorSubtle: 'hsl(175 84% 32% / 0.12)',
  },
  {
    id: 6,
    label: 'Reflection',
    description: 'LLM self-critique loop',
    icon: BrainCircuit,
    color: 'hsl(38 92% 45%)',
    colorSubtle: 'hsl(38 92% 45% / 0.12)',
  },
  {
    id: 7,
    label: 'Validation',
    description: 'Hallucination detection',
    icon: ShieldCheck,
    color: 'hsl(161 94% 30%)',
    colorSubtle: 'hsl(161 94% 30% / 0.12)',
  },
  {
    id: 8,
    label: 'Grounded Response',
    description: 'Cited, confident output',
    icon: CheckCircle2,
    color: 'hsl(161 94% 30%)',
    colorSubtle: 'hsl(161 94% 30% / 0.15)',
  },
]

// Total animation cycle duration in seconds
const CYCLE_DURATION = 1.6
const TOTAL_DURATION = CYCLE_DURATION * PIPELINE_NODES.length

export function HeroPipeline({ className }: { className?: string }) {
  const [activeNode, setActiveNode] = useState(0)
  const [hoveredNode, setHoveredNode] = useState<number | null>(null)
  const shouldReduceMotion = useReducedMotion()

  useEffect(() => {
    if (shouldReduceMotion) return
    const interval = setInterval(() => {
      setActiveNode((prev) => (prev + 1) % PIPELINE_NODES.length)
    }, CYCLE_DURATION * 1000)
    return () => clearInterval(interval)
  }, [shouldReduceMotion])

  const displayActive = hoveredNode !== null ? hoveredNode : activeNode
  const activeData = PIPELINE_NODES[displayActive]

  return (
    <div className={cn('relative w-full flex flex-col items-center gap-6', className)}>

      {/* ─── Header label ─── */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.3 }}
        className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface border border-border/60 shadow-sm"
      >
        <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">
          RAG Pipeline
        </span>
        <span className="w-2 h-2 rounded-full bg-success animate-pulse" style={{ animationDelay: '0.5s' }} />
      </motion.div>

      {/* ─── Pipeline card ─── */}
      <motion.div
        className="relative w-full max-w-md"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.5 }}
      >
        {/* Card background */}
        <div className="relative bg-surface/80 backdrop-blur-xl rounded-2xl border border-border/60 shadow-xl overflow-hidden">
          {/* Subtle inner glow matching active node */}
          <motion.div
            className="absolute inset-0 rounded-2xl pointer-events-none"
            animate={{ boxShadow: `inset 0 0 60px ${activeData.colorSubtle}` }}
            transition={{ duration: 0.6 }}
          />

          {/* Flowing progress bar at top */}
          <div className="relative h-1 bg-border/30 overflow-hidden rounded-t-2xl">
            <motion.div
              className="absolute left-0 top-0 h-full rounded-full"
              style={{ background: `linear-gradient(to right, ${activeData.color}80, ${activeData.color})` }}
              animate={{
                width: `${((displayActive + 1) / PIPELINE_NODES.length) * 100}%`,
                boxShadow: `0 0 12px ${activeData.color}`,
              }}
              transition={{ duration: 0.5, ease: 'easeInOut' }}
            />
            {/* Traveling particle */}
            {!shouldReduceMotion && (
              <motion.div
                className="absolute top-0 h-full w-8 rounded-full"
                style={{
                  background: `linear-gradient(to right, transparent, ${activeData.color}, transparent)`,
                  filter: `blur(2px)`,
                }}
                animate={{ left: ['-5%', '105%'] }}
                transition={{ duration: TOTAL_DURATION, repeat: Infinity, ease: 'linear' }}
              />
            )}
          </div>

          {/* Pipeline nodes */}
          <div className="p-4 space-y-1.5">
            {PIPELINE_NODES.map((node, idx) => {
              const isActive = displayActive === idx
              const isCompleted = idx < displayActive

              return (
                <motion.div
                  key={node.id}
                  onMouseEnter={() => setHoveredNode(idx)}
                  onMouseLeave={() => setHoveredNode(null)}
                  className={cn(
                    'relative flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-300',
                    isActive
                      ? 'bg-surface shadow-md'
                      : 'hover:bg-surface/60',
                  )}
                  animate={{
                    scale: isActive ? 1.02 : 1,
                    opacity: isCompleted ? 0.6 : 1,
                  }}
                  transition={{ duration: 0.3 }}
                >
                  {/* Active border */}
                  {isActive && (
                    <motion.div
                      layoutId="active-border"
                      className="absolute inset-0 rounded-xl border-2 pointer-events-none"
                      style={{ borderColor: node.color }}
                      transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                    />
                  )}

                  {/* Connection line (except last) */}
                  {idx < PIPELINE_NODES.length - 1 && (
                    <div
                      className="absolute left-[22px] top-full w-0.5 h-1.5 z-10"
                      style={{
                        background: isCompleted
                          ? node.color
                          : 'hsl(215 15% 85%)',
                        opacity: 0.6,
                      }}
                    />
                  )}

                  {/* Step icon */}
                  <div
                    className="relative flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center"
                    style={{
                      background: isActive || isCompleted ? node.colorSubtle : 'hsl(215 15% 95%)',
                    }}
                  >
                    <node.icon
                      className="w-4 h-4 transition-colors duration-300"
                      style={{ color: isActive || isCompleted ? node.color : 'hsl(215 15% 60%)' }}
                    />
                    {/* Completed checkmark */}
                    {isCompleted && (
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        className="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full flex items-center justify-center"
                        style={{ background: node.color }}
                      >
                        <svg className="w-2 h-2 text-white" fill="none" viewBox="0 0 8 8">
                          <path d="M1.5 4L3 5.5L6.5 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </motion.div>
                    )}
                    {/* Active pulse ring */}
                    {isActive && !shouldReduceMotion && (
                      <motion.div
                        className="absolute inset-0 rounded-lg"
                        style={{ border: `2px solid ${node.color}` }}
                        animate={{ scale: [1, 1.6, 1.6], opacity: [0.8, 0, 0] }}
                        transition={{ duration: 1.2, repeat: Infinity, ease: 'easeOut' }}
                      />
                    )}
                  </div>

                  {/* Text */}
                  <div className="flex-1 min-w-0">
                    <p
                      className="text-sm font-semibold leading-none"
                      style={{ color: isActive ? node.color : isCompleted ? 'hsl(215 20% 40%)' : 'hsl(215 20% 55%)' }}
                    >
                      {node.label}
                    </p>
                    {isActive && (
                      <motion.p
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="text-xs mt-0.5 leading-none"
                        style={{ color: 'hsl(215 15% 55%)' }}
                      >
                        {node.description}
                      </motion.p>
                    )}
                  </div>

                  {/* Step number / status */}
                  <div
                    className="flex-shrink-0 text-xs font-mono font-bold tabular-nums"
                    style={{ color: isActive ? node.color : 'hsl(215 15% 70%)' }}
                  >
                    {String(idx + 1).padStart(2, '0')}
                  </div>
                </motion.div>
              )
            })}
          </div>

          {/* Footer stats */}
          <div className="px-4 pb-4 pt-2 border-t border-border/40 flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
              <span className="text-xs text-muted-foreground font-medium">Live Processing</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-center">
                <div className="text-xs font-bold text-foreground">99.2%</div>
                <div className="text-[10px] text-muted-foreground">Accuracy</div>
              </div>
              <div className="h-4 w-px bg-border/50" />
              <div className="text-center">
                <div className="text-xs font-bold text-foreground">~240ms</div>
                <div className="text-[10px] text-muted-foreground">Latency</div>
              </div>
            </div>
          </div>
        </div>

        {/* Outer glow effect */}
        <motion.div
          className="absolute inset-0 rounded-2xl -z-10 blur-2xl"
          animate={{ opacity: [0.15, 0.25, 0.15] }}
          transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
          style={{ background: `radial-gradient(ellipse at center, ${activeData.color}30 0%, transparent 70%)` }}
        />
      </motion.div>

      {/* ─── Floating info badge ─── */}
      <AnimatePresence mode="wait">
        <motion.div
          key={displayActive}
          initial={{ opacity: 0, y: 8, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -8, scale: 0.95 }}
          transition={{ duration: 0.3 }}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border/50 bg-surface/70 backdrop-blur-md shadow-sm"
        >
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: activeData.color }}
          />
          <span className="text-xs text-muted-foreground font-medium">
            Step {displayActive + 1}/{PIPELINE_NODES.length} —{' '}
          </span>
          <span className="text-xs font-semibold" style={{ color: activeData.color }}>
            {activeData.label}
          </span>
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
