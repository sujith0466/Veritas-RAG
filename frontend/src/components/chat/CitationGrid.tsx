

import { FileText, BookOpen } from 'lucide-react'

interface Citation {
  citation_index: number
  document_id: string
  source_name?: string
  document_name?: string
  excerpt: string
}

interface CitationGridProps {
  citations: Citation[]
}

export function CitationGrid({ citations }: CitationGridProps) {
  if (!citations || citations.length === 0) return null

  return (
    <div className="mt-3 w-full space-y-2.5 pt-3 border-t border-border/40">
      <div className="text-xs font-semibold text-muted-foreground/90 px-1 flex items-center gap-1.5 tracking-tight">
        <BookOpen className="h-3.5 w-3.5 text-primary" />
        <span>Sources Cited ({citations.length})</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {citations.map((cite, idx) => {
          const displayName = cite.source_name || cite.document_name || cite.document_id
          
          return (
            <div 
              key={`${cite.citation_index}-${idx}`} 
              id={`cite-${cite.citation_index}`} 
              className="group relative bg-surface dark:bg-slate-900/60 border border-border/80 dark:border-white/[0.08] rounded-xl p-3 shadow-sm hover:shadow-md hover:border-primary/40 dark:hover:border-primary/40 transition-all duration-200 text-xs space-y-1.5"
            >
              <div className="flex items-center gap-2 font-medium text-foreground">
                <span className="bg-primary/10 text-primary border border-primary/20 px-1.5 rounded inline-flex items-center justify-center h-4 text-[10px] font-bold font-mono shrink-0">
                  [{cite.citation_index}]
                </span>
                <FileText className="h-3.5 w-3.5 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                <span className="truncate text-[11px] font-semibold text-foreground/90 group-hover:text-foreground">{displayName}</span>
              </div>
              <p className="text-muted-foreground/80 dark:text-muted-foreground text-[11px] line-clamp-3 leading-relaxed pl-6 italic" title={cite.excerpt}>
                &quot;{cite.excerpt}&quot;
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
