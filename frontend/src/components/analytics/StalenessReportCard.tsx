import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, useReducedMotion } from 'framer-motion'
import { Clock, RefreshCw, AlertTriangle, CheckCircle2, ShieldCheck, Check, ExternalLink } from 'lucide-react'
import { Link } from 'react-router-dom'
import { knowledgeHealthService } from '@/services/knowledgeHealthService'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Skeleton } from '@/components/common/Skeleton'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import type { StalenessReportDTO, StaleDocumentItemDTO } from '@/types'

export function StalenessReportCard() {
  const shouldReduceMotion = useReducedMotion()
  const queryClient = useQueryClient()
  const currentWorkspace = useWorkspaceStore((s) => s.currentWorkspace)
  const [remediationFeedback, setRemediationFeedback] = useState<string | null>(null)

  const { data, isLoading, error, refetch, isFetching } = useQuery<StalenessReportDTO>({
    queryKey: ['staleness-report', currentWorkspace?.id],
    queryFn: () => knowledgeHealthService.getStalenessReport(currentWorkspace?.id as string),
    enabled: !!currentWorkspace?.id,
    staleTime: 5 * 60 * 1000,
  })

  const remediationMutation = useMutation({
    mutationFn: (action: 'MARK_REVIEWED') => {
      if (!currentWorkspace?.id || !data?.stale_documents || data.stale_documents.length === 0) {
        return Promise.resolve(null)
      }
      const documentIds = data.stale_documents.map((d: StaleDocumentItemDTO) => d.document_id)
      return knowledgeHealthService.executeBulkRemediation(currentWorkspace.id, {
        action,
        document_ids: documentIds,
      })
    },
    onSuccess: () => {
      setRemediationFeedback('Successfully marked stale documents as reviewed and fresh.')
      setTimeout(() => setRemediationFeedback(null), 4000)
      queryClient.invalidateQueries({ queryKey: ['staleness-report'] })
    },
  })

  const handleReviewAll = async () => {
    await remediationMutation.mutateAsync('MARK_REVIEWED')
  }

  const staleCount = data?.stale_count ?? 0
  const totalCount = data?.total_documents ?? 0

  return (
    <motion.div
      initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: shouldReduceMotion ? 0.1 : 0.35, delay: 0.25 }}
      className="h-full"
    >
      <Card className="h-full flex flex-col border border-border/60 bg-card/60 dark:bg-slate-900/60 backdrop-blur-xl rounded-2xl overflow-hidden shadow-sm hover:border-border transition-colors">
        <CardHeader className="pb-3 border-b border-border/30">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
                <Clock className="w-4 h-4" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold text-foreground">
                  Knowledge Staleness & Health
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  Document aging distribution, freshness decay, and remediation actions
                </CardDescription>
              </div>
            </div>

            {data && staleCount > 0 && (
              <Badge
                variant="destructive"
                className="bg-rose-500/10 text-rose-400 border border-rose-500/20 font-mono text-xs px-2.5 py-0.5"
              >
                {staleCount} Stale ({totalCount > 0 ? `${((staleCount / totalCount) * 100).toFixed(0)}%` : ''})
              </Badge>
            )}
          </div>
        </CardHeader>

        <CardContent className="flex-1 p-4 flex flex-col justify-between gap-4">
          {isLoading ? (
            <div className="space-y-3 py-2">
              <div className="grid grid-cols-3 gap-2">
                <Skeleton className="h-10 rounded-lg" />
                <Skeleton className="h-10 rounded-lg" />
                <Skeleton className="h-10 rounded-lg" />
              </div>
              <Skeleton className="h-14 w-full rounded-xl" />
              <Skeleton className="h-14 w-full rounded-xl" />
            </div>
          ) : error ? (
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-center space-y-2">
              <AlertTriangle className="w-8 h-8 text-destructive/70" />
              <p className="text-xs text-muted-foreground">Failed to load staleness report</p>
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
          ) : !data || staleCount === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center border border-dashed border-border/40 rounded-xl bg-background/30">
              <CheckCircle2 className="w-8 h-8 text-emerald-400 mb-2" />
              <p className="text-xs font-semibold text-foreground">All workspace documents are fresh</p>
              <p className="text-[11px] text-muted-foreground mt-1 max-w-xs">
                Zero documents exceed staleness thresholds. Knowledge vectors remain active and verified.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Aging breakdown distribution cards */}
              {data.aging_distribution && (
                <div className="grid grid-cols-3 gap-2 text-center">
                  {Object.entries(data.aging_distribution).map(([range, count], idx) => (
                    <div
                      key={idx}
                      className="p-2 rounded-xl bg-muted/30 border border-border/40 space-y-0.5"
                    >
                      <div className="text-[10px] uppercase font-mono text-muted-foreground/80">{range}</div>
                      <div className="text-sm font-bold font-mono text-foreground">{count}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Stale document list */}
              <div className="space-y-2 max-h-[190px] overflow-y-auto pr-1 custom-scrollbar">
                {data.stale_documents.map((doc) => (
                  <div
                    key={doc.document_id}
                    className="p-2.5 rounded-xl border border-border/50 bg-background/50 hover:bg-muted/40 transition-colors flex items-center justify-between gap-3"
                  >
                    <div className="overflow-hidden space-y-0.5">
                      <p className="text-xs font-medium text-foreground truncate" title={doc.filename}>
                        {doc.filename}
                      </p>
                      <div className="flex items-center gap-2 text-[10px] text-muted-foreground font-mono">
                        <span>Age: {doc.age_days}d</span>
                        <span>•</span>
                        <span>Freshness: {doc.freshness_score.toFixed(0)}%</span>
                      </div>
                    </div>

                    <Badge
                      variant={doc.is_expired ? 'destructive' : 'outline'}
                      className="text-[10px] font-mono shrink-0"
                    >
                      {doc.is_expired ? 'Expired' : 'Stale'}
                    </Badge>
                  </div>
                ))}
              </div>

              {/* Remediation feedback */}
              {remediationFeedback && (
                <div className="flex items-center gap-1.5 p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
                  <Check className="w-3.5 h-3.5 shrink-0" />
                  <span>{remediationFeedback}</span>
                </div>
              )}

              {/* Safe Remediation & Inspection Actions */}
              <div className="pt-2 border-t border-border/30 flex items-center justify-between gap-2 flex-wrap">
                <span className="text-[11px] text-muted-foreground font-medium">Remediation:</span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleReviewAll}
                    disabled={remediationMutation.isPending}
                    className="h-7 px-2.5 text-xs gap-1 border-border/60 hover:bg-muted"
                    title="Mark stale documents as reviewed and fresh"
                  >
                    <ShieldCheck className="w-3 h-3 text-emerald-400" />
                    <span>{remediationMutation.isPending ? 'Reviewing...' : 'Mark Reviewed'}</span>
                  </Button>

                  <Button
                    variant="ghost"
                    size="sm"
                    asChild
                    className="h-7 px-2.5 text-xs gap-1 text-muted-foreground hover:text-foreground"
                    title="Inspect documents in document repository"
                  >
                    <Link to="/documents">
                      <span>Inspect Docs</span>
                      <ExternalLink className="w-3 h-3" />
                    </Link>
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
