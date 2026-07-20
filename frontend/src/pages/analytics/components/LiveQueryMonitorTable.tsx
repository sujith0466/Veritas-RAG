import { useState } from 'react'
import { ShieldCheck, ShieldAlert, HelpCircle, Clock, Filter, ChevronLeft, ChevronRight } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import type { QueryHistoryItemDTO } from '@/types'

interface LiveQueryMonitorTableProps {
  items: QueryHistoryItemDTO[]
  total: number
  page: number
  pageSize: number
  isLoading?: boolean
  onPageChange: (newPage: number) => void
  onOutcomeFilterChange: (outcome: string | undefined) => void
  selectedOutcome?: string
}

export function LiveQueryMonitorTable({
  items,
  total,
  page,
  pageSize,
  isLoading = false,
  onPageChange,
  onOutcomeFilterChange,
  selectedOutcome,
}: LiveQueryMonitorTableProps) {
  const [searchQuery, setSearchQuery] = useState('')

  const filteredItems = items.filter((item) =>
    item.query_text.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.correlation_id.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  const renderOutcomeBadge = (outcome: string) => {
    if (outcome === 'SUCCESS') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
          <ShieldCheck className="h-3 w-3" />
          Served (Verified)
        </span>
      )
    }
    if (outcome === 'CLARIFICATION_REQUIRED') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-500 border border-amber-500/20">
          <HelpCircle className="h-3 w-3" />
          Clarification Requested
        </span>
      )
    }
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-rose-500/10 text-rose-500 border border-rose-500/20">
        <ShieldAlert className="h-3 w-3" />
        {outcome.replace('ABORTED_', 'Aborted: ')}
      </span>
    )
  }

  return (
    <Card className="border-border/60 bg-surface/60 backdrop-blur-xl shadow-lg">
      <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border/40">
        <div>
          <CardTitle className="text-base font-bold flex items-center gap-2">
            <Clock className="h-4.5 w-4.5 text-primary" />
            Live AI Query Execution & Trace Monitor
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground mt-0.5">
            Granular audit trace of pre-generation confidence, verification status, and latencies
          </CardDescription>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Search input */}
          <input
            type="text"
            placeholder="Search queries or trace ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-8 rounded-md border border-border/60 bg-surface px-2.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary w-48"
          />

          {/* Outcome filter */}
          <div className="flex items-center gap-1.5 bg-surface px-2.5 h-8 rounded-md border border-border/60">
            <Filter className="h-3.5 w-3.5 text-muted-foreground" />
            <select
              value={selectedOutcome || ''}
              onChange={(e) => onOutcomeFilterChange(e.target.value || undefined)}
              className="bg-transparent text-xs text-foreground focus:outline-none border-none cursor-pointer"
            >
              <option value="" className="bg-surface text-foreground">All Outcomes</option>
              <option value="SUCCESS" className="bg-surface text-foreground">SUCCESS</option>
              <option value="CLARIFICATION_REQUIRED" className="bg-surface text-foreground">CLARIFICATION</option>
              <option value="ABORTED_LOW_CONFIDENCE" className="bg-surface text-foreground">ABORTED (LOW CONF)</option>
              <option value="ABORTED_HALLUCINATION" className="bg-surface text-foreground">ABORTED (HALLUCINATION)</option>
            </select>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-border/40 bg-surface/40 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                <th className="py-3 px-4">Timestamp & Trace</th>
                <th className="py-3 px-4">Query Text</th>
                <th className="py-3 px-4">Confidence</th>
                <th className="py-3 px-4">Outcome Status</th>
                <th className="py-3 px-4">Retries</th>
                <th className="py-3 px-4 text-right">Latency</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/30 text-xs">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-muted-foreground">
                    Loading query trace history...
                  </td>
                </tr>
              ) : filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-muted-foreground">
                    No query execution records match the selected criteria.
                  </td>
                </tr>
              ) : (
                filteredItems.map((item) => {
                  const conf = item.confidence_score ?? 0
                  const confColor =
                    conf >= 0.75 ? 'text-emerald-500 bg-emerald-500/10' : conf >= 0.4 ? 'text-amber-500 bg-amber-500/10' : 'text-rose-500 bg-rose-500/10'

                  return (
                    <tr key={item.id} className="hover:bg-surface/50 transition-colors">
                      <td className="py-3 px-4 whitespace-nowrap">
                        <div className="font-medium text-foreground">
                          {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </div>
                        <div className="text-[10px] text-muted-foreground font-mono mt-0.5 truncate max-w-[110px]" title={item.correlation_id}>
                          {item.correlation_id}
                        </div>
                      </td>
                      <td className="py-3 px-4 max-w-xs sm:max-w-md truncate text-foreground font-medium" title={item.query_text}>
                        {item.query_text}
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap">
                        {item.confidence_score === null ? (
                          <span className="text-muted-foreground text-[11px]">N/A</span>
                        ) : (
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold ${confColor}`}>
                            {(conf * 100).toFixed(0)}%
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap">
                        {renderOutcomeBadge(item.outcome)}
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap text-muted-foreground">
                        {item.retry_attempts > 0 ? (
                          <span className="font-semibold text-amber-500">{item.retry_attempts} loops</span>
                        ) : (
                          '0'
                        )}
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap text-right font-mono text-foreground font-semibold">
                        {item.total_duration_ms.toFixed(0)} ms
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination controls */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-border/40 text-xs text-muted-foreground bg-surface/30">
          <div>
            Showing <span className="font-semibold text-foreground">{(page - 1) * pageSize + (filteredItems.length > 0 ? 1 : 0)}</span> to{' '}
            <span className="font-semibold text-foreground">{(page - 1) * pageSize + filteredItems.length}</span> of{' '}
            <span className="font-semibold text-foreground">{total}</span> queries
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1 || isLoading}
              className="p-1 rounded border border-border bg-surface hover:bg-surface/80 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="font-medium text-foreground">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages || isLoading}
              className="p-1 rounded border border-border bg-surface hover:bg-surface/80 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
