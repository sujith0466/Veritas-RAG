import * as React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Copy, Check, ArrowLeft, ArrowRight, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/common'
import type { ChunkDetailResponse } from '@/types'

interface ChunkDetailDrawerProps {
  chunk: ChunkDetailResponse | null
  isOpen: boolean
  onClose: () => void
  onNavigateToChunkId: (id: string) => void
}

export function ChunkDetailDrawer({
  chunk,
  isOpen,
  onClose,
  onNavigateToChunkId,
}: ChunkDetailDrawerProps) {
  const [copied, setCopied] = React.useState(false)

  const handleCopy = () => {
    if (!chunk) return
    navigator.clipboard.writeText(chunk.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <AnimatePresence>
      {isOpen && chunk && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50"
          />

          {/* Drawer Panel */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed top-0 right-0 h-full w-full max-w-2xl bg-slate-900 border-l border-slate-800 shadow-2xl z-50 flex flex-col overflow-hidden"
          >
            {/* Header */}
            <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 font-mono font-bold">
                  #{chunk.chunk_index}
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-100">Document Chunk Detail</h3>
                  <p className="text-xs text-slate-400 font-mono truncate max-w-xs">{chunk.id}</p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={onClose}
                className="p-2 text-slate-400 hover:text-slate-200"
              >
                <X className="w-5 h-5" />
              </Button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Doubly-Linked Neighbor Navigation Bar */}
              <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 flex items-center justify-between shadow-inner">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!chunk.previous_chunk_id}
                  onClick={() => chunk.previous_chunk_id && onNavigateToChunkId(chunk.previous_chunk_id)}
                  className="gap-2 text-xs"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  Prev Chunk
                </Button>
                <div className="text-center">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Doubly-Linked Graph Sequence</span>
                  <p className="text-xs font-mono text-indigo-400 font-bold mt-0.5">Sequence Position #{chunk.chunk_index}</p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!chunk.next_chunk_id}
                  onClick={() => chunk.next_chunk_id && onNavigateToChunkId(chunk.next_chunk_id)}
                  className="gap-2 text-xs"
                >
                  Next Chunk
                  <ArrowRight className="w-3.5 h-3.5" />
                </Button>
              </div>

              {/* Gauges & Metadata Summary */}
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3">
                  <p className="text-[10px] font-semibold text-slate-400 uppercase">Strategy Used</p>
                  <p className="text-sm font-bold text-indigo-400 capitalize mt-1">{chunk.strategy_used}</p>
                </div>
                <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3">
                  <p className="text-[10px] font-semibold text-slate-400 uppercase">Token Count</p>
                  <p className="text-sm font-bold text-slate-100 font-mono mt-1">{chunk.token_count} <span className="text-xs font-normal text-slate-500">tokens</span></p>
                </div>
                <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3">
                  <p className="text-[10px] font-semibold text-slate-400 uppercase">Character Count</p>
                  <p className="text-sm font-bold text-slate-100 font-mono mt-1">{chunk.character_count} <span className="text-xs font-normal text-slate-500">chars</span></p>
                </div>
              </div>

              {/* Section Path Breadcrumbs */}
              <div>
                <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Section Path Breadcrumb Hierarchy</h4>
                {chunk.section_path && chunk.section_path.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5 p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                    {chunk.section_path.map((item, idx) => (
                      <span key={idx} className="px-2 py-1 rounded bg-slate-800 border border-slate-700 text-xs text-indigo-300 font-medium">
                        {item}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-500 italic p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                    No section headings recorded (Root Level).
                  </p>
                )}
              </div>

              {/* Raw Chunk Content */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Normalized Chunk Body (`content`)</h4>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCopy}
                    className="gap-1.5 py-1 px-2 text-xs text-slate-300 hover:text-white"
                  >
                    {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    {copied ? 'Copied!' : 'Copy Content'}
                  </Button>
                </div>
                <pre className="bg-slate-950 p-4 rounded-xl border border-slate-800 text-xs text-slate-200 font-mono whitespace-pre-wrap leading-relaxed max-h-80 overflow-y-auto">
                  {chunk.content}
                </pre>
              </div>

              {/* SHA-256 Checksum & Embedded verification */}
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Content SHA-256 Hash:</span>
                  <span className="font-mono text-slate-300 text-[11px] truncate max-w-[320px]">{chunk.content_hash}</span>
                </div>
                <div className="flex items-center justify-between pt-2 border-t border-slate-800">
                  <span className="text-slate-400">Milestone 1 Zero-Embedding Boundary:</span>
                  <span className="inline-flex items-center gap-1 text-emerald-400 font-bold">
                    <ShieldCheck className="w-4 h-4" /> Not Embedded (False)
                  </span>
                </div>
              </div>

              {/* Raw Metadata JSON */}
              {chunk.metadata_json && Object.keys(chunk.metadata_json).length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Metadata JSON (`metadata_json`)</h4>
                  <pre className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-[11px] text-indigo-300 font-mono overflow-x-auto">
                    {JSON.stringify(chunk.metadata_json, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
