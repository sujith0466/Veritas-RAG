import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, useReducedMotion } from 'framer-motion'
import { BookOpen, ExternalLink, AlertCircle, RefreshCw, FileText } from 'lucide-react'
import { Link } from 'react-router-dom'
import { analyticsService } from '@/services/analyticsService'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Skeleton } from '@/components/common/Skeleton'
import { Button } from '@/components/common/Button'
import { Badge } from '@/components/common/Badge'
import type { MostCitedDocumentDTO } from '@/types'

interface MostCitedDocumentsCardProps {
  startTime?: string
  endTime?: string
}

export function MostCitedDocumentsCard({ startTime, endTime }: MostCitedDocumentsCardProps) {
  const shouldReduceMotion = useReducedMotion()

  const { data, isLoading, error, refetch, isFetching } = useQuery<MostCitedDocumentDTO[]>({
    queryKey: ['most-cited-documents', startTime, endTime],
    queryFn: () => analyticsService.getMostCitedDocuments(startTime, endTime),
    staleTime: 5 * 60 * 1000,
  })

  const maxCitations = React.useMemo(() => {
    if (!data || data.length === 0) return 1
    return Math.max(...data.map((d) => d.citation_count), 1)
  }, [data])

  return (
    <motion.div
      initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: shouldReduceMotion ? 0.1 : 0.35, delay: 0.2 }}
      className="h-full"
    >
      <Card className="h-full flex flex-col border border-border/60 bg-card/60 dark:bg-slate-900/60 backdrop-blur-xl rounded-2xl overflow-hidden shadow-sm hover:border-border transition-colors">
        <CardHeader className="pb-3 border-b border-border/30">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                <BookOpen className="w-4 h-4" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold text-foreground">
                  Most Cited Knowledge Assets
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  Corpus documents most frequently retrieved and cited as evidence in RAG answers
                </CardDescription>
              </div>
            </div>

            <Button
              variant="ghost"
              size="sm"
              asChild
              className="h-8 text-xs gap-1.5 text-muted-foreground hover:text-foreground"
            >
              <Link to="/documents">
                <span>View All Docs</span>
                <ExternalLink className="w-3 h-3" />
              </Link>
            </Button>
          </div>
        </CardHeader>

        <CardContent className="flex-1 p-4 flex flex-col justify-between">
          {isLoading ? (
            <div className="space-y-3 py-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="p-3 rounded-xl border border-border/40 bg-muted/20 space-y-2">
                  <div className="flex justify-between items-center">
                    <Skeleton className="h-4 w-3/5 rounded" />
                    <Skeleton className="h-4 w-16 rounded" />
                  </div>
                  <Skeleton className="h-1.5 w-full rounded-full" />
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-center space-y-2">
              <AlertCircle className="w-8 h-8 text-destructive/70" />
              <p className="text-xs text-muted-foreground">Failed to load citation analytics</p>
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
              <FileText className="w-8 h-8 text-indigo-400/50 mb-2" />
              <p className="text-xs font-semibold text-foreground">No citation records in this window</p>
              <p className="text-[11px] text-muted-foreground mt-1 max-w-xs">
                As chat queries retrieve and cite knowledge chunks, top assets will be indexed here.
              </p>
            </div>
          ) : (
            <div className="space-y-2.5 max-h-[300px] overflow-y-auto pr-1 custom-scrollbar">
              {data.map((doc, i) => {
                const percentage = Math.round((doc.citation_count / maxCitations) * 100)
                return (
                  <div
                    key={doc.document_id}
                    className="p-3 rounded-xl border border-border/50 bg-background/50 hover:bg-muted/40 transition-colors space-y-2 group"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2.5 overflow-hidden">
                        <span className="font-mono text-[10px] font-bold text-muted-foreground/80 w-5 shrink-0">
                          #{i + 1}
                        </span>
                        <div className="flex items-center gap-1.5 overflow-hidden">
                          <FileText className="w-3.5 h-3.5 text-muted-foreground shrink-0 group-hover:text-primary transition-colors" />
                          <span
                            className="text-xs font-medium text-foreground truncate group-hover:text-primary transition-colors"
                            title={doc.document_title}
                          >
                            {doc.document_title}
                          </span>
                        </div>
                      </div>

                      <Badge
                        variant="secondary"
                        className="font-mono text-[11px] font-semibold bg-muted/60 shrink-0"
                      >
                        {doc.citation_count} {doc.citation_count === 1 ? 'citation' : 'citations'}
                      </Badge>
                    </div>

                    {/* Proportional visual meter */}
                    <div className="h-1.5 w-full bg-muted/50 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full"
                        initial={shouldReduceMotion ? { width: `${percentage}%` } : { width: 0 }}
                        animate={{ width: `${percentage}%` }}
                        transition={{ duration: shouldReduceMotion ? 0 : 0.5, delay: i * 0.04 }}
                      />
                    </div>

                    {doc.last_cited_at && (
                      <div className="text-[10px] text-muted-foreground/70 font-mono text-right">
                        Last cited: {new Date(doc.last_cited_at).toLocaleDateString()}
                      </div>
                    )}
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
