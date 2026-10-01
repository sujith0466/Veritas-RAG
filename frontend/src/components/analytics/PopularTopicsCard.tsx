import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, useReducedMotion } from 'framer-motion'
import { Hash, Search, AlertCircle, RefreshCw, Sparkles } from 'lucide-react'
import { analyticsService } from '@/services/analyticsService'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Skeleton } from '@/components/common/Skeleton'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import type { PopularTopicDTO } from '@/types'

interface PopularTopicsCardProps {
  startTime?: string
  endTime?: string
}

export function PopularTopicsCard({ startTime, endTime }: PopularTopicsCardProps) {
  const shouldReduceMotion = useReducedMotion()
  const [filterQuery, setFilterQuery] = React.useState('')

  const { data, isLoading, error, refetch, isFetching } = useQuery<PopularTopicDTO[]>({
    queryKey: ['popular-topics', startTime, endTime],
    queryFn: () => analyticsService.getPopularTopics(startTime, endTime),
    staleTime: 5 * 60 * 1000,
  })

  // Calculate highest count for proportional progress bars
  const maxCount = React.useMemo(() => {
    if (!data || data.length === 0) return 1
    return Math.max(...data.map((d) => d.count), 1)
  }, [data])

  const filteredTopics = React.useMemo(() => {
    if (!data) return []
    if (!filterQuery.trim()) return data
    const query = filterQuery.toLowerCase()
    return data.filter((t) => t.topic.toLowerCase().includes(query))
  }, [data, filterQuery])

  return (
    <motion.div
      initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: shouldReduceMotion ? 0.1 : 0.35, delay: 0.1 }}
      className="h-full"
    >
      <Card className="h-full flex flex-col border border-border/60 bg-card/60 dark:bg-slate-900/60 backdrop-blur-xl rounded-2xl overflow-hidden shadow-sm hover:border-border transition-colors">
        <CardHeader className="pb-3 border-b border-border/30">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
                <Hash className="w-4 h-4" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold text-foreground">
                  Topic Intelligence
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  Frequent semantic lexemes and inquiry themes across workspace queries
                </CardDescription>
              </div>
            </div>

            {data && data.length > 5 && (
              <div className="relative w-36 sm:w-44">
                <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  placeholder="Filter topics..."
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
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="space-y-1.5">
                  <div className="flex justify-between">
                    <Skeleton className="h-4 w-28 rounded" />
                    <Skeleton className="h-4 w-10 rounded" />
                  </div>
                  <Skeleton className="h-2 w-full rounded-full" />
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-center space-y-2">
              <AlertCircle className="w-8 h-8 text-destructive/70" />
              <p className="text-xs text-muted-foreground">Failed to load topic intelligence</p>
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
              <Sparkles className="w-8 h-8 text-blue-400/50 mb-2" />
              <p className="text-xs font-semibold text-foreground">No popular topics identified yet</p>
              <p className="text-[11px] text-muted-foreground mt-1 max-w-xs">
                Run RAG queries in Chat to build semantic topic intelligence for this workspace.
              </p>
            </div>
          ) : filteredTopics.length === 0 ? (
            <div className="flex-1 flex items-center justify-center p-6 text-xs text-muted-foreground">
              No topics matching "{filterQuery}"
            </div>
          ) : (
            <div className="space-y-3 max-h-[300px] overflow-y-auto pr-1 custom-scrollbar">
              {filteredTopics.map((topic, i) => {
                const percentage = Math.round((topic.count / maxCount) * 100)
                return (
                  <div key={i} className="group p-2 rounded-xl hover:bg-muted/40 transition-colors">
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <div className="flex items-center gap-2 overflow-hidden">
                        <span className="font-mono text-[10px] font-bold text-muted-foreground/80 w-5 shrink-0">
                          #{i + 1}
                        </span>
                        <span className="font-medium text-foreground truncate group-hover:text-primary transition-colors">
                          {topic.topic}
                        </span>
                      </div>
                      <span className="font-mono text-xs font-semibold text-muted-foreground bg-muted/60 px-2 py-0.5 rounded-md shrink-0">
                        {topic.count} {topic.count === 1 ? 'query' : 'queries'}
                      </span>
                    </div>

                    {/* Proportional visual bar */}
                    <div className="h-1.5 w-full bg-muted/50 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full"
                        initial={shouldReduceMotion ? { width: `${percentage}%` } : { width: 0 }}
                        animate={{ width: `${percentage}%` }}
                        transition={{ duration: shouldReduceMotion ? 0 : 0.5, delay: i * 0.04 }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
