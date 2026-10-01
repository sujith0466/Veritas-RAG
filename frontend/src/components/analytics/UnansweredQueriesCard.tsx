import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, useReducedMotion } from 'framer-motion'
import { AlertCircle, Search, RefreshCw, CheckCircle2, ShieldAlert } from 'lucide-react'
import { analyticsService } from '@/services/analyticsService'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Skeleton } from '@/components/common/Skeleton'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import { Badge } from '@/components/common/Badge'
import type { UnansweredQueryDTO } from '@/types'

interface UnansweredQueriesCardProps {
  startTime?: string
  endTime?: string
}

export function UnansweredQueriesCard({ startTime, endTime }: UnansweredQueriesCardProps) {
  const shouldReduceMotion = useReducedMotion()
  const [filterQuery, setFilterQuery] = React.useState('')

  const { data, isLoading, error, refetch, isFetching } = useQuery<UnansweredQueryDTO[]>({
    queryKey: ['unanswered-queries', startTime, endTime],
    queryFn: () => analyticsService.getUnansweredQueries(startTime, endTime),
    staleTime: 5 * 60 * 1000,
  })

  const filteredQueries = React.useMemo(() => {
    if (!data) return []
    if (!filterQuery.trim()) return data
    const query = filterQuery.toLowerCase()
    return data.filter(
      (q) =>
        q.query_text.toLowerCase().includes(query) ||
        q.outcome.toLowerCase().includes(query)
    )
  }, [data, filterQuery])

  const getOutcomeBadge = (outcome: string) => {
    const norm = outcome.toUpperCase()
    if (norm.includes('HALLUCINATION')) {
      return (
        <Badge variant="destructive" className="bg-rose-500/10 text-rose-400 border-rose-500/20 text-[10px] font-mono">
          Hallucination Blocked
        </Badge>
      )
    }
    if (norm.includes('LOW_CONFIDENCE')) {
      return (
        <Badge variant="outline" className="bg-amber-500/10 text-amber-400 border-amber-500/20 text-[10px] font-mono">
          Low Confidence
        </Badge>
      )
    }
    if (norm.includes('CLARIFICATION')) {
      return (
        <Badge variant="outline" className="bg-sky-500/10 text-sky-400 border-sky-500/20 text-[10px] font-mono">
          Clarification Required
        </Badge>
      )
    }
    if (norm.includes('RETRIES')) {
      return (
        <Badge variant="outline" className="bg-purple-500/10 text-purple-400 border-purple-500/20 text-[10px] font-mono">
          Max Retries
        </Badge>
      )
    }
    return (
      <Badge variant="outline" className="text-[10px] font-mono">
        {outcome.replace(/_/g, ' ')}
      </Badge>
    )
  }

  return (
    <motion.div
      initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: shouldReduceMotion ? 0.1 : 0.35, delay: 0.15 }}
      className="h-full"
    >
      <Card className="h-full flex flex-col border border-border/60 bg-card/60 dark:bg-slate-900/60 backdrop-blur-xl rounded-2xl overflow-hidden shadow-sm hover:border-border transition-colors">
        <CardHeader className="pb-3 border-b border-border/30">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <ShieldAlert className="w-4 h-4" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold text-foreground">
                  Unanswered & Blocked Query Forensics
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  Queries intercepted by safety guards, hallucination prevention, or low retrieval confidence
                </CardDescription>
              </div>
            </div>

            {data && data.length > 4 && (
              <div className="relative w-36 sm:w-44">
                <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  placeholder="Filter queries..."
                  value={filterQuery}
                  onChange={(e) => setFilterQuery(e.target.value)}
                  className="h-8 pl-8 text-xs bg-background/50 border-border/60"
                />
              </div>
            )}
          </div>
        </CardHeader>

        <CardContent className="flex-1 p-4 flex flex-col justify-between">
          {isLoading ? (
            <div className="space-y-3 py-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="p-3 rounded-xl border border-border/40 bg-muted/20 space-y-2">
                  <div className="flex justify-between items-center">
                    <Skeleton className="h-4 w-3/4 rounded" />
                    <Skeleton className="h-4 w-12 rounded" />
                  </div>
                  <div className="flex justify-between items-center">
                    <Skeleton className="h-4 w-24 rounded" />
                    <Skeleton className="h-3 w-16 rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-center space-y-2">
              <AlertCircle className="w-8 h-8 text-destructive/70" />
              <p className="text-xs text-muted-foreground">Failed to load query forensics</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => refetch()}
                disabled={isFetching}
                className="h-7 text-xs gap-1.5"
              >
                <RefreshCw className={`w-3 h-3 ${isFetching ? 'animate-spin' : ''}`} />
                Retry
              </Button>
            </div>
          ) : !data || data.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center border border-dashed border-border/40 rounded-xl bg-background/30">
              <CheckCircle2 className="w-8 h-8 text-emerald-400 mb-2" />
              <p className="text-xs font-semibold text-foreground">Zero blocked or unanswered queries</p>
              <p className="text-[11px] text-muted-foreground mt-1 max-w-xs">
                All executed queries in this time window met grounding verification standards.
              </p>
            </div>
          ) : filteredQueries.length === 0 ? (
            <div className="flex-1 flex items-center justify-center p-6 text-xs text-muted-foreground">
              No queries matching "{filterQuery}"
            </div>
          ) : (
            <div className="space-y-2.5 max-h-[300px] overflow-y-auto pr-1 custom-scrollbar">
              {filteredQueries.map((query, i) => (
                <div
                  key={i}
                  className="p-3 rounded-xl border border-border/50 bg-background/50 hover:bg-muted/40 transition-colors space-y-2"
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-xs font-medium text-foreground line-clamp-2 leading-relaxed" title={query.query_text}>
                      "{query.query_text}"
                    </p>
                    <span className="font-mono text-[11px] font-semibold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-md shrink-0">
                      {query.count}x
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1 border-t border-border/30">
                    <div className="flex items-center gap-1.5">
                      <span>Reason:</span>
                      {getOutcomeBadge(query.outcome)}
                    </div>
                    {query.last_seen && (
                      <span className="font-mono text-[10px] text-muted-foreground/70">
                        {new Date(query.last_seen).toLocaleDateString([], {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
