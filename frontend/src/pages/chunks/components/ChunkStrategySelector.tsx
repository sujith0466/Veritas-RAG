import * as React from 'react'
import { motion } from 'framer-motion'
import { Sliders, Zap, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/common'
import type { StrategyInfoDTO, DocumentResponse } from '@/types'

interface ChunkStrategySelectorProps {
  strategies: StrategyInfoDTO[]
  documents: DocumentResponse[]
  selectedDocId: string
  onSelectDocId: (id: string) => void
  onTriggerChunking: (docId: string, strategy: string | null, maxChars: number, overlap: number) => Promise<void>
  isProcessing: boolean
}

export function ChunkStrategySelector({
  strategies,
  documents,
  selectedDocId,
  onSelectDocId,
  onTriggerChunking,
  isProcessing,
}: ChunkStrategySelectorProps) {
  const [selectedStrategy, setSelectedStrategy] = React.useState<string>('recursive')
  const [maxChars, setMaxChars] = React.useState<number>(1000)
  const [overlapChars, setOverlapChars] = React.useState<number>(200)

  const currentStrategy = strategies.find((s) => s.name === selectedStrategy)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedDocId) return
    const strategyArg = selectedStrategy === 'auto' ? null : selectedStrategy
    onTriggerChunking(selectedDocId, strategyArg, maxChars, overlapChars)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl p-6 mb-6 shadow-xl"
    >
      <div className="flex items-center gap-3 mb-4 pb-4 border-b border-slate-800/80">
        <div className="w-10 h-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
          <Sliders className="w-5 h-5" />
        </div>
        <div>
          <h3 className="text-lg font-bold text-slate-100">Document Chunking Strategy Engine</h3>
          <p className="text-xs text-slate-400">Configure content-aware splitting parameters without embedding generation (`ADR-005`)</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Document Selector */}
        <div className="lg:col-span-1">
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
            Target Document
          </label>
          <select
            value={selectedDocId}
            onChange={(e) => onSelectDocId(e.target.value)}
            disabled={isProcessing}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors"
          >
            <option value="">-- Select Document --</option>
            {documents.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.original_filename} ({doc.status})
              </option>
            ))}
          </select>
          <p className="text-[11px] text-slate-500 mt-1">Select a PROCESSED document to split into chunks.</p>
        </div>

        {/* Strategy Grid Choice */}
        <div className="lg:col-span-2">
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
            Splitting Algorithm
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {strategies.map((strat) => {
              const isSelected = selectedStrategy === strat.name
              return (
                <button
                  key={strat.name}
                  type="button"
                  onClick={() => {
                    setSelectedStrategy(strat.name)
                    setMaxChars(strat.default_max_characters || 1000)
                    setOverlapChars(strat.default_overlap_characters || 200)
                  }}
                  disabled={isProcessing}
                  className={`p-2.5 rounded-lg border text-left transition-all relative ${
                    isSelected
                      ? 'bg-indigo-500/10 border-indigo-500 text-slate-100 shadow-md'
                      : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold capitalize">{strat.name}</span>
                    {isSelected && <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400" />}
                  </div>
                  <p className="text-[10px] text-slate-500 mt-1 line-clamp-2">{strat.display_name}</p>
                  {strat.is_placeholder && (
                    <span className="absolute top-1 right-1 px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/20 border border-amber-500/30 text-amber-400">
                      M2 Stub
                    </span>
                  )}
                </button>
              )
            })}
          </div>
          {currentStrategy && (
            <p className="text-xs text-slate-400 mt-2 bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/60">
              <span className="font-semibold text-indigo-400">{currentStrategy.display_name}:</span> {currentStrategy.description}
            </p>
          )}
        </div>

        {/* Sliders & Trigger */}
        <div className="lg:col-span-1 flex flex-col justify-between">
          <div>
            <div className="mb-4">
              <div className="flex justify-between text-xs font-semibold text-slate-300 mb-1">
                <span>Max Characters</span>
                <span className="text-indigo-400">{maxChars}</span>
              </div>
              <input
                type="range"
                min="200"
                max="5000"
                step="100"
                value={maxChars}
                onChange={(e) => setMaxChars(Number(e.target.value))}
                disabled={isProcessing || currentStrategy?.is_placeholder}
                className="w-full accent-indigo-500 bg-slate-800 h-1.5 rounded-lg cursor-pointer"
              />
            </div>

            <div className="mb-4">
              <div className="flex justify-between text-xs font-semibold text-slate-300 mb-1">
                <span>Overlap Characters</span>
                <span className="text-indigo-400">{overlapChars}</span>
              </div>
              <input
                type="range"
                min="0"
                max="500"
                step="25"
                value={overlapChars}
                onChange={(e) => setOverlapChars(Number(e.target.value))}
                disabled={isProcessing || currentStrategy?.is_placeholder}
                className="w-full accent-indigo-500 bg-slate-800 h-1.5 rounded-lg cursor-pointer"
              />
            </div>
          </div>

          <Button
            type="submit"
            variant="default"
            disabled={!selectedDocId || isProcessing || currentStrategy?.is_placeholder}
            className="w-full justify-center gap-2 py-2.5 shadow-lg shadow-indigo-500/20"
          >
            <Zap className="w-4 h-4" />
            {isProcessing ? 'Splitting Document...' : 'Execute Chunking Pipeline'}
          </Button>
        </div>
      </form>

      {currentStrategy?.is_placeholder && (
        <div className="mt-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-start gap-2.5 text-amber-300 text-xs">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <strong className="font-bold">Phase 2 Milestone 2 Dependency:</strong> Semantic similarity chunking requires dense embedding vectors from the upcoming Embedding Pipeline (`M2`). Please select `recursive`, `markdown`, `sentence`, `paragraph`, `table`, or `code` for Milestone 1.
          </div>
        </div>
      )}
    </motion.div>
  )
}
