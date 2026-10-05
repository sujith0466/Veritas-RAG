import React, { useState } from 'react'
import { Check, Copy, Pencil } from 'lucide-react'
import { ActionButton, MessageActionBar } from './MessageActionBar'
import { copyToClipboard } from '@/utils/clipboard'
import { cn } from '@/utils/cn'

export interface UserMessageActionsProps {
  content: string
  onEdit: () => void
  isEditing?: boolean
  disabled?: boolean
  className?: string
}

export const UserMessageActions: React.FC<UserMessageActionsProps> = ({
  content,
  onEdit,
  isEditing = false,
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
      setAnnouncement('User message copied to clipboard')
      setTimeout(() => {
        setCopied(false)
        setAnnouncement('')
      }, 2000)
    }
  }

  return (
    <>
      <span className="sr-only" aria-live="polite">
        {announcement}
      </span>
      <MessageActionBar
        ariaLabel="User message actions"
        className={cn(
          'transition-opacity duration-150',
          className
        )}
      >
        <ActionButton
          icon={<Pencil className="h-3.5 w-3.5" />}
          tooltip="Edit message"
          ariaLabel="Edit message"
          onClick={(e) => {
            e.stopPropagation()
            onEdit()
          }}
          active={isEditing}
          disabled={disabled || isEditing}
        />
        <ActionButton
          icon={
            copied ? (
              <Check className="h-3.5 w-3.5 text-emerald-500 transition-transform duration-150 scale-110" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )
          }
          tooltip={copied ? 'Copied!' : 'Copy text'}
          ariaLabel={copied ? 'Copied to clipboard' : 'Copy user message to clipboard'}
          onClick={handleCopy}
          disabled={disabled}
        />
      </MessageActionBar>
    </>
  )
}
