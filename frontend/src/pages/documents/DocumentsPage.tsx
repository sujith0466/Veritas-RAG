import * as React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  RefreshCw,
  Filter,
} from 'lucide-react'
import { PageTransition } from '@/components/layouts'
import { Button, PageHeader } from '@/components/common'
import { documentService } from '@/services/documentService'
import type { DocumentResponse, ProcessingStatusResponse } from '@/types'
import {
  UploadDropzone,
  DocumentProgress,
  DocumentList,
  DocumentDetailDrawer,
  ZipPreviewDialog,
} from './components'

export function DocumentsPage() {
  const [documents, setDocuments] = React.useState<DocumentResponse[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [statusFilter, setStatusFilter] = React.useState<string>('ALL')

  // Active upload & polling state
  const [isUploading, setIsUploading] = React.useState(false)
  const [uploadProgress, setUploadProgress] = React.useState(0)
  const [activeStatus, setActiveStatus] = React.useState<ProcessingStatusResponse | null>(null)
  const [activeDocName, setActiveDocName] = React.useState<string>('')
  const [isPolling, setIsPolling] = React.useState(false)
  const [selectedZipFile, setSelectedZipFile] = React.useState<File | null>(null)

  // Detail drawer state
  const [selectedDocId, setSelectedDocId] = React.useState<string | null>(null)

  const fetchDocuments = React.useCallback(async () => {
    try {
      const resp = await documentService.listDocuments(1, 50, statusFilter)
      setDocuments(resp.items || [])
    } catch (err) {
      console.error('Failed to fetch documents:', err)
    } finally {
      setIsLoading(false)
    }
  }, [statusFilter])

  React.useEffect(() => {
    setIsLoading(true)
    fetchDocuments()
  }, [fetchDocuments])

  // Polling effect for active document job
  React.useEffect(() => {
    if (!activeStatus || !isPolling) return

    const interval = setInterval(async () => {
      try {
        const latest = await documentService.getDocumentStatus(activeStatus.document_id)
        setActiveStatus(latest)

        if (latest.status === 'PROCESSED' || latest.status === 'FAILED') {
          setIsPolling(false)
          fetchDocuments() // Refresh registry table
        }
      } catch (err) {
        console.error('Polling error:', err)
        setIsPolling(false)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [activeStatus, isPolling, fetchDocuments])

  const handleUpload = async (file: File, onProgress: (percent: number) => void) => {
    setIsUploading(true)
    setUploadProgress(0)
    try {
      const resp = await documentService.uploadDocument(file, (percent) => {
        setUploadProgress(percent)
        onProgress(percent)
      })

      setActiveDocName(file.name)
      setActiveStatus({
        document_id: resp.document_id,
        status: resp.status,
        current_step: 'validation',
        progress_percent: 20,
        retry_count: 0,
        updated_at: resp.created_at,
      })
      setIsPolling(true)
      fetchDocuments()
    } finally {
      setIsUploading(false)
    }
  }

  const handleZipConfirm = async (files: Array<{file: File, path: string}>) => {
    setSelectedZipFile(null)
    setIsUploading(true)
    setUploadProgress(0)
    let completed = 0

    for (const item of files) {
      try {
        await documentService.uploadDocument(item.file, undefined, item.path)
      } catch (err) {
        console.error(`Failed to upload ${item.path}:`, err)
      } finally {
        completed++
        setUploadProgress(Math.round((completed / files.length) * 100))
        if (completed % 5 === 0) fetchDocuments() // Refresh periodically
      }
    }

    fetchDocuments()
    setIsUploading(false)
  }

  const handleDelete = async (docId: string) => {
    try {
      await documentService.deleteDocument(docId)
      if (activeStatus?.document_id === docId) {
        setActiveStatus(null)
        setIsPolling(false)
      }
      await fetchDocuments()
    } catch (err) {
      console.error('Failed to delete document:', err)
    }
  }

  const handleArchive = async (docId: string) => {
    try {
      await documentService.archiveDocument(docId)
      await fetchDocuments()
    } catch (err) {
      console.error('Failed to archive document:', err)
    }
  }

  const handleRestore = async (docId: string) => {
    try {
      await documentService.restoreDocument(docId)
      await fetchDocuments()
    } catch (err) {
      console.error('Failed to restore document:', err)
    }
  }

  const filterOptions = [
    { label: 'All Documents', value: 'ALL' },
    { label: 'Processed', value: 'PROCESSED' },
    { label: 'Validating', value: 'VALIDATING' },
    { label: 'Extracting', value: 'EXTRACTING' },
    { label: 'Archived', value: 'ARCHIVED' },
    { label: 'Failed', value: 'FAILED' },
  ]

  return (
    <PageTransition className="space-y-8 pb-12">
      <PageHeader
        title="Document Intelligence Foundation"
        description="Enterprise-grade document ingestion, capability registry extraction, OCR density fallback, and canonical manifest generation. No vector retrieval or AI calls."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => fetchDocuments()}
            isLoading={isLoading}
            className="flex items-center gap-1.5"
          >
            {!isLoading && <RefreshCw className="h-3.5 w-3.5" />}
            Refresh Registry
          </Button>
        }
      />

      {/* Upload Dropzone */}
      <UploadDropzone
        onUpload={handleUpload}
        onZipSelect={(file) => setSelectedZipFile(file)}
        isUploading={isUploading}
        uploadProgress={uploadProgress}
      />

      {/* ZIP Preview Dialog */}
      {selectedZipFile && (
        <ZipPreviewDialog
          zipFile={selectedZipFile}
          onClose={() => setSelectedZipFile(null)}
          onConfirm={handleZipConfirm}
        />
      )}

      {/* Real-Time Processing Lifecycle Tracker */}
      <AnimatePresence>
        {activeStatus && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <DocumentProgress
              status={activeStatus}
              documentName={activeDocName}
              isPolling={isPolling}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Filter Bar & Document Registry Table */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Filter by Pipeline State:
            </span>
            <div className="flex flex-wrap gap-1.5 ml-2">
              {filterOptions.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setStatusFilter(opt.value)}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                    statusFilter === opt.value
                      ? 'bg-primary text-primary-foreground shadow-sm'
                      : 'bg-surface border border-border text-muted-foreground hover:text-foreground hover:bg-muted'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <DocumentList
          documents={documents}
          isLoading={isLoading}
          onSelectDocument={(doc) => setSelectedDocId(doc.id)}
          onDeleteDocument={handleDelete}
          onArchiveDocument={handleArchive}
          onRestoreDocument={handleRestore}
        />
      </div>

      {/* Canonical Manifest Drawer / Modal (`Refinement 1`) */}
      <DocumentDetailDrawer
        documentId={selectedDocId}
        onClose={() => setSelectedDocId(null)}
      />
    </PageTransition>
  )
}
