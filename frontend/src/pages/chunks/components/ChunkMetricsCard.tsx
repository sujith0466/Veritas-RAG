import { motion } from 'framer-motion'
import { Layers, Hash, Cpu, AlertCircle } from 'lucide-react'
import type { ChunkMetricsDTO } from '@/types'

interface ChunkMetricsCardProps {
  metrics: ChunkMetricsDTO | null
  isLoading: boolean
}

export function ChunkMetricsCard({ metrics, isLoading }: ChunkMetricsCardProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-surface/60 border border-border rounded-xl p-5 animate-pulse h-28" />
        ))}
      </div>
    )
  }

  const totalChunks = metrics?.total_chunks || 0
  const avgTokens = Math.round(metrics?.average_chunk_tokens || 0)
  const avgChars = Math.round(metrics?.average_chunk_characters || 0)
  const breakdown = metrics?.strategy_breakdown || {}
  const embeddedCount = metrics?.is_embedded_count || 0

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-surface/60 backdrop-blur border border-border/80 rounded-xl p-5 flex items-center justify-between shadow-lg"
      >
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Total Chunks</p>
          <p className="text-2xl font-bold text-foreground mt-1">{totalChunks.toLocaleString()}</p>
          <p className="text-xs text-muted-foreground mt-1">Across active documents</p>
        </div>
        <div className="w-12 h-12 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
          <Layers className="w-6 h-6" />
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-surface/60 backdrop-blur border border-border/80 rounded-xl p-5 flex items-center justify-between shadow-lg"
      >
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Avg Token Density</p>
          <p className="text-2xl font-bold text-foreground mt-1">{avgTokens} <span className="text-xs font-normal text-muted-foreground">tokens</span></p>
          <p className="text-xs text-muted-foreground mt-1">~{avgChars} chars per chunk</p>
        </div>
        <div className="w-12 h-12 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
          <Hash className="w-6 h-6" />
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="bg-surface/60 backdrop-blur border border-border/80 rounded-xl p-5 flex items-center justify-between shadow-lg"
      >
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Strategies Used</p>
          <div className="flex flex-wrap gap-1 mt-2">
            {Object.keys(breakdown).length === 0 ? (
              <span className="text-xs text-muted-foreground">None</span>
            ) : (
              Object.entries(breakdown).map(([strat, count]) => (
                <span key={strat} className="px-2 py-0.5 text-xs rounded-md bg-border border border-border text-foreground font-medium">
                  {strat}: {count}
                </span>
              ))
            )}
          </div>
        </div>
        <div className="w-12 h-12 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
          <Cpu className="w-6 h-6" />
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="bg-surface/60 backdrop-blur border border-border/80 rounded-xl p-5 flex items-center justify-between shadow-lg"
      >
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Embedding Status</p>
          <p className="text-2xl font-bold text-amber-400 mt-1">{embeddedCount} <span className="text-xs font-normal text-muted-foreground">/ {totalChunks}</span></p>
          <p className="text-xs text-amber-500/80 mt-1 font-medium flex items-center gap-1">
            <AlertCircle className="w-3.5 h-3.5" /> Strictly Zero in Milestone 1
          </p>
        </div>
        <div className="w-12 h-12 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
          <AlertCircle className="w-6 h-6" />
        </div>
      </motion.div>
    </div>
  )
}
