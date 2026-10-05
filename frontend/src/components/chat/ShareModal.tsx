import React, { useState } from 'react'
import { Check, Copy, ExternalLink, FileText, Lock, Share2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/common/Dialog'
import { Button } from '@/components/common/Button'
import { copyToClipboard } from '@/utils/clipboard'
import type { ChatMessage } from '@/stores/chatStore'

export interface ShareModalProps {
  isOpen: boolean
  onClose: () => void
  message: ChatMessage | null
  sessionId: string | null
}

/**
 * Generates a clean, user-safe Markdown export of the assistant response.
 * Strictly avoids exposing internal IDs, tenant IDs, Qdrant vectors, or storage paths.
 */
export function formatSafeMarkdownExport(message: ChatMessage): string {
  let content = message.message || ''

  // Format safe user-visible citations
  if (message.citations && Array.isArray(message.citations) && message.citations.length > 0) {
    const citationLines: string[] = []
    message.citations.forEach((c: any) => {
      const idx = c.citation_index ?? ''
      const docName = c.document_name || c.title || 'Referenced Document'
      const page = c.page_number ? ` (Page ${c.page_number})` : ''
      const section = c.section_title ? ` [${c.section_title}]` : ''
      citationLines.push(`- [${idx}] ${docName}${page}${section}`)
    })

    if (citationLines.length > 0) {
      content += '\n\n---\n### Sources & Citations\n' + citationLines.join('\n')
    }
  }

  // Format safe reliability indicator if user-visible
  if (message.reliability_score !== undefined && message.reliability_score !== null) {
    const pct = Math.round(message.reliability_score * 100)
    const label =
      message.reliability_score >= 0.8
        ? 'Highly Grounded'
        : message.reliability_score >= 0.5
          ? 'Partially Grounded'
          : 'Low Grounding'
    content += `\n\n### Verification\n- Reliability Score: ${pct}% (${label})`
  }

  return content.trim()
}

export const ShareModal: React.FC<ShareModalProps> = ({
  isOpen,
  onClose,
  message,
  sessionId,
}) => {
  const [copiedMarkdown, setCopiedMarkdown] = useState(false)
  const [copiedLink, setCopiedLink] = useState(false)
  const [sharedNative, setSharedNative] = useState(false)

  if (!message) return null

  const deepLink =
    typeof window !== 'undefined' && sessionId
      ? `${window.location.origin}/chat/${sessionId}?messageId=${message.id}`
      : ''

  const safeMarkdown = formatSafeMarkdownExport(message)

  const handleCopyMarkdown = async () => {
    const success = await copyToClipboard(safeMarkdown)
    if (success) {
      setCopiedMarkdown(true)
      setTimeout(() => setCopiedMarkdown(false), 2000)
    }
  }

  const handleCopyLink = async () => {
    if (!deepLink) return
    const success = await copyToClipboard(deepLink)
    if (success) {
      setCopiedLink(true)
      setTimeout(() => setCopiedLink(false), 2000)
    }
  }

  const canNativeShare =
    typeof navigator !== 'undefined' &&
    typeof navigator.share === 'function'

  const handleNativeShare = async () => {
    if (!canNativeShare) return
    try {
      await navigator.share({
        title: 'Veritas-RAG - Chat Response',
        text: safeMarkdown,
      })
      setSharedNative(true)
      setTimeout(() => setSharedNative(false), 2000)
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error('Native share failed', err)
      }
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md gap-5">
        <DialogHeader>
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary border border-primary/20">
              <Share2 className="h-4.5 w-4.5" />
            </div>
            <div>
              <DialogTitle className="text-base font-semibold">Share Response</DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground">
                Export sanitized response or copy authenticated deep-link.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          {/* Option 1: Safe Markdown Export */}
          <div className="flex items-center justify-between p-3 rounded-lg border border-border/70 bg-surface hover:bg-muted/40 transition-colors">
            <div className="flex items-center gap-2.5">
              <FileText className="h-4 w-4 text-primary shrink-0" />
              <div>
                <span className="text-xs font-medium text-foreground block">Formatted Markdown</span>
                <span className="text-[11px] text-muted-foreground block">Clean response with cited document names</span>
              </div>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleCopyMarkdown}
              className="text-xs h-7.5 px-2.5 gap-1.5 shrink-0"
            >
              {copiedMarkdown ? (
                <>
                  <Check className="h-3.5 w-3.5 text-emerald-500" />
                  <span className="text-emerald-500 font-medium">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  <span>Copy</span>
                </>
              )}
            </Button>
          </div>

          {/* Option 2: Native Device Share (if supported) */}
          {canNativeShare && (
            <div className="flex items-center justify-between p-3 rounded-lg border border-border/70 bg-surface hover:bg-muted/40 transition-colors">
              <div className="flex items-center gap-2.5">
                <Share2 className="h-4 w-4 text-primary shrink-0" />
                <div>
                  <span className="text-xs font-medium text-foreground block">Device Share Sheet</span>
                  <span className="text-[11px] text-muted-foreground block">Send to email, Slack, or other apps</span>
                </div>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleNativeShare}
                className="text-xs h-7.5 px-2.5 gap-1.5 shrink-0"
              >
                {sharedNative ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-emerald-500" />
                    <span className="text-emerald-500 font-medium">Shared</span>
                  </>
                ) : (
                  <>
                    <ExternalLink className="h-3.5 w-3.5" />
                    <span>Share</span>
                  </>
                )}
              </Button>
            </div>
          )}

          {/* Option 3: Authenticated Deep Link */}
          {deepLink && (
            <div className="flex flex-col gap-2 p-3 rounded-lg border border-border/70 bg-surface">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Lock className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                  <span className="text-xs font-medium text-foreground">Private Deep Link</span>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleCopyLink}
                  className="text-xs h-7 px-2.5 gap-1.5"
                >
                  {copiedLink ? (
                    <>
                      <Check className="h-3.5 w-3.5 text-emerald-500" />
                      <span className="text-emerald-500 font-medium">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" />
                      <span>Copy Link</span>
                    </>
                  )}
                </Button>
              </div>
              <p className="text-[11px] text-muted-foreground leading-normal">
                This link is private and accessible only by you in this workspace. To share findings with colleagues, use <span className="font-semibold text-foreground">Formatted Markdown</span>.
              </p>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
