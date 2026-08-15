import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { BookOpen, AlertCircle } from 'lucide-react'
import { analyticsService } from '@/services/analyticsService'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Skeleton } from '@/components/common/Skeleton'
import { Badge } from '@/components/common/Badge'

export function MostCitedDocumentsCard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['most-cited-documents'],
    queryFn: () => analyticsService.getMostCitedDocuments(),
    staleTime: 5 * 60 * 1000,
  })

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 }}
    >
      <Card className="h-full border-border/50 bg-card/50 backdrop-blur-sm transition-all hover:shadow-md hover:bg-card/80">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-indigo-500" />
              Most Cited Documents
            </CardTitle>
          </div>
          <CardDescription>
            The documents most frequently used as evidence in AI chat responses.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-12 w-full rounded-md" />
              ))}
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-6 text-muted-foreground text-sm">
              <AlertCircle className="h-8 w-8 mb-2 text-destructive/60" />
              <p>Failed to load most cited documents</p>
            </div>
          ) : !data || data.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center text-muted-foreground text-sm border-2 border-dashed border-border/50 rounded-lg bg-background/50">
              <p>No citation data available yet.</p>
              <p className="text-xs mt-1">Chat responses will populate this list.</p>
            </div>
          ) : (
            <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
              {data.map((doc: any, i: number) => (
                <div
                  key={doc.document_id}
                  className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-background/50 hover:bg-muted/50 transition-colors group"
                >
                  <div className="flex items-center gap-3 overflow-hidden">
                    <div className="flex-shrink-0 flex items-center justify-center w-6 text-sm font-bold text-muted-foreground group-hover:text-foreground transition-colors">
                      #{i + 1}
                    </div>
                    <div className="flex flex-col overflow-hidden">
                      <span className="text-sm font-medium text-foreground truncate" title={doc.document_title}>
                        {doc.document_title}
                      </span>
                      {doc.last_cited_at && (
                        <span className="text-xs text-muted-foreground truncate">
                          Last cited: {new Date(doc.last_cited_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>
                  <Badge variant="secondary" className="ml-2 flex-shrink-0 font-mono">
                    {doc.citation_count} citations
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
