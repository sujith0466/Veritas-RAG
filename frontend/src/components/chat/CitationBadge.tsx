import React from 'react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/common/Tooltip'
import { FileText } from 'lucide-react'

interface CitationBadgeProps {
  citation: {
    citation_index: number
    document_id: string
    source_name?: string
    document_name?: string
    excerpt: string
  }
}

export function CitationBadge({ citation }: CitationBadgeProps) {
  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    document.getElementById(`cite-${citation.citation_index}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    
    // Highlight effect
    const el = document.getElementById(`cite-${citation.citation_index}`)
    if (el) {
      el.classList.add('ring-2', 'ring-primary', 'border-primary')
      setTimeout(() => {
        el.classList.remove('ring-2', 'ring-primary', 'border-primary')
      }, 2000)
    }
  }

  const displayName = citation.source_name || citation.document_name || citation.document_id

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={handleClick}
            aria-label={`Citation [${citation.citation_index}]: ${displayName}`}
            className="inline-flex items-center justify-center font-mono text-[10px] font-semibold px-1.5 py-0.5 mx-0.5 rounded bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 hover:border-primary/40 transition-all duration-150 align-baseline cursor-pointer focus:outline-none focus-visible:ring-1 focus-visible:ring-primary"
          >
            [{citation.citation_index}]
          </button>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs text-xs space-y-1.5 z-50 p-3 bg-surface/95 dark:bg-slate-900/95 backdrop-blur-md border border-border/80 shadow-lg rounded-xl">
          <div className="flex items-center gap-1.5 font-semibold text-foreground truncate pb-1.5 border-b border-border/50 text-[11px]">
            <FileText className="h-3 w-3 text-primary shrink-0" />
            <span className="truncate">{displayName}</span>
          </div>
          <div className="text-muted-foreground line-clamp-3 leading-relaxed text-[11px] italic">
            &quot;{citation.excerpt}&quot;
          </div>
          <div className="text-[10px] text-primary/80 font-medium pt-0.5">
            Click to view source card
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
