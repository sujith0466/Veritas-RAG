import { Layers, Search, Zap, Filter } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import type { SearchAnalyticsDTO } from '@/types'

interface RetrievalQualityCardProps {
  searchAnalytics: SearchAnalyticsDTO | null
  isLoading?: boolean
}

export function RetrievalQualityCard({ searchAnalytics, isLoading }: RetrievalQualityCardProps) {
  if (isLoading || !searchAnalytics) {
    return (
      <Card className="border-border/60 bg-surface/60 backdrop-blur-xl shadow-lg">
        <CardHeader>
          <CardTitle className="text-base font-bold flex items-center gap-2">
            <Search className="h-4.5 w-4.5 text-primary animate-spin" />
            Hybrid Retrieval Quality & Stage Latencies
          </CardTitle>
        </CardHeader>
        <CardContent className="h-[220px] flex items-center justify-center text-xs text-muted-foreground">
          Loading retrieval analytics...
        </CardContent>
      </Card>
    )
  }

  const {
    total_searches,
    avg_dense_candidates,
    avg_sparse_candidates,
    avg_merged_unique,
    avg_retrieval_duration_ms,
  } = searchAnalytics

  return (
    <Card className="border-border/60 bg-surface/60 backdrop-blur-xl shadow-lg flex flex-col justify-between">
      <CardHeader className="pb-3 border-b border-border/40">
        <CardTitle className="text-base font-bold flex items-center gap-2">
          <Layers className="h-4.5 w-4.5 text-primary" />
          Hybrid Retrieval Quality & Stage Latencies
        </CardTitle>
        <CardDescription className="text-xs text-muted-foreground mt-0.5">
          Dense vector vs Sparse keyword candidate yield and RRF fusion deduplication
        </CardDescription>
      </CardHeader>

      <CardContent className="pt-5 space-y-5">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg bg-surface/80 border border-border/50 p-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
              <span>Avg Retrieval Latency</span>
              <Zap className="h-3.5 w-3.5 text-primary" />
            </div>
            <div className="text-xl font-bold text-foreground">
              {avg_retrieval_duration_ms.toFixed(1)} <span className="text-xs font-normal text-muted-foreground">ms</span>
            </div>
            <div className="text-[11px] text-muted-foreground mt-0.5">
              Across {total_searches} hybrid searches
            </div>
          </div>

          <div className="rounded-lg bg-surface/80 border border-border/50 p-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
              <span>RRF Merged Unique</span>
              <Filter className="h-3.5 w-3.5 text-emerald-500" />
            </div>
            <div className="text-xl font-bold text-foreground">
              {avg_merged_unique.toFixed(1)} <span className="text-xs font-normal text-muted-foreground">chunks</span>
            </div>
            <div className="text-[11px] text-muted-foreground mt-0.5">
              Post-fusion deduplicated yield
            </div>
          </div>
        </div>

        <div className="space-y-3 pt-1">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-foreground">Dense Vector Candidates (Qdrant)</span>
            <span className="font-semibold text-primary">{avg_dense_candidates.toFixed(1)} avg</span>
          </div>
          <div className="h-2 w-full bg-surface rounded-full overflow-hidden border border-border/40">
            <div
              className="h-full bg-primary rounded-full transition-all duration-700"
              style={{ width: `${Math.min(100, (avg_dense_candidates / Math.max(1, avg_dense_candidates + avg_sparse_candidates)) * 100)}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-xs pt-1">
            <span className="font-medium text-foreground">Sparse Keyword Candidates (BM25)</span>
            <span className="font-semibold text-amber-500">{avg_sparse_candidates.toFixed(1)} avg</span>
          </div>
          <div className="h-2 w-full bg-surface rounded-full overflow-hidden border border-border/40">
            <div
              className="h-full bg-amber-500 rounded-full transition-all duration-700"
              style={{ width: `${Math.min(100, (avg_sparse_candidates / Math.max(1, avg_dense_candidates + avg_sparse_candidates)) * 100)}%` }}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
