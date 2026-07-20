import * as React from 'react'
import { motion } from 'framer-motion'
import { Eye, ChevronRight, Layers, ArrowLeftRight } from 'lucide-react'
import { Button } from '@/components/common'
import type { ChunkResponse } from '@/types'

interface ChunkListTableProps {
  chunks: ChunkResponse[]
  total: number
  page: number
  size: number
  onPageChange: (page: number) => void
  onSelectChunk: (chunk: ChunkResponse) => void
  isLoading: boolean
}

export function ChunkListTable({
  chunks,
  total,
  page,
  size,
  onPageChange,
  onSelectChunk,
  isLoading,
}: ChunkListTableProps) {
  const totalPages = Math.ceil(total / size) || 1

  if (isLoading) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 animate-pulse space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-14 bg-slate-800/50 rounded-lg w-full" />
        ))}
      </div>
    )
  }

  if (chunks.length === 0) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-12 text-center">
        <Layers className="w-12 h-12 text-slate-600 mx-auto mb-3" />
        <h4 className="text-base font-bold text-slate-300">No Document Chunks Found</h4>
        <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
          Select a processed document above and run our chunking pipeline (`recursive`, `markdown`, `table`, `code`) to generate structured knowledge chunks.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-950/50 text-slate-400 text-xs uppercase tracking-wider font-semibold">
              <th className="py-3.5 px-4 w-16">Idx</th>
              <th className="py-3.5 px-4">Content Preview</th>
              <th className="py-3.5 px-4 w-44">Section Path</th>
              <th className="py-3.5 px-4 w-28 text-center">Strategy</th>
              <th className="py-3.5 px-4 w-24 text-right">Tokens</th>
              <th className="py-3.5 px-4 w-24 text-right">Chars</th>
              <th className="py-3.5 px-4 w-24 text-center">Doubly-Linked</th>
              <th className="py-3.5 px-4 w-20 text-center">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-sm text-slate-300">
            {chunks.map((chunk) => {
              const hasPrev = Boolean(chunk.previous_chunk_id)
              const hasNext = Boolean(chunk.next_chunk_id)
              return (
                <motion.tr
                  key={chunk.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="hover:bg-slate-800/40 transition-colors group"
                >
                  <td className="py-3 px-4 font-mono font-bold text-indigo-400 text-xs">
                    #{chunk.chunk_index}
                  </td>
                  <td className="py-3 px-4">
                    <p className="line-clamp-2 text-xs text-slate-200 font-mono bg-slate-950/60 p-2 rounded border border-slate-800/80">
                      {chunk.content}
                    </p>
                  </td>
                  <td className="py-3 px-4">
                    {chunk.section_path && chunk.section_path.length > 0 ? (
                      <div className="flex flex-wrap gap-1 items-center">
                        {chunk.section_path.map((pathItem, idx) => (
                          <React.Fragment key={idx}>
                            {idx > 0 && <ChevronRight className="w-2.5 h-2.5 text-slate-600 shrink-0" />}
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-indigo-300 border border-slate-700 truncate max-w-[120px]">
                              {pathItem}
                            </span>
                          </React.Fragment>
                        ))}
                      </div>
                    ) : (
                      <span className="text-xs text-slate-600 italic">Root</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-center">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                      {chunk.strategy_used}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right font-mono text-xs text-slate-300">
                    {chunk.token_count}
                  </td>
                  <td className="py-3 px-4 text-right font-mono text-xs text-slate-400">
                    {chunk.character_count}
                  </td>
                  <td className="py-3 px-4 text-center">
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-[11px]">
                      <span className={hasPrev ? 'text-emerald-400 font-bold' : 'text-slate-600'}>←</span>
                      <ArrowLeftRight className="w-3 h-3 text-slate-500" />
                      <span className={hasNext ? 'text-emerald-400 font-bold' : 'text-slate-600'}>→</span>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onSelectChunk(chunk)}
                      className="p-1.5 text-slate-400 hover:text-indigo-400 hover:bg-indigo-500/10 rounded-lg"
                      title="Inspect Chunk Details"
                    >
                      <Eye className="w-4 h-4" />
                    </Button>
                  </td>
                </motion.tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination Bar */}
      <div className="px-6 py-3.5 bg-slate-950/80 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
        <div>
          Showing <span className="font-bold text-slate-200">{(page - 1) * size + 1}</span> to{' '}
          <span className="font-bold text-slate-200">{Math.min(page * size, total)}</span> of{' '}
          <span className="font-bold text-slate-200">{total}</span> chunks
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            className="px-3 py-1 text-xs"
          >
            Prev
          </Button>
          <span className="px-2 font-mono text-slate-300">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="secondary"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            className="px-3 py-1 text-xs"
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
