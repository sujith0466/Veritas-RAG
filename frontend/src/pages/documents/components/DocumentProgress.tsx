import { motion } from 'framer-motion'
import {
  CheckCircle2,
  Clock,
  AlertTriangle,
  Loader2,
  FileText,
  ShieldAlert,
  RotateCcw,
} from 'lucide-react'
import { Card, Badge } from '@/components/common'
import { cn } from '@/utils/cn'
import type { ProcessingStatusResponse } from '@/types'

export interface DocumentProgressProps {
  status: ProcessingStatusResponse | null
  documentName?: string
  isPolling: boolean
}

const STAGES = [
  { key: 'upload', label: 'File Uploaded', desc: 'SHA-256 check & physical volume storage' },
  { key: 'validation', label: 'Validation Pipeline', desc: 'Magic bytes, MIME check & virus scan' },
  { key: 'extraction', label: 'Content Extraction', desc: 'Capability registry routing & parsing' },
  { key: 'ocr', label: 'OCR Screening', desc: 'Density check & engine fallback' },
  { key: 'manifest', label: 'Canonical Manifest', desc: 'NFC normalization & contract check' },
]

export function DocumentProgress({ status, documentName, isPolling }: DocumentProgressProps) {
  if (!status) return null

  const getStageState = (_stageKey: string, index: number) => {
    if (status.status === 'PROCESSED') return 'completed'
    if (status.status === 'FAILED') {
      const currentIdx = STAGES.findIndex((s) => s.key === status.current_step)
      if (index < currentIdx) return 'completed'
      if (index === currentIdx) return 'failed'
      return 'pending'
    }

    const currentIdx = STAGES.findIndex((s) => s.key === status.current_step)
    if (index < currentIdx) return 'completed'
    if (index === currentIdx) return 'active'
    return 'pending'
  }

  const getStatusBadge = () => {
    switch (status.status) {
      case 'PROCESSED':
        return <Badge variant="success">PROCESSED (CONTRACT VERIFIED)</Badge>
      case 'FAILED':
        return <Badge variant="destructive">FAILED (SEVERITY CHECKED)</Badge>
      case 'VALIDATING':
      case 'EXTRACTING':
      case 'RETRYING':
        return (
          <Badge variant="warning" className="animate-pulse">
            {status.status} (RETRY {status.retry_count}/3)
          </Badge>
        )
      default:
        return <Badge variant="subtle">{status.status}</Badge>
    }
  }

  return (
    <Card className="p-6 bg-surface-elevated/80 backdrop-blur-md border-primary/20 relative overflow-hidden shadow-lg">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border/50">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="font-semibold text-foreground text-sm sm:text-base">
                Pipeline Lifecycle: {documentName || status.document_id.slice(0, 8)}
              </h4>
              {getStatusBadge()}
            </div>
            <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-2">
              <span>Current Step: <strong className="text-foreground uppercase">{status.current_step}</strong></span>
              {isPolling && (
                <span className="inline-flex items-center gap-1 text-primary">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Real-time worker polling (2s)
                </span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-right">
          <div className="text-xs font-medium text-muted-foreground">
            Progress: <span className="text-foreground font-bold">{status.progress_percent}%</span>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-muted rounded-full h-2 my-6 overflow-hidden">
        <motion.div
          className={cn(
            'h-full rounded-full transition-all duration-300',
            status.status === 'PROCESSED' ? 'bg-success' : status.status === 'FAILED' ? 'bg-danger' : 'bg-gradient-primary',
          )}
          initial={{ width: 0 }}
          animate={{ width: `${status.progress_percent}%` }}
        />
      </div>

      {/* Stages Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
        {STAGES.map((stage, i) => {
          const state = getStageState(stage.key, i)
          return (
            <div
              key={stage.key}
              className={cn(
                'p-3 rounded-lg border transition-all flex flex-col justify-between gap-2',
                state === 'completed' && 'bg-success/5 border-success/30 text-foreground',
                state === 'active' && 'bg-primary/10 border-primary shadow-sm ring-1 ring-primary/30',
                state === 'failed' && 'bg-danger/10 border-danger/40 text-danger',
                state === 'pending' && 'bg-muted/30 border-border/40 opacity-50',
              )}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider">{stage.label}</span>
                {state === 'completed' && <CheckCircle2 className="h-4 w-4 text-success shrink-0" />}
                {state === 'active' && <Loader2 className="h-4 w-4 text-primary animate-spin shrink-0" />}
                {state === 'failed' && <ShieldAlert className="h-4 w-4 text-danger shrink-0" />}
                {state === 'pending' && <Clock className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
              </div>
              <p className="text-[11px] text-muted-foreground leading-tight">{stage.desc}</p>
            </div>
          )
        })}
      </div>

      {/* Error / Retry Banner */}
      {status.status === 'FAILED' && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-6 p-4 rounded-lg bg-danger/10 border border-danger/30 flex items-start gap-3"
        >
          <AlertTriangle className="h-5 w-5 text-danger shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h5 className="font-semibold text-sm text-danger flex items-center gap-2">
              Ingestion Pipeline Failure [{status.error_code || 'SYS_002'}]
              {status.retry_count > 0 && (
                <Badge variant="destructive" className="text-[10px] h-4">
                  <RotateCcw className="h-3 w-3 mr-1" /> Retried {status.retry_count}/3 times
                </Badge>
              )}
            </h5>
            <p className="text-xs text-muted-foreground">
              {status.error_message || 'An unrecoverable error occurred during background processing.'}
            </p>
          </div>
        </motion.div>
      )}
    </Card>
  )
}
