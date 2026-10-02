import * as React from 'react'
import { Globe, AlertCircle, ArrowRight, ShieldCheck } from 'lucide-react'
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

export function AddWebsiteDialog({ isOpen, onClose, onSuccess }: AddWebsiteDialogProps) {
  const [url, setUrl] = React.useState('')
  const [validationError, setValidationError] = React.useState<string | null>(null)
  const [apiError, setApiError] = React.useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = React.useState(false)

  // Reset form when dialog opens/closes
  React.useEffect(() => {
    if (isOpen) {
      setUrl('')
      setValidationError(null)
      setApiError(null)
      setIsSubmitting(false)
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
    if (url.trim()) {
      setValidationError(validateUrl(url))
    }
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

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && !isSubmitting && onClose()}>
      <DialogContent className="max-w-lg overflow-hidden p-0 border-border/80 shadow-lg">
        <DialogHeader className="p-6 pb-4 border-b border-border/50 bg-muted/20">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0 ring-1 ring-primary/20">
              <Globe className="h-5 w-5" />
            </div>
            <div>
              <DialogTitle className="text-base font-semibold text-foreground">
                Add Website Knowledge Source
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                Ingest live documentation or web content directly into your searchable knowledge base.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Lifecycle pipeline preview banner */}
          <div className="rounded-lg bg-surface border border-border/70 p-3 text-xs text-muted-foreground space-y-2">
            <div className="flex items-center gap-1.5 font-medium text-foreground text-[11px] uppercase tracking-wider">
              <ShieldCheck className="h-3.5 w-3.5 text-primary" />
              Automated Ingestion Pipeline
            </div>
            <div className="grid grid-cols-4 gap-1 text-[11px] text-center">
              <div className="bg-muted/50 py-1 px-1.5 rounded border border-border/40 font-mono">
                1. Fetch
              </div>
              <div className="bg-muted/50 py-1 px-1.5 rounded border border-border/40 font-mono">
                2. Extract
              </div>
              <div className="bg-muted/50 py-1 px-1.5 rounded border border-border/40 font-mono">
                3. Chunk
              </div>
              <div className="bg-muted/50 py-1 px-1.5 rounded border border-border/40 font-mono">
                4. Index
              </div>
            </div>
          </div>

          {/* URL Input */}
          <div className="space-y-1.5">
            <label htmlFor="website-url-input" className="block text-xs font-semibold text-foreground">
              Website URL <span className="text-danger">*</span>
            </label>
            <div className="relative">
              <Globe className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/70" />
              <input
                id="website-url-input"
                type="url"
                autoFocus
                disabled={isSubmitting}
                placeholder="https://example.com/docs/overview"
                value={url}
                onChange={handleUrlChange}
                onBlur={handleBlur}
                className={`w-full pl-9 pr-3 py-2 text-xs rounded-lg border bg-background text-foreground placeholder:text-muted-foreground/60 transition-colors focus:outline-none focus:ring-2 ${
                  validationError
                    ? 'border-danger focus:ring-danger/20'
                    : 'border-border focus:border-primary focus:ring-primary/20'
                }`}
              />
            </div>
            {validationError ? (
              <p className="text-xs text-danger flex items-center gap-1 mt-1">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                {validationError}
              </p>
            ) : (
              <p className="text-[11px] text-muted-foreground">
                Public HTTP or HTTPS URL. Veritas validates against SSRF boundaries before fetching.
              </p>
            )}
          </div>

          {/* API Error Alert */}
          {apiError && (
            <div className="p-3 rounded-lg bg-danger/10 border border-danger/20 flex items-start gap-2.5 text-xs text-danger">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <div>
                <strong className="font-semibold block">Ingestion Failed</strong>
                <span>{apiError}</span>
              </div>
            </div>
          )}

          <DialogFooter className="pt-2 flex items-center justify-end gap-2 border-t border-border/40">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={isSubmitting}
              onClick={onClose}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="default"
              size="sm"
              isLoading={isSubmitting}
              disabled={isSubmitting}
              className="text-xs flex items-center gap-1.5 shadow-xs"
            >
              {!isSubmitting && <ArrowRight className="h-3.5 w-3.5" />}
              {isSubmitting ? 'Ingesting Website...' : 'Ingest Website'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
