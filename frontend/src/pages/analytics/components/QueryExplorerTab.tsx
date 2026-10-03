import { useState } from 'react'
import { Search, Terminal, ArrowRight } from 'lucide-react'
import { Card, CardContent } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { LiveQueryMonitorTable } from './LiveQueryMonitorTable'
import type { QueryHistoryItemDTO } from '@/types'

interface QueryExplorerTabProps {
  items: QueryHistoryItemDTO[]
  total: number
  page: number
  pageSize: number
  isLoading: boolean
  outcomeFilter?: string
  selectedTraceId?: string | null
  onPageChange: (newPage: number) => void
  onOutcomeFilterChange: (outcome: string | undefined) => void
  onSelectTrace: (correlationId: string) => void
}

export function QueryExplorerTab({
  items,
  total,
  page,
  pageSize,
  isLoading,
  outcomeFilter,
  selectedTraceId,
  onPageChange,
  onOutcomeFilterChange,
  onSelectTrace,
}: QueryExplorerTabProps) {
  const [directTraceId, setDirectTraceId] = useState('')

  const handleDirectLookup = (e: React.FormEvent) => {
    e.preventDefault()
    if (directTraceId.trim()) {
      onSelectTrace(directTraceId.trim())
    }
  }

  return (
    <div className="space-y-6">
      {/* Direct Lookup Bar */}
      <Card className="border-border/60 bg-surface/60 backdrop-blur-xl shadow-sm">
        <CardContent className="p-4">
          <form onSubmit={handleDirectLookup} className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground whitespace-nowrap">
              <Terminal className="h-4 w-4 text-primary" />
              <span>Direct Trace ID Lookup:</span>
            </div>
            <div className="flex-1 relative">
              <input
                type="text"
                value={directTraceId}
                onChange={(e) => setDirectTraceId(e.target.value)}
                placeholder="Paste correlation ID or trace UUID (e.g., query-123e4567-e89b...)"
                className="w-full h-9 rounded-lg border border-border/60 bg-surface px-3 text-xs font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <Button
              type="submit"
              size="sm"
              disabled={!directTraceId.trim()}
              className="flex items-center gap-1.5 text-xs h-9 font-semibold"
            >
              <Search className="h-3.5 w-3.5" /> Inspect Trace <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Explorer Query Table */}
      <LiveQueryMonitorTable
        items={items}
        total={total}
        page={page}
        pageSize={pageSize}
        isLoading={isLoading}
        onPageChange={onPageChange}
        onOutcomeFilterChange={onOutcomeFilterChange}
        selectedOutcome={outcomeFilter}
        onSelectTrace={onSelectTrace}
        selectedTraceId={selectedTraceId}
      />
    </div>
  )
}
