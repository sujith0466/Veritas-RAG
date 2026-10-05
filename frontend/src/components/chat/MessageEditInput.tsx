import React, { useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { cn } from '@/utils/cn'

export interface MessageEditInputProps {
  initialContent: string
  onSave: (newContent: string) => Promise<void> | void
  onCancel: () => void
  disabled?: boolean
  className?: string
}

export const MessageEditInput: React.FC<MessageEditInputProps> = ({
  initialContent,
  onSave,
  onCancel,
  disabled = false,
  className,
}) => {
  const shouldReduceMotion = useReducedMotion()
  const [content, setContent] = useState(initialContent)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.focus()
      // Move cursor to end
      const len = textareaRef.current.value.length
      textareaRef.current.setSelectionRange(len, len)
      // Auto-resize
      adjustHeight()
    }
  }, [])

  const adjustHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 260)}px`
    }
  }

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setContent(e.target.value)
    adjustHeight()
  }

  const handleSubmit = async () => {
    const trimmed = content.trim()
    if (!trimmed || isSubmitting || disabled) return
    setIsSubmitting(true)
    try {
      await onSave(trimmed)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      e.stopPropagation()
      if (!isSubmitting) {
        onCancel()
      }
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      e.stopPropagation()
      handleSubmit()
    }
  }

  return (
    <motion.div
      initial={!shouldReduceMotion ? { opacity: 0, y: 3, scale: 0.99 } : false}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.15 }}
      className={cn(
        'flex flex-col gap-2.5 w-full rounded-xl border border-border/80 bg-surface/95 dark:bg-slate-900/90 p-3 shadow-md backdrop-blur-sm',
        className
      )}
    >
      <label htmlFor="message-edit-textarea" className="sr-only">
        Edit your message
      </label>
      <textarea
        id="message-edit-textarea"
        ref={textareaRef}
        value={content}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        disabled={isSubmitting || disabled}
        rows={1}
        className={cn(
          'w-full resize-none bg-transparent text-sm leading-relaxed text-foreground placeholder:text-muted-foreground',
          'focus:outline-none min-h-[44px] max-h-[260px] py-1 px-1.5'
        )}
        placeholder="Edit message..."
      />

      <div className="flex items-center justify-end gap-2 pt-1 border-t border-border/40">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onCancel}
          disabled={isSubmitting || disabled}
          className="text-xs h-7 px-2.5 text-muted-foreground hover:text-foreground"
        >
          Cancel
        </Button>
        <Button
          type="button"
          variant="default"
          size="sm"
          onClick={handleSubmit}
          disabled={!content.trim() || isSubmitting || disabled}
          className="text-xs h-7 px-3 gap-1.5 font-medium"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-3 w-3 animate-spin" />
              <span>Updating...</span>
            </>
          ) : (
            <span>Save & Submit</span>
          )}
        </Button>
      </div>
    </motion.div>
  )
}
