import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Database, FileText, Layers, HardDrive, ArrowUpRight } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import type { CommandKnowledgeHealthDTO } from '@/types'

interface KnowledgePipelineCardProps {
  knowledge: CommandKnowledgeHealthDTO
  isLoading: boolean
}

export const KnowledgePipelineCard: React.FC<KnowledgePipelineCardProps> = ({
  knowledge,
  isLoading,
}) => {
  const navigate = useNavigate()

  return (
    <Card className="bg-card/60 backdrop-blur-md border border-border/70 shadow-sm flex flex-col h-full">
      <CardHeader className="pb-3 border-b border-border/40">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base font-bold flex items-center gap-2">
              <Database className="h-4 w-4 text-primary" />
              Knowledge Base & Vector Sync Health
            </CardTitle>
            <CardDescription className="text-xs">
              Document ingestion pipeline volume, chunk indexation, and background job queue.
            </CardDescription>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/documents')}
            className="text-xs text-primary hover:text-primary/80 gap-1 h-7 px-2"
          >
            Manage Docs
            <ArrowUpRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="p-4 flex-1 flex flex-col justify-between space-y-4">
        {/* Knowledge Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          <div className="p-2.5 rounded-lg bg-background/50 border border-border/50 text-xs">
            <span className="text-[10px] uppercase font-semibold text-muted-foreground flex items-center gap-1 mb-1">
              <FileText className="h-3 w-3 text-sky-400" />
              Documents
            </span>
            <span className="font-mono font-bold text-lg text-foreground block">
              {isLoading ? '...' : knowledge.total_documents.toLocaleString()}
            </span>
            <span className="text-[10px] text-emerald-400">
              {knowledge.processed_documents} ready
            </span>
          </div>

          <div className="p-2.5 rounded-lg bg-background/50 border border-border/50 text-xs">
            <span className="text-[10px] uppercase font-semibold text-muted-foreground flex items-center gap-1 mb-1">
              <Layers className="h-3 w-3 text-indigo-400" />
              Chunks
            </span>
            <span className="font-mono font-bold text-lg text-foreground block">
              {isLoading ? '...' : knowledge.total_chunks.toLocaleString()}
            </span>
            <span className="text-[10px] text-muted-foreground">Indexed fragments</span>
          </div>

          <div className="p-2.5 rounded-lg bg-background/50 border border-border/50 text-xs">
            <span className="text-[10px] uppercase font-semibold text-muted-foreground flex items-center gap-1 mb-1">
              <HardDrive className="h-3 w-3 text-emerald-400" />
              Embeddings
            </span>
            <span className="font-mono font-bold text-lg text-foreground block">
              {isLoading ? '...' : knowledge.total_embeddings.toLocaleString()}
            </span>
            <span className="text-[10px] text-emerald-400">Dense vectors</span>
          </div>

          <div className="p-2.5 rounded-lg bg-background/50 border border-border/50 text-xs">
            <span className="text-[10px] uppercase font-semibold text-muted-foreground flex items-center gap-1 mb-1">
              <Database className="h-3 w-3 text-primary" />
              Cluster Parity
            </span>
            <span className="font-mono font-bold text-lg text-foreground block capitalize">
              {knowledge.vector_status}
            </span>
            <span className="text-[10px] text-muted-foreground">Qdrant status</span>
          </div>
        </div>

        {/* Ingestion Queue Telemetry */}
        <div className="pt-3 border-t border-border/40 flex items-center justify-between text-xs">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-sky-400" />
              <span className="text-muted-foreground">Pending Ingestion Jobs:</span>
              <span className="font-mono font-bold text-foreground">
                {isLoading ? '...' : knowledge.pending_jobs}
              </span>
            </div>

            <div className="flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  knowledge.failed_jobs > 0 ? 'bg-rose-500 animate-pulse' : 'bg-emerald-500'
                }`}
              />
              <span className="text-muted-foreground">Failed Ingestion Jobs:</span>
              <span
                className={`font-mono font-bold ${
                  knowledge.failed_jobs > 0 ? 'text-rose-400' : 'text-foreground'
                }`}
              >
                {isLoading ? '...' : knowledge.failed_jobs}
              </span>
            </div>
          </div>

          {knowledge.failed_jobs > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/documents?status=FAILED')}
              className="text-[11px] h-6 px-2 text-rose-400 border-rose-500/30 hover:bg-rose-500/10"
            >
              Inspect Failures
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
