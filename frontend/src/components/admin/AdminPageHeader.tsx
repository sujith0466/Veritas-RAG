import React from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { cn } from '@/utils/cn'

interface BreadcrumbItem {
  label: string
  href?: string
}

interface AdminPageHeaderProps {
  eyebrow?: string
  title: string
  description?: string
  breadcrumbs?: BreadcrumbItem[]
  badge?: React.ReactNode
  actions?: React.ReactNode
  className?: string
}

export function AdminPageHeader({
  eyebrow = 'ADMINISTRATION',
  title,
  description,
  breadcrumbs,
  badge,
  actions,
  className,
}: AdminPageHeaderProps) {
  const shouldReduceMotion = useReducedMotion()

  return (
    <motion.header
      initial={{ opacity: 0, y: shouldReduceMotion ? 0 : -6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className={cn(
        'relative mb-8 pb-6 border-b border-border/60 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between',
        className
      )}
    >
      <div className="space-y-1.5">
        {breadcrumbs && breadcrumbs.length > 0 ? (
          <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono mb-1">
            {breadcrumbs.map((b, i) => (
              <React.Fragment key={b.label}>
                {i > 0 && <span className="text-muted-foreground/40">/</span>}
                {b.href ? (
                  <a href={b.href} className="hover:text-foreground transition-colors">
                    {b.label}
                  </a>
                ) : (
                  <span className="text-foreground/80 font-medium">{b.label}</span>
                )}
              </React.Fragment>
            ))}
          </nav>
        ) : (
          eyebrow && (
            <div className="text-2xs font-mono font-semibold tracking-wider uppercase text-primary">
              {eyebrow}
            </div>
          )
        )}

        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground font-sans">
            {title}
          </h1>
          {badge && <div className="inline-flex items-center">{badge}</div>}
        </div>

        {description && (
          <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
            {description}
          </p>
        )}
      </div>

      {actions && (
        <div className="flex flex-wrap items-center gap-2.5 pt-1 sm:pt-0">
          {actions}
        </div>
      )}
    </motion.header>
  )
}
