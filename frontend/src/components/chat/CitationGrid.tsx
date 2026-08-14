

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
    <div className="mt-2 w-full space-y-2 pt-2 border-t border-border/30">
      <div className="text-xs font-semibold text-muted-foreground px-1 flex items-center gap-1.5">
        Sources Cited ({citations.length}):
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {citations.map((cite, idx) => {
          const displayName = cite.source_name || cite.document_name || cite.document_id
          
          return (
            <div 
              key={`${cite.citation_index}-${idx}`} 
              id={`cite-${cite.citation_index}`} 
              className="bg-surface border border-border/60 rounded-lg p-2.5 shadow-sm text-xs space-y-1.5 hover:border-primary/40 transition-all duration-300"
            >
              <div className="flex items-center gap-1.5 font-medium text-foreground">
                <span className="bg-primary/10 text-primary px-1.5 rounded inline-flex items-center justify-center h-4 text-[10px] font-bold">
                  [{cite.citation_index}]
                </span>
                <span className="truncate text-[11px]">{displayName}</span>
              </div>
              <p className="text-muted-foreground line-clamp-3 leading-relaxed" title={cite.excerpt}>
                &quot;{cite.excerpt}&quot;
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
