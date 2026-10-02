import * as React from 'react'
import {
  Globe,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  X,
  FileText,
  Layers,
  Database,
  Lock,
} from 'lucide-react'
import { motion, AnimatePresence, useReducedMotion, type Variants } from 'framer-motion'
import {
  Button,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/common'
import { documentService } from '@/services/documentService'
import type { UrlIngestResponse } from '@/types'

export interface AddWebsiteDialogProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (resp: UrlIngestResponse, url: string) => void
}

const PIPELINE_STEPS = [
  {
    step: '1',
    name: 'Fetch',
    detail: 'SSRF & DNS',
    icon: Globe,
  },
  {
    step: '2',
    name: 'Extract',
    detail: 'DOM & Meta',
    icon: FileText,
  },
  {
    step: '3',
    name: 'Chunk',
    detail: 'Tokens',
    icon: Layers,
  },
  {
    step: '4',
    name: 'Index',
    detail: 'Qdrant Vectors',
    icon: Database,
  },
] as const

export function AddWebsiteDialog({ isOpen, onClose, onSuccess }: AddWebsiteDialogProps) {
  const [url, setUrl] = React.useState('')
  const [validationError, setValidationError] = React.useState<string | null>(null)
  const [apiError, setApiError] = React.useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = React.useState(false)
  const [isFocused, setIsFocused] = React.useState(false)

  const shouldReduceMotion = useReducedMotion()

  // Reset form when dialog opens/closes
  React.useEffect(() => {
    if (isOpen) {
      setUrl('')
      setValidationError(null)
      setApiError(null)
      setIsSubmitting(false)
      setIsFocused(false)
    }
  }, [isOpen])

  const validateUrl = (value: string): string | null => {
    const trimmed = value.trim()
    if (!trimmed) {
      return 'Please enter a website URL.'
    }
    if (!/^https?:\/\//i.test(trimmed)) {
      return 'URL must begin with http:// or https:// (e.g. https://example.com/docs).'
    }
    try {
      const parsed = new URL(trimmed)
      if (!parsed.hostname || !parsed.hostname.includes('.')) {
        return 'Please enter a valid domain name (e.g. example.com).'
      }
      if (['localhost', '127.0.0.1', '0.0.0.0', '::1'].includes(parsed.hostname.toLowerCase())) {
        return 'Localhost and private loopback addresses are blocked for security.'
      }
    } catch {
      return 'Enter a valid, well-formed URL.'
    }
    return null
  }

  const isValidUrl = React.useMemo(() => {
    if (!url.trim()) return false
    return validateUrl(url) === null
  }, [url])

  const handleUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setUrl(val)
    if (validationError) {
      setValidationError(validateUrl(val))
    }
    if (apiError) {
      setApiError(null)
    }
  }

  const handleBlur = () => {
    setIsFocused(false)
    if (url.trim()) {
      setValidationError(validateUrl(url))
    }
  }

  const handleClearUrl = () => {
    setUrl('')
    setValidationError(null)
    setApiError(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const error = validateUrl(url)
    if (error) {
      setValidationError(error)
      return
    }

    setValidationError(null)
    setApiError(null)
    setIsSubmitting(true)

    try {
      const resp = await documentService.ingestUrl(url.trim())
      onSuccess(resp, url.trim())
      onClose()
    } catch (err: unknown) {
      console.error('Failed to ingest website URL:', err)
      const message =
        err && typeof err === 'object' && 'message' in err
          ? String((err as { message?: string }).message)
          : 'Unable to connect to the specified website. Please ensure the URL is publicly reachable.'
      setApiError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Animation variants adhering to Veritas centralized motion system
  const contentVariants: Variants = {
    hidden: { opacity: 0, y: shouldReduceMotion ? 0 : 8 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.2,
        staggerChildren: shouldReduceMotion ? 0 : 0.05,
      },
    },
  }

  const itemVariants: Variants = {
    hidden: { opacity: 0, y: shouldReduceMotion ? 0 : 6 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.18 },
    },
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && !isSubmitting && onClose()}>
      <DialogContent className="max-w-lg overflow-hidden p-0 rounded-2xl border border-border/80 dark:border-white/[0.08] bg-surface-elevated/95 dark:bg-slate-900/95 backdrop-blur-xl shadow-2xl shadow-slate-950/20 dark:shadow-black/50">
        {/* Subtle Ambient Radial Highlight */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-primary/[0.07] via-primary/[0.02] to-transparent dark:from-primary/[0.12]"
        />

        {/* Modal Header */}
        <DialogHeader className="relative p-6 pb-5 border-b border-border/60 dark:border-white/[0.06] bg-muted/15 dark:bg-white/[0.02]">
          <div className="flex items-start gap-4">
            <div className="h-11 w-11 rounded-xl bg-primary/10 dark:bg-primary/20 border border-primary/25 flex items-center justify-center text-primary shrink-0 shadow-xs ring-1 ring-primary/10">
              <Globe className="h-5 w-5" />
            </div>
            <div className="space-y-1 pr-6">
              <DialogTitle className="text-base sm:text-lg font-semibold tracking-tight text-foreground">
                Add Website Knowledge Source
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground leading-relaxed">
                Ingest live documentation or public web content directly into your isolated knowledge registry.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* Modal Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5 max-h-[80vh] overflow-y-auto">
          <motion.div
            variants={contentVariants}
            initial="hidden"
            animate="visible"
            className="space-y-5"
          >
            {/* Connected Ingestion Pipeline Stepper */}
            <motion.div
              variants={itemVariants}
              className="rounded-xl bg-muted/30 dark:bg-slate-950/40 border border-border/70 dark:border-white/[0.06] p-3.5 space-y-3"
            >
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5 font-semibold text-foreground text-[11px] uppercase tracking-wider">
                  <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                  <span>Automated Pipeline</span>
                </div>
                <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-primary/10 text-primary border border-primary/20">
                  <Lock className="h-2.5 w-2.5" />
                  <span>SSRF Protected</span>
                </div>
              </div>

              {/* 4-Step Connected Stepper */}
              <div className="relative pt-1">
                {/* Horizontal Connector Line Behind Badges */}
                <div
                  aria-hidden="true"
                  className="absolute top-4 left-6 right-6 h-[2px] bg-border/80 dark:bg-slate-800 -z-0"
                >
                  {isSubmitting && (
                    <div className="h-full bg-primary animate-pulse" />
                  )}
                </div>

                <div className="grid grid-cols-4 gap-2 relative z-10">
                  {PIPELINE_STEPS.map((step) => {
                    const Icon = step.icon
                    return (
                      <div
                        key={step.step}
                        className={`group flex flex-col items-center text-center p-2 rounded-lg border transition-all duration-200 ${
                          isSubmitting
                            ? 'bg-primary/[0.04] border-primary/30 shadow-xs'
                            : 'bg-surface/90 dark:bg-slate-900/90 border-border/70 dark:border-slate-800'
                        }`}
                      >
                        <div
                          className={`h-7 w-7 rounded-lg flex items-center justify-center mb-1.5 transition-colors ${
                            isSubmitting
                              ? 'bg-primary text-primary-foreground shadow-xs'
                              : 'bg-muted/70 dark:bg-slate-800 text-muted-foreground group-hover:text-primary'
                          }`}
                        >
                          <Icon className="h-3.5 w-3.5" />
                        </div>
                        <span className="text-[11px] font-semibold text-foreground tracking-tight">
                          {step.step}. {step.name}
                        </span>
                        <span className="text-[10px] text-muted-foreground/80 mt-0.5 truncate max-w-full">
                          {step.detail}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </motion.div>

            {/* URL Input with Refined Focus Aura and Validation */}
            <motion.div variants={itemVariants} className="space-y-1.5">
              <label
                htmlFor="website-url-input"
                className="block text-xs font-semibold text-foreground tracking-tight"
              >
                Website URL <span className="text-danger">*</span>
              </label>

              <div
                className={`relative flex items-center rounded-xl border bg-background/60 transition-all duration-200 ${
                  validationError
                    ? 'border-danger/80 ring-2 ring-danger/15'
                    : isFocused
                    ? 'border-primary ring-4 ring-primary/10 shadow-xs'
                    : 'border-border/80 hover:border-border'
                }`}
              >
                {/* Leading Globe Icon */}
                <div
                  className={`pl-3.5 pr-2.5 transition-colors duration-200 ${
                    isFocused ? 'text-primary' : 'text-muted-foreground/70'
                  }`}
                >
                  <Globe className="h-4 w-4" />
                </div>

                {/* Input Field */}
                <input
                  id="website-url-input"
                  type="url"
                  autoFocus
                  disabled={isSubmitting}
                  placeholder="https://docs.example.com/api/v1"
                  value={url}
                  onChange={handleUrlChange}
                  onFocus={() => setIsFocused(true)}
                  onBlur={handleBlur}
                  aria-invalid={!!validationError}
                  aria-describedby={validationError ? 'url-validation-error' : 'url-helper-text'}
                  className="w-full py-2.5 pr-14 text-xs bg-transparent text-foreground placeholder:text-muted-foreground/50 focus:outline-none disabled:opacity-50"
                />

                {/* Trailing Indicators: Valid Check & Clear Button */}
                <div className="absolute right-3 flex items-center gap-1.5">
                  {isValidUrl && !isSubmitting && (
                    <CheckCircle2 className="h-4 w-4 text-success" />
                  )}
                  {url.length > 0 && !isSubmitting && (
                    <button
                      type="button"
                      onClick={handleClearUrl}
                      className="p-0.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/70 transition-colors"
                      aria-label="Clear URL input"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </div>

              {/* Dynamic Error or Explanatory Helper Text */}
              <AnimatePresence mode="wait">
                {validationError ? (
                  <motion.p
                    key="val-err"
                    id="url-validation-error"
                    role="alert"
                    initial={{ opacity: 0, height: 0, y: -4 }}
                    animate={{ opacity: 1, height: 'auto', y: 0 }}
                    exit={{ opacity: 0, height: 0, y: -4 }}
                    transition={{ duration: 0.15, ease: 'easeOut' }}
                    className="text-xs text-danger flex items-center gap-1.5 mt-1"
                  >
                    <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                    <span>{validationError}</span>
                  </motion.p>
                ) : (
                  <motion.p
                    key="val-helper"
                    id="url-helper-text"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="text-[11px] text-muted-foreground leading-normal"
                  >
                    Public HTTP/HTTPS endpoints only. Hostnames are DNS-resolved and evaluated against private subnets.
                  </motion.p>
                )}
              </AnimatePresence>
            </motion.div>

            {/* API Error Alert Banner */}
            <AnimatePresence>
              {apiError && (
                <motion.div
                  role="alert"
                  aria-live="polite"
                  initial={{ opacity: 0, height: 0, y: -6 }}
                  animate={{ opacity: 1, height: 'auto', y: 0 }}
                  exit={{ opacity: 0, height: 0, y: -6 }}
                  transition={{ duration: 0.2, ease: 'easeOut' }}
                  className="p-3.5 rounded-xl bg-danger/10 border border-danger/25 flex items-start gap-3 text-xs text-danger shadow-xs"
                >
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-danger" />
                  <div className="space-y-0.5">
                    <strong className="font-semibold block">Ingestion Request Failed</strong>
                    <span className="leading-relaxed opacity-95">{apiError}</span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Dialog Footer Actions */}
            <motion.div variants={itemVariants}>
              <DialogFooter className="pt-3 flex items-center justify-end gap-2.5 border-t border-border/50 dark:border-white/[0.06]">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={isSubmitting}
                  onClick={onClose}
                  className="text-xs hover:bg-muted/60 transition-colors"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="default"
                  size="sm"
                  isLoading={isSubmitting}
                  disabled={isSubmitting}
                  className="text-xs group flex items-center gap-1.5 shadow-sm hover:shadow hover:bg-primary-hover active:scale-[0.98] transition-all"
                >
                  <span>{isSubmitting ? 'Ingesting Website...' : 'Ingest Website'}</span>
                  {!isSubmitting && (
                    <ArrowRight className="h-3.5 w-3.5 transition-transform duration-150 group-hover:translate-x-0.5" />
                  )}
                </Button>
              </DialogFooter>
            </motion.div>
          </motion.div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
