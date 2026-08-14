import React from 'react'
import { Badge } from '@/components/common/Badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/common/Tooltip'

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
      el.classList.add('ring-2', 'ring-primary')
      setTimeout(() => el.classList.remove('ring-2', 'ring-primary'), 2000)
    }
  }

  const displayName = citation.source_name || citation.document_name || citation.document_id

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge 
            variant="secondary" 
            className="cursor-pointer text-[10px] px-1 py-0 hover:bg-primary/20 transition-colors mx-0.5 inline-flex items-center justify-center" 
            onClick={handleClick}
          >
            [{citation.citation_index}]
          </Badge>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs text-xs space-y-1 z-50 p-2.5">
          <div className="font-semibold text-foreground truncate pb-1 border-b border-border/50">{displayName}</div>
          <div className="text-muted-foreground line-clamp-3 pt-1">&quot;{citation.excerpt}&quot;</div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
