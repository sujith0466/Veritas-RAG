import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { AlertCircle } from 'lucide-react'
import { analyticsService } from '@/services/analyticsService'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Skeleton } from '@/components/common/Skeleton'

export function UnansweredQueriesCard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['unanswered-queries'],
    queryFn: () => analyticsService.getUnansweredQueries(),
    staleTime: 5 * 60 * 1000,
  })

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.2 }}
      className="h-full"
    >
      <Card className="h-full border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-amber-500" />
            <CardTitle>Unanswered Queries</CardTitle>
          </div>
          <CardDescription>
            Queries that resulted in a non-success outcome.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : error ? (
            <div className="text-sm text-destructive">Failed to load queries.</div>
          ) : data?.length === 0 ? (
            <div className="text-sm text-muted-foreground text-center py-4">No unanswered queries!</div>
          ) : (
            <div className="space-y-4 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
              {data?.map((query, i) => (
                <div key={i} className="flex flex-col gap-1 p-3 rounded-md bg-muted/50 border border-border/50">
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-sm font-medium line-clamp-2" title={query.query_text}>{query.query_text}</span>
                    <span className="text-xs font-semibold text-amber-600 bg-amber-500/10 px-2 py-0.5 rounded-full whitespace-nowrap">
                      {query.count} {query.count === 1 ? 'time' : 'times'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-xs text-muted-foreground truncate" title={query.outcome}>
                      {query.outcome.replace(/_/g, ' ')}
                    </span>
                    {query.last_seen && (
                      <span className="text-[10px] text-muted-foreground">
                        {new Date(query.last_seen).toLocaleDateString()}
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
