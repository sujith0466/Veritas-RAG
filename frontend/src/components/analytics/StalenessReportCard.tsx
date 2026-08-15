import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Clock, Archive, RefreshCw, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { knowledgeHealthService } from '@/services/knowledgeHealthService'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Skeleton } from '@/components/common/Skeleton'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'

export function StalenessReportCard() {
  const queryClient = useQueryClient()
  const currentWorkspace = useWorkspaceStore((s) => s.currentWorkspace)
  const [isRemediating, setIsRemediating] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['staleness-report', currentWorkspace?.id],
    queryFn: () => knowledgeHealthService.getStalenessReport(currentWorkspace?.id as string),
    enabled: !!currentWorkspace?.id,
    staleTime: 5 * 60 * 1000,
  })

  const remediationMutation = useMutation({
    mutationFn: (action: 'MARK_REVIEWED' | 'ARCHIVE' | 'REPROCESS') => {
      if (!currentWorkspace?.id || !data?.stale_documents) return Promise.resolve(null)
      const documentIds = data.stale_documents.map((d: any) => d.document_id)
      return knowledgeHealthService.executeBulkRemediation(currentWorkspace.id, {
        action,
        document_ids: documentIds,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['staleness-report'] })
    },
  })

  const handleRemediation = async (action: 'MARK_REVIEWED' | 'ARCHIVE' | 'REPROCESS') => {
    setIsRemediating(true)
    try {
      await remediationMutation.mutateAsync(action)
    } finally {
      setIsRemediating(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.2 }}
    >
      <Card className="h-full border-border/50 bg-card/50 backdrop-blur-sm transition-all hover:shadow-md hover:bg-card/80 flex flex-col">
        <CardHeader className="pb-3 shrink-0">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <Clock className="w-5 h-5 text-amber-500" />
              Document Staleness Report
            </CardTitle>
            {data && data.stale_count > 0 && (
              <Badge variant="destructive" className="animate-pulse">
                {data.stale_count} Stale
              </Badge>
            )}
          </div>
          <CardDescription>
            Identify and remediate outdated documents dragging down knowledge health.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex-1 flex flex-col">
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-14 w-full rounded-md" />
              ))}
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-6 text-muted-foreground text-sm flex-1">
              <AlertTriangle className="h-8 w-8 mb-2 text-destructive/60" />
              <p>Failed to load staleness report</p>
            </div>
          ) : !data || data.stale_documents?.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center text-muted-foreground text-sm border-2 border-dashed border-border/50 rounded-lg bg-background/50 flex-1">
              <CheckCircle2 className="h-10 w-10 mb-3 text-success/60" />
              <p className="font-medium text-foreground">All documents are fresh!</p>
              <p className="text-xs mt-1">No stale documents require remediation.</p>
            </div>
          ) : (
            <div className="flex flex-col h-full justify-between gap-4">
              <div className="space-y-3 max-h-[220px] overflow-y-auto pr-2 custom-scrollbar">
                {data.stale_documents.map((doc: any) => (
                  <div
                    key={doc.document_id}
                    className="flex flex-col p-3 rounded-lg border border-border/50 bg-background/50 hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-foreground truncate" title={doc.filename}>
                        {doc.filename}
                      </span>
                      <Badge variant={doc.is_expired ? 'destructive' : 'warning'} className="text-[10px]">
                        {doc.age_days} days old
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>Health Score: {doc.freshness_score.toFixed(1)}</span>
                      <span>Updated: {new Date(doc.last_updated_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                ))}
              </div>
              
              <div className="flex flex-wrap gap-2 pt-3 border-t border-border/50 shrink-0">
                <Button 
                  size="sm" 
                  variant="outline" 
                  onClick={() => handleRemediation('MARK_REVIEWED')}
                  isLoading={isRemediating && remediationMutation.variables === 'MARK_REVIEWED'}
                  disabled={isRemediating}
                  className="flex-1 text-xs"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1.5 text-success" />
                  Mark Reviewed
                </Button>
                <Button 
                  size="sm" 
                  variant="outline" 
                  onClick={() => handleRemediation('REPROCESS')}
                  isLoading={isRemediating && remediationMutation.variables === 'REPROCESS'}
                  disabled={isRemediating}
                  className="flex-1 text-xs"
                >
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5 text-primary" />
                  Reprocess
                </Button>
                <Button 
                  size="sm" 
                  variant="outline" 
                  onClick={() => handleRemediation('ARCHIVE')}
                  isLoading={isRemediating && remediationMutation.variables === 'ARCHIVE'}
                  disabled={isRemediating}
                  className="flex-1 text-xs hover:bg-destructive/10 hover:text-destructive border-destructive/20"
                >
                  <Archive className="w-3.5 h-3.5 mr-1.5" />
                  Archive All
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
