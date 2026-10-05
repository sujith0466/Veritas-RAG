import React from 'react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/common/Tooltip'
import { cn } from '@/utils/cn'

export interface ActionButtonProps {
  icon: React.ReactNode
  tooltip: string
  ariaLabel: string
  onClick: (e: React.MouseEvent<HTMLButtonElement>) => void
  active?: boolean
  disabled?: boolean
  className?: string
  activeClassName?: string
}

export const ActionButton: React.FC<ActionButtonProps> = ({
  icon,
  tooltip,
  ariaLabel,
  onClick,
  active = false,
  disabled = false,
  className,
  activeClassName = 'text-primary bg-primary/10 border-primary/20',
}) => {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onClick}
          disabled={disabled}
          aria-label={ariaLabel}
          aria-pressed={active}
          className={cn(
            'inline-flex items-center justify-center rounded-md p-1.5 transition-colors duration-150',
            'text-muted-foreground hover:text-foreground hover:bg-muted/60',
            'focus-visible:outline-none focus-visible:ring-1.5 focus-visible:ring-primary focus-visible:ring-offset-1 focus-visible:ring-offset-background',
            'disabled:pointer-events-none disabled:opacity-40',
            active && activeClassName,
            className
          )}
        >
          {icon}
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" sideOffset={4}>
        <span>{tooltip}</span>
      </TooltipContent>
    </Tooltip>
  )
}

export interface MessageActionBarProps {
  children: React.ReactNode
  className?: string
  ariaLabel?: string
}

export const MessageActionBar: React.FC<MessageActionBarProps> = ({
  children,
  className,
  ariaLabel = 'Message actions',
}) => {
  return (
    <TooltipProvider delayDuration={200}>
      <div
        role="toolbar"
        aria-label={ariaLabel}
        className={cn(
          'flex items-center gap-0.5 rounded-lg border border-border/40 bg-surface/80 p-0.5 backdrop-blur-sm shadow-xs',
          className
        )}
      >
        {children}
      </div>
    </TooltipProvider>
  )
}
