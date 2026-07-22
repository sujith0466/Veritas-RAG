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
      <div className="bg-surface/60 border border-border rounded-xl p-6 animate-pulse space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-14 bg-border/50 rounded-lg w-full" />
        ))}
      </div>
    )
  }

  if (chunks.length === 0) {
    return (
      <div className="bg-surface/60 border border-border rounded-xl p-12 text-center">
        <Layers className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
        <h4 className="text-base font-bold text-foreground">No Document Chunks Found</h4>
        <p className="text-xs text-muted-foreground mt-1 max-w-md mx-auto">
          Select a processed document above and run our chunking pipeline (`recursive`, `markdown`, `table`, `code`) to generate structured knowledge chunks.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-surface/60 border border-border rounded-xl overflow-hidden shadow-xl">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-border bg-background/50 text-muted-foreground text-xs uppercase tracking-wider font-semibold">
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
          <tbody className="divide-y divide-border/60 text-sm text-foreground">
            {chunks.map((chunk) => {
              const hasPrev = Boolean(chunk.previous_chunk_id)
              const hasNext = Boolean(chunk.next_chunk_id)
              return (
                <motion.tr
                  key={chunk.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="hover:bg-border/40 transition-colors group"
                >
                  <td className="py-3 px-4 font-mono font-bold text-indigo-400 text-xs">
                    #{chunk.chunk_index}
                  </td>
                  <td className="py-3 px-4">
                    <p className="line-clamp-2 text-xs text-foreground font-mono bg-background/60 p-2 rounded border border-border/80">
                      {chunk.content}
                    </p>
                  </td>
                  <td className="py-3 px-4">
                    {chunk.section_path && chunk.section_path.length > 0 ? (
                      <div className="flex flex-wrap gap-1 items-center">
                        {chunk.section_path.map((pathItem, idx) => (
                          <React.Fragment key={idx}>
                            {idx > 0 && <ChevronRight className="w-2.5 h-2.5 text-muted-foreground shrink-0" />}
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-border text-indigo-300 border border-border truncate max-w-[120px]">
                              {pathItem}
                            </span>
                          </React.Fragment>
                        ))}
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground italic">Root</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-center">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                      {chunk.strategy_used}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right font-mono text-xs text-foreground">
                    {chunk.token_count}
                  </td>
                  <td className="py-3 px-4 text-right font-mono text-xs text-muted-foreground">
                    {chunk.character_count}
                  </td>
                  <td className="py-3 px-4 text-center">
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-background border border-border text-[11px]">
                      <span className={hasPrev ? 'text-emerald-400 font-bold' : 'text-muted-foreground'}>←</span>
                      <ArrowLeftRight className="w-3 h-3 text-muted-foreground" />
                      <span className={hasNext ? 'text-emerald-400 font-bold' : 'text-muted-foreground'}>→</span>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onSelectChunk(chunk)}
                      className="p-1.5 text-muted-foreground hover:text-indigo-400 hover:bg-indigo-500/10 rounded-lg"
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
      <div className="px-6 py-3.5 bg-background/80 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
        <div>
          Showing <span className="font-bold text-foreground">{(page - 1) * size + 1}</span> to{' '}
          <span className="font-bold text-foreground">{Math.min(page * size, total)}</span> of{' '}
          <span className="font-bold text-foreground">{total}</span> chunks
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
          <span className="px-2 font-mono text-foreground">
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
