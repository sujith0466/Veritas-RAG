import { useState, useEffect } from 'react'
import {
  AlertTriangle,
  Trash2,
  CheckCircle2,
  X,
  RefreshCw,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { Button } from '@/components/common/Button'
import { Badge } from '@/components/common/Badge'
import { documentService } from '@/services/documentService'
import { useKnowledgeHealthStore } from '@/stores/knowledgeHealthStore'
import type { DocumentDetailResponse } from '@/types'

interface DestructivePurgeModalProps {
  isOpen: boolean
  onClose: () => void
  documentId: string
  onPurgeSuccess?: (summary: {
    document_id: string
    qdrant_points_deleted: number
    pg_chunks_deleted: number
    duration_ms: number
  }) => void
}

export function DestructivePurgeModal({
  isOpen,
  onClose,
  documentId,
  onPurgeSuccess,
}: DestructivePurgeModalProps) {
  const { purgeDocument, fetchParity } = useKnowledgeHealthStore()

  const [isPreflighting, setIsPreflighting] = useState(false)
  const [docDetail, setDocDetail] = useState<DocumentDetailResponse | null>(null)
  const [preflightError, setPreflightError] = useState<string | null>(null)

  const [confirmInput, setConfirmInput] = useState('')
  const [isPurging, setIsPurging] = useState(false)
  const [purgeError, setPurgeError] = useState<string | null>(null)
  const [successSummary, setSuccessSummary] = useState<{
    document_id: string
    qdrant_points_deleted: number
    pg_chunks_deleted: number
    duration_ms: number
  } | null>(null)

  useEffect(() => {
    if (isOpen && documentId.trim()) {
      setIsPreflighting(true)
      setPreflightError(null)
      setDocDetail(null)
      setConfirmInput('')
      setPurgeError(null)
      setSuccessSummary(null)

      documentService
        .getDocumentDetail(documentId.trim())
        .then((detail) => {
          setDocDetail(detail)
        })
        .catch((err) => {
          console.warn('Preflight check document lookup error:', err)
          setPreflightError(
            err instanceof Error
              ? err.message
              : 'Could not resolve document metadata from workspace DB. Proceed with caution if purging orphaned vectors.',
          )
        })
        .finally(() => {
          setIsPreflighting(false)
        })
    }
  }, [isOpen, documentId])

  const handleExecutePurge = async () => {
    if (confirmInput.trim() !== 'PURGE') return
    setIsPurging(true)
    setPurgeError(null)
    try {
      const res = await purgeDocument(documentId.trim())
      if (res) {
        const summary = {
          document_id: res.document_id,
          qdrant_points_deleted: res.qdrant_points_deleted ?? res.purged_points_count ?? 0,
          pg_chunks_deleted: res.pg_chunks_deleted ?? 0,
          duration_ms: res.duration_ms ?? 0,
        }
        setSuccessSummary(summary)
        onPurgeSuccess?.(summary)
        fetchParity()
      }
    } catch (err) {
      setPurgeError(err instanceof Error ? err.message : 'Failed to execute two-phase purge')
    } finally {
      setIsPurging(false)
    }
  }

  if (!isOpen) return null

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 overflow-y-auto bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
        {/* Backdrop click to dismiss if not purging */}
        <div className="fixed inset-0" onClick={isPurging ? undefined : onClose} />

        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.2 }}
          className="relative z-10 w-full max-w-lg rounded-2xl border border-destructive/40 bg-surface shadow-2xl p-6 space-y-5"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-start justify-between pb-3 border-b border-border/60">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-destructive/10 text-destructive border border-destructive/20">
                <Trash2 className="h-6 w-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-foreground">
                  Preflight Destruction Guard
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Two-phase atomic vector purge & DB cascade
                </p>
              </div>
            </div>
            {!isPurging && (
              <button
                onClick={onClose}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            )}
          </div>

          {/* Body */}
          {successSummary ? (
            <div className="space-y-4 py-2">
              <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-500 flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="text-sm font-bold">Purge Executed Successfully</div>
                  <p className="text-xs opacity-90 leading-relaxed">
                    Vectors for document{' '}
                    <span className="font-mono font-semibold">
                      {successSummary.document_id.slice(0, 8)}...
                    </span>{' '}
                    have been permanently purged across Qdrant cluster points and PostgreSQL chunks.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="p-2.5 rounded-lg bg-surface border border-border/50">
                  <div className="text-muted-foreground">Qdrant Points</div>
                  <div className="font-bold text-foreground mt-1">
                    {successSummary.qdrant_points_deleted} purged
                  </div>
                </div>
                <div className="p-2.5 rounded-lg bg-surface border border-border/50">
                  <div className="text-muted-foreground">DB Chunks</div>
                  <div className="font-bold text-foreground mt-1">
                    {successSummary.pg_chunks_deleted} removed
                  </div>
                </div>
                <div className="p-2.5 rounded-lg bg-surface border border-border/50">
                  <div className="text-muted-foreground">Duration</div>
                  <div className="font-bold font-mono text-foreground mt-1">
                    {successSummary.duration_ms.toFixed(1)} ms
                  </div>
                </div>
              </div>

              <Button onClick={onClose} className="w-full text-xs font-semibold">
                Close
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Preflight Target Card */}
              <div className="p-4 rounded-xl bg-surface/80 border border-border/60 space-y-2.5">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-muted-foreground font-semibold uppercase tracking-wider">
                    Target Document Preflight
                  </span>
                  {isPreflighting ? (
                    <span className="flex items-center gap-1.5 text-muted-foreground">
                      <RefreshCw className="h-3 w-3 animate-spin text-primary" /> Inspecting DB...
                    </span>
                  ) : docDetail ? (
                    <Badge variant="success" className="text-[10px]">
                      Verified in DB
                    </Badge>
                  ) : (
                    <Badge variant="warning" className="text-[10px]">
                      Unverified / Orphan
                    </Badge>
                  )}
                </div>

                <div className="text-xs font-mono bg-muted/40 p-2 rounded border border-border/40 text-foreground break-all">
                  {documentId}
                </div>

                {docDetail && (
                  <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border/40 text-xs">
                    <div>
                      <span className="text-muted-foreground">Document: </span>
                      <span className="font-semibold text-foreground truncate block">
                        {docDetail.original_filename || docDetail.filename || 'Untitled'}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Status: </span>
                      <span className="font-semibold text-foreground">
                        {docDetail.status || 'UNKNOWN'}
                      </span>
                    </div>
                  </div>
                )}

                {preflightError && (
                  <div className="text-[11px] text-amber-500 bg-amber-500/10 p-2 rounded border border-amber-500/20">
                    {preflightError}
                  </div>
                )}
              </div>

              {/* Danger Warning Banner */}
              <div className="p-3.5 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
                <div className="text-xs space-y-1">
                  <span className="font-bold">Irreversible Vector Purge</span>
                  <p className="opacity-90 leading-relaxed">
                    This operation will immediately delete all Qdrant vector points associated with this
                    document and mark it unindexed. Search queries will no longer match chunks from this document.
                  </p>
                </div>
              </div>

              {/* Typed Confirmation Field */}
              <div className="space-y-2">
                <label className="text-xs font-medium text-foreground">
                  Type <span className="font-mono font-bold text-destructive">PURGE</span> to confirm execution:
                </label>
                <input
                  type="text"
                  value={confirmInput}
                  onChange={(e) => setConfirmInput(e.target.value)}
                  placeholder="PURGE"
                  disabled={isPurging}
                  className="w-full h-9 rounded-lg border border-border/60 bg-surface px-3 text-xs font-mono uppercase tracking-wider text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-destructive"
                />
              </div>

              {purgeError && (
                <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-xs">
                  {purgeError}
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center gap-3 pt-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onClose}
                  disabled={isPurging}
                  className="flex-1 text-xs"
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleExecutePurge}
                  disabled={confirmInput.trim() !== 'PURGE' || isPurging}
                  className="flex-1 text-xs font-bold flex items-center justify-center gap-2"
                >
                  {isPurging ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Purging Vectors...
                    </>
                  ) : (
                    <>
                      <Trash2 className="h-3.5 w-3.5" /> Execute Purge
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </AnimatePresence>
  )
}
