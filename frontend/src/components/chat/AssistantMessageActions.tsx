import React, { useState } from 'react'
import { Check, Copy, Share2, ThumbsDown, ThumbsUp } from 'lucide-react'
import { ActionButton, MessageActionBar } from './MessageActionBar'
import { copyToClipboard } from '@/utils/clipboard'
import { cn } from '@/utils/cn'

export interface AssistantMessageActionsProps {
  content: string
  feedback?: 'like' | 'dislike' | null
  onFeedback?: (rating: 'like' | 'dislike' | null) => void
  onShare?: () => void
  disabled?: boolean
  className?: string
}

export const AssistantMessageActions: React.FC<AssistantMessageActionsProps> = ({
  content,
  feedback = null,
  onFeedback,
  onShare,
  disabled = false,
  className,
}) => {
  const [copied, setCopied] = useState(false)
  const [announcement, setAnnouncement] = useState('')

  const handleCopy = async (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation()
    const success = await copyToClipboard(content)
    if (success) {
      setCopied(true)
      setAnnouncement('Response copied to clipboard')
      setTimeout(() => {
        setCopied(false)
        setAnnouncement('')
      }, 2000)
    }
  }

  const handleLike = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation()
    if (!onFeedback || disabled) return
    const next = feedback === 'like' ? null : 'like'
    onFeedback(next)
    setAnnouncement(next ? 'Marked response as helpful' : 'Cleared response feedback')
  }

  const handleDislike = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation()
    if (!onFeedback || disabled) return
    const next = feedback === 'dislike' ? null : 'dislike'
    onFeedback(next)
    setAnnouncement(next ? 'Marked response as unhelpful' : 'Cleared response feedback')
  }

  const handleShare = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation()
    if (!onShare || disabled) return
    onShare()
  }

  return (
    <>
      <span className="sr-only" aria-live="polite">
        {announcement}
      </span>
      <MessageActionBar
        ariaLabel="Assistant message actions"
        className={cn('transition-opacity duration-150', className)}
      >
        <ActionButton
          icon={
            copied ? (
              <Check className="h-3.5 w-3.5 text-emerald-500 transition-transform duration-150 scale-110" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )
          }
          tooltip={copied ? 'Copied!' : 'Copy response'}
          ariaLabel={copied ? 'Copied response to clipboard' : 'Copy response to clipboard'}
          onClick={handleCopy}
          disabled={disabled}
        />
        <ActionButton
          icon={<ThumbsUp className="h-3.5 w-3.5" />}
          tooltip={feedback === 'like' ? 'Remove helpful rating' : 'Helpful response'}
          ariaLabel={feedback === 'like' ? 'Remove like rating' : 'Like response'}
          onClick={handleLike}
          active={feedback === 'like'}
          activeClassName="text-emerald-500 bg-emerald-500/10 border-emerald-500/30 hover:bg-emerald-500/20"
          disabled={disabled}
        />
        <ActionButton
          icon={<ThumbsDown className="h-3.5 w-3.5" />}
          tooltip={feedback === 'dislike' ? 'Remove unhelpful rating' : 'Unhelpful response'}
          ariaLabel={feedback === 'dislike' ? 'Remove dislike rating' : 'Dislike response'}
          onClick={handleDislike}
          active={feedback === 'dislike'}
          activeClassName="text-rose-500 bg-rose-500/10 border-rose-500/30 hover:bg-rose-500/20"
          disabled={disabled}
        />
        {onShare && (
          <ActionButton
            icon={<Share2 className="h-3.5 w-3.5" />}
            tooltip="Share response"
            ariaLabel="Share response"
            onClick={handleShare}
            disabled={disabled}
          />
        )}
      </MessageActionBar>
    </>
  )
}
