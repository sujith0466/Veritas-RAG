import React from 'react'
import {
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  ArrowRight,
  FileText,
  Activity,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/common/Table'
import type { QueryExecutionLedgerItemDTO } from '@/types'

interface ExecutionFlightRecorderProps {
  items: QueryExecutionLedgerItemDTO[]
  total: number
  page: number
  pageSize: number
  onPageChange: (newPage: number) => void
  search: string
  onSearchChange: (query: string) => void
  statusFilter: string
  onStatusFilterChange: (status: string) => void
  onInspectTrace: (queryId: string) => void
  isLoading: boolean
  timeWindow: string
}

const STATUS_FILTERS = [
  { label: 'All Outcomes', value: 'ALL' },
  { label: 'Success', value: 'SUCCESS' },
  { label: 'Clarifications', value: 'CLARIFICATION_REQUIRED' },
  { label: 'Hallucination Aborts', value: 'ABORTED_HALLUCINATION' },
  { label: 'Policy Blocks', value: 'POLICY_VIOLATION' },
]

export const ExecutionFlightRecorder: React.FC<ExecutionFlightRecorderProps> = ({
  items,
  total,
  page,
  pageSize,
  onPageChange,
  search,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  onInspectTrace,
  isLoading,
  timeWindow,
}) => {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  const getStatusBadge = (outcome: string) => {
    switch (outcome) {
      case 'SUCCESS':
        return <Badge variant="success" className="text-[10px]">SUCCESS</Badge>
      case 'CLARIFICATION_REQUIRED':
        return <Badge variant="default" className="text-[10px] bg-sky-500/10 text-sky-400 border-sky-500/20">CLARIFICATION</Badge>
      case 'ABORTED_HALLUCINATION':
        return <Badge variant="destructive" className="text-[10px]">HALLUCINATION</Badge>
      case 'ABORTED_LOW_CONFIDENCE':
        return <Badge variant="warning" className="text-[10px]">LOW CONFIDENCE</Badge>
      case 'POLICY_VIOLATION':
        return <Badge variant="destructive" className="text-[10px]">POLICY BLOCK</Badge>
      default:
        return <Badge variant="subtle" className="text-[10px]">{outcome}</Badge>
    }
  }

  return (
    <Card className="bg-card/60 backdrop-blur-md border border-border/70 shadow-sm flex flex-col">
      <CardHeader className="pb-3 border-b border-border/40">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base font-bold flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" />
              AI Execution Flight Recorder & Audit Ledger
            </CardTitle>
            <CardDescription className="text-xs">
              Forensic ledger of every query execution, self-correction attempt, and latency footprint.
            </CardDescription>
          </div>

          {/* Search Bar & Filter Options */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative min-w-[200px] sm:min-w-[260px]">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search queries by text..."
                value={search}
                onChange={(e) => onSearchChange(e.target.value)}
                className="w-full bg-background/60 border border-border/60 rounded-lg pl-8 pr-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            <div className="flex items-center bg-background/60 hover:bg-background/80 border border-border/60 hover:border-border rounded-lg p-1 text-xs transition-colors">
              <Filter className="h-3 w-3 text-muted-foreground ml-1.5 mr-1" />
              <select
                value={statusFilter}
                onChange={(e) => onStatusFilterChange(e.target.value)}
                className="bg-transparent text-foreground text-xs focus:outline-none cursor-pointer pr-1 [color-scheme:light] dark:[color-scheme:dark]"
                aria-label="Filter by outcome"
              >
                {STATUS_FILTERS.map((f) => (
                  <option
                    key={f.value}
                    value={f.value}
                    className="bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100 py-1"
                  >
                    {f.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-0 flex-1 flex flex-col">
        {isLoading ? (
          <div className="flex items-center justify-center p-12 text-xs text-muted-foreground">
            Loading execution ledger records...
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 text-center">
            <div className="h-10 w-10 rounded-full bg-muted/60 flex items-center justify-center mb-2">
              <FileText className="h-5 w-5 text-muted-foreground" />
            </div>
            <p className="text-sm font-semibold text-foreground">No Query Executions Recorded ({timeWindow.toUpperCase()})</p>
            <p className="text-xs text-muted-foreground mt-0.5 max-w-sm">
              No executions matched your search or selected time window. Expand the window or execute queries in chat.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-[38%]">Query Text</TableHead>
                  <TableHead>Outcome</TableHead>
                  <TableHead>Reliability</TableHead>
                  <TableHead>Latency</TableHead>
                  <TableHead>Retries</TableHead>
                  <TableHead className="text-right">Timestamp</TableHead>
                  <TableHead className="text-right">Forensics</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id} className="hover:bg-muted/30 transition-colors">
                    <TableCell className="font-medium max-w-[260px] truncate" title={item.query_text}>
                      {item.query_text}
                    </TableCell>
                    <TableCell>{getStatusBadge(item.outcome)}</TableCell>
                    <TableCell className="font-mono text-xs">
                      {item.reliability_score !== null
                        ? `${(item.reliability_score * 100).toFixed(0)}%`
                        : item.confidence_score !== null
                        ? `${(item.confidence_score * 100).toFixed(0)}%`
                        : 'N/A'}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {item.duration_ms ? `${Math.round(item.duration_ms).toLocaleString()}ms` : 'N/A'}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {item.retry_attempts > 0 ? (
                        <span className="text-amber-400 font-semibold">{item.retry_attempts}x</span>
                      ) : (
                        <span className="text-muted-foreground">0</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground text-xs font-mono">
                      {new Date(item.timestamp).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onInspectTrace(item.id)}
                        className="text-[11px] h-7 px-2 text-primary hover:text-primary/80 gap-1"
                      >
                        Inspect
                        <ArrowRight className="h-3 w-3" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {/* Pagination Bar */}
        {total > pageSize && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border/40 text-xs text-muted-foreground">
            <span>
              Showing {Math.min(total, (page - 1) * pageSize + 1)} to{' '}
              {Math.min(total, page * pageSize)} of {total.toLocaleString()} records
            </span>
            <div className="flex items-center gap-1.5">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onPageChange(page - 1)}
                disabled={page <= 1}
                className="h-7 px-2"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </Button>
              <span className="px-2 font-mono">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onPageChange(page + 1)}
                disabled={page >= totalPages}
                className="h-7 px-2"
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
