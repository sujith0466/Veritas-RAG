import * as React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  RefreshCw,
  Filter,
  Search,
  X,
  Globe,
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
  AddWebsiteDialog,
} from './components'

export function DocumentsPage() {
  const [documents, setDocuments] = React.useState<DocumentResponse[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [statusFilter, setStatusFilter] = React.useState<string>('ALL')
  const [searchQuery, setSearchQuery] = React.useState<string>('')
  const [debouncedSearch, setDebouncedSearch] = React.useState<string>('')

  // Add website dialog state
  const [isAddWebsiteOpen, setIsAddWebsiteOpen] = React.useState(false)

  // Pagination & Sorting state
  const [page, setPage] = React.useState(1)
  const [pageSize, setPageSize] = React.useState(20)
  const [totalCount, setTotalCount] = React.useState(0)
  const [totalPages, setTotalPages] = React.useState(1)
  const [sortBy, setSortBy] = React.useState('created_at')
  const [sortOrder, setSortOrder] = React.useState<'asc' | 'desc'>('desc')

  // Active upload & polling state
  const [isUploading, setIsUploading] = React.useState(false)
  const [uploadProgress, setUploadProgress] = React.useState(0)
  const [activeStatus, setActiveStatus] = React.useState<ProcessingStatusResponse | null>(null)
  const [activeDocName, setActiveDocName] = React.useState<string>('')
  const [isPolling, setIsPolling] = React.useState(false)
  const [selectedZipFile, setSelectedZipFile] = React.useState<File | null>(null)

  // Detail drawer state
  const [selectedDocId, setSelectedDocId] = React.useState<string | null>(null)

  // Debounce search query
  React.useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchQuery)
      setPage(1) // Reset to page 1 on search change
    }, 300)
    return () => clearTimeout(handler)
  }, [searchQuery])

  const fetchDocuments = React.useCallback(async () => {
    try {
      const resp = await documentService.listDocuments(
        page,
        pageSize,
        statusFilter,
        debouncedSearch,
        sortBy,
        sortOrder
      )
      setDocuments(resp.items || [])
      setTotalCount(resp.total || 0)
      setTotalPages(resp.pages || 1)
    } catch (err) {
      console.error('Failed to fetch documents:', err)
    } finally {
      setIsLoading(false)
    }
  }, [page, pageSize, statusFilter, debouncedSearch, sortBy, sortOrder])

  React.useEffect(() => {
    setIsLoading(true)
    fetchDocuments()
  }, [fetchDocuments])

  // Restore in-flight polling from sessionStorage on mount
  React.useEffect(() => {
    try {
      const saved = sessionStorage.getItem('raguard_active_doc_poll')
      if (saved) {
        const parsed = JSON.parse(saved)
        if (parsed.document_id && parsed.status !== 'READY' && parsed.status !== 'FAILED') {
          setActiveStatus(parsed)
          setActiveDocName(parsed.document_name || '')
          setIsPolling(true)
        } else {
          sessionStorage.removeItem('raguard_active_doc_poll')
        }
      }
    } catch {
      // Safe fallback
    }
  }, [])

  // Resilient polling effect for active document job through READY / FAILED
  React.useEffect(() => {
    if (!activeStatus || !isPolling) return

    const pollStartTime = Date.now()
    const MAX_POLL_DURATION_MS = 600000 // 10 minutes timeout safeguard

    const interval = setInterval(async () => {
      // Check timeout
      if (Date.now() - pollStartTime > MAX_POLL_DURATION_MS) {
        console.warn('Document processing polling reached max timeout (10m). Stopping.')
        setIsPolling(false)
        sessionStorage.removeItem('raguard_active_doc_poll')
        return
      }

      try {
        const latest = await documentService.getDocumentStatus(activeStatus.document_id)
        setActiveStatus(latest)

        const TERMINAL_STATUSES = new Set(['READY', 'FAILED', 'ARCHIVED', 'DELETED'])
        if (TERMINAL_STATUSES.has(latest.status)) {
          setIsPolling(false)
          sessionStorage.removeItem('raguard_active_doc_poll')
          fetchDocuments() // Refresh registry table
        } else {
          // Persist in-flight state
          try {
            sessionStorage.setItem(
              'raguard_active_doc_poll',
              JSON.stringify({ ...latest, document_name: activeDocName })
            )
          } catch {
            // Ignore storage errors
          }
        }
      } catch (err) {
        console.error('Polling error:', err)
        setIsPolling(false)
        sessionStorage.removeItem('raguard_active_doc_poll')
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [activeStatus?.document_id, isPolling, fetchDocuments, activeDocName])

  const handleUpload = async (file: File, onProgress: (percent: number) => void) => {
    setIsUploading(true)
    setUploadProgress(0)
    try {
      const resp = await documentService.uploadDocument(file, (percent) => {
        setUploadProgress(percent)
        onProgress(percent)
      })

      setActiveDocName(file.name)
      const initialStatus: ProcessingStatusResponse = {
        document_id: resp.document_id,
        status: resp.status,
        current_step: 'validation',
        progress_percent: 20,
        retry_count: 0,
        updated_at: resp.created_at,
      }
      setActiveStatus(initialStatus)
      try {
        sessionStorage.setItem(
          'raguard_active_doc_poll',
          JSON.stringify({ ...initialStatus, document_name: file.name })
        )
      } catch {
        // Ignore storage errors
      }
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

  const handleRetry = async (docId: string) => {
    try {
      const resp = await documentService.retryDocument(docId)
      const doc = documents.find((d) => d.id === docId)
      setActiveDocName(doc?.filename || 'Retrying document')
      const initialStatus: ProcessingStatusResponse = {
        document_id: resp.document_id,
        status: resp.status,
        current_step: 'upload',
        progress_percent: 10,
        retry_count: 0,
        updated_at: new Date().toISOString(),
      }
      setActiveStatus(initialStatus)
      setIsPolling(true)
      await fetchDocuments()
    } catch (err) {
      console.error('Failed to retry document:', err)
    }
  }

  const handleReingest = async (docId: string) => {
    try {
      const resp = await documentService.reingestDocument(docId)
      const doc = documents.find((d) => d.id === docId)
      setActiveDocName(doc?.filename || 'Re-ingesting document')
      const initialStatus: ProcessingStatusResponse = {
        document_id: resp.document_id,
        status: resp.status,
        current_step: 'upload',
        progress_percent: 10,
        retry_count: 0,
        updated_at: new Date().toISOString(),
      }
      setActiveStatus(initialStatus)
      setIsPolling(true)
      await fetchDocuments()
    } catch (err) {
      console.error('Failed to re-ingest document:', err)
    }
  }

  const handleRefreshWebsite = async (docId: string) => {
    try {
      const resp = await documentService.refreshWebsiteDocument(docId)
      const doc = documents.find((d) => d.id === docId)
      setActiveDocName(doc?.filename || doc?.source_url || 'Refreshing website knowledge')
      const initialStatus: ProcessingStatusResponse = {
        document_id: resp.document_id,
        status: resp.status,
        current_step: 'fetching',
        progress_percent: 15,
        retry_count: 0,
        updated_at: new Date().toISOString(),
      }
      setActiveStatus(initialStatus)
      try {
        sessionStorage.setItem(
          'raguard_active_doc_poll',
          JSON.stringify({ ...initialStatus, document_name: doc?.filename || doc?.source_url || 'Website Document' })
        )
      } catch {
        // Safe fallback
      }
      setIsPolling(true)
      await fetchDocuments()
    } catch (err) {
      console.error('Failed to refresh website knowledge:', err)
    }
  }

  const handleDownloadOriginal = async (doc: DocumentResponse) => {
    try {
      await documentService.downloadOriginal(doc.id, doc.original_filename || doc.filename)
    } catch (err) {
      console.error('Download original failed:', err)
    }
  }

  const handleDownloadExtractedText = async (doc: DocumentResponse) => {
    try {
      await documentService.downloadExtractedText(doc.id, `${doc.filename}.extracted.txt`)
    } catch (err) {
      console.error('Download extracted text failed:', err)
    }
  }

  const handleSortChange = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortOrder('desc')
    }
    setPage(1)
  }

  const filterOptions = [
    { label: 'All Documents', value: 'ALL' },
    { label: 'Ready & Ingested', value: 'READY' },
    { label: 'Processing', value: 'EXTRACTING' },
    { label: 'Failed', value: 'FAILED' },
    { label: 'Archived', value: 'ARCHIVED' },
  ]

  return (
    <PageTransition className="space-y-8 pb-12">
      <PageHeader
        title="Document Intelligence & Knowledge Store"
        description="Enterprise-grade document ingestion, OCR density extraction, vector sync, resilient retry, and lifecycle management."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="default"
              size="sm"
              onClick={() => setIsAddWebsiteOpen(true)}
              className="flex items-center gap-1.5 shadow-sm"
            >
              <Globe className="h-3.5 w-3.5" />
              Add Website
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => fetchDocuments()}
              isLoading={isLoading}
              className="flex items-center gap-1.5 shadow-sm"
            >
              {!isLoading && <RefreshCw className="h-3.5 w-3.5" />}
              Refresh Registry
            </Button>
          </div>
        }
      />

      {/* Upload Dropzone */}
      <UploadDropzone
        onUpload={handleUpload}
        onZipSelect={(file) => setSelectedZipFile(file)}
        isUploading={isUploading}
        uploadProgress={uploadProgress}
      />

      {/* Add Website Dialog */}
      <AddWebsiteDialog
        isOpen={isAddWebsiteOpen}
        onClose={() => setIsAddWebsiteOpen(false)}
        onSuccess={(resp, url) => {
          setActiveDocName(url)
          const initialStatus: ProcessingStatusResponse = {
            document_id: resp.document_id,
            status: resp.status,
            current_step: 'fetching',
            progress_percent: 15,
            retry_count: 0,
            updated_at: new Date().toISOString(),
          }
          setActiveStatus(initialStatus)
          try {
            sessionStorage.setItem(
              'raguard_active_doc_poll',
              JSON.stringify({ ...initialStatus, document_name: url })
            )
          } catch {
            // Safe fallback
          }
          setIsPolling(true)
          fetchDocuments()
        }}
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

      {/* Filter Bar, Search Input & Document Registry Table */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-surface rounded-xl border border-border/70 shadow-xs">
          {/* Status Filters */}
          <div className="flex flex-wrap items-center gap-1.5">
            <Filter className="h-4 w-4 text-muted-foreground mr-1" />
            {filterOptions.map((opt) => (
              <button
                key={opt.value}
                onClick={() => {
                  setStatusFilter(opt.value)
                  setPage(1)
                }}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  statusFilter === opt.value
                    ? 'bg-primary text-primary-foreground shadow-xs'
                    : 'bg-muted/50 text-muted-foreground hover:text-foreground hover:bg-muted'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Search Input Bar */}
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search filename..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-8 py-1.5 text-xs rounded-lg border border-border bg-background text-foreground placeholder:text-muted-foreground/70 focus:outline-none focus:ring-1 focus:ring-primary"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>
        </div>

        <DocumentList
          documents={documents}
          isLoading={isLoading}
          page={page}
          pageSize={pageSize}
          totalCount={totalCount}
          totalPages={totalPages}
          sortBy={sortBy}
          sortOrder={sortOrder}
          onPageChange={setPage}
          onPageSizeChange={(newSize) => {
            setPageSize(newSize)
            setPage(1)
          }}
          onSortChange={handleSortChange}
          onSelectDocument={(doc) => setSelectedDocId(doc.id)}
          onDeleteDocument={handleDelete}
          onArchiveDocument={handleArchive}
          onRestoreDocument={handleRestore}
          onRetryDocument={handleRetry}
          onReingestDocument={handleReingest}
          onRefreshWebsite={handleRefreshWebsite}
          onDownloadOriginal={handleDownloadOriginal}
          onDownloadExtractedText={handleDownloadExtractedText}
        />
      </div>

      {/* Canonical Manifest Drawer / Modal */}
      <DocumentDetailDrawer
        documentId={selectedDocId}
        onClose={() => setSelectedDocId(null)}
        onReingest={handleReingest}
        onRefreshWebsite={handleRefreshWebsite}
      />
    </PageTransition>
  )
}

