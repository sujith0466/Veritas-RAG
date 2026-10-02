import * as React from 'react'
import {
  FileText,
  Eye,
  Trash2,
  Calendar,
  Layers,
  AlertCircle,
  FileCheck2,
  Download,
  RotateCw,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from 'lucide-react'
import {
  Button,
  Badge,
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  EmptyState,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/common'
import type { DocumentResponse } from '@/types'

export interface DocumentListProps {
  documents: DocumentResponse[]
  isLoading: boolean
  page: number
  pageSize: number
  totalCount: number
  totalPages: number
  sortBy: string
  sortOrder: 'asc' | 'desc'
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
  onSortChange: (field: string) => void
  onSelectDocument: (doc: DocumentResponse) => void
  onDeleteDocument: (docId: string) => Promise<void>
  onArchiveDocument?: (docId: string) => Promise<void>
  onRestoreDocument?: (docId: string) => Promise<void>
  onRetryDocument?: (docId: string) => Promise<void>
  onReingestDocument?: (docId: string) => Promise<void>
  onDownloadOriginal?: (doc: DocumentResponse) => Promise<void>
  onDownloadExtractedText?: (doc: DocumentResponse) => Promise<void>
}

export function DocumentList({
  documents,
  isLoading,
  page,
  pageSize,
  totalCount,
  totalPages,
  sortBy,
  sortOrder,
  onPageChange,
  onPageSizeChange,
  onSortChange,
  onSelectDocument,
  onDeleteDocument,
  onArchiveDocument,
  onRestoreDocument,
  onRetryDocument,
  onReingestDocument,
  onDownloadOriginal,
  onDownloadExtractedText,
}: DocumentListProps) {
  const [deleteConfirmDoc, setDeleteConfirmDoc] = React.useState<DocumentResponse | null>(null)
  const [archiveConfirmDoc, setArchiveConfirmDoc] = React.useState<DocumentResponse | null>(null)
  const [reingestConfirmDoc, setReingestConfirmDoc] = React.useState<DocumentResponse | null>(null)
  const [isDeleting, setIsDeleting] = React.useState(false)
  const [isArchiving, setIsArchiving] = React.useState(false)
  const [isReingesting, setIsReingesting] = React.useState(false)
  const [retryingDocId, setRetryingDocId] = React.useState<string | null>(null)

  const handleDelete = async () => {
    if (!deleteConfirmDoc) return
    setIsDeleting(true)
    try {
      await onDeleteDocument(deleteConfirmDoc.id)
      setDeleteConfirmDoc(null)
    } finally {
      setIsDeleting(false)
    }
  }

  const handleArchive = async () => {
    if (!archiveConfirmDoc || !onArchiveDocument) return
    setIsArchiving(true)
    try {
      await onArchiveDocument(archiveConfirmDoc.id)
      setArchiveConfirmDoc(null)
    } finally {
      setIsArchiving(false)
    }
  }

  const handleReingest = async () => {
    if (!reingestConfirmDoc || !onReingestDocument) return
    setIsReingesting(true)
    try {
      await onReingestDocument(reingestConfirmDoc.id)
      setReingestConfirmDoc(null)
    } finally {
      setIsReingesting(false)
    }
  }

  const handleRetry = async (docId: string) => {
    if (!onRetryDocument) return
    setRetryingDocId(docId)
    try {
      await onRetryDocument(docId)
    } finally {
      setRetryingDocId(null)
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'READY':
      case 'PROCESSED':
        return <Badge variant="success">{status}</Badge>
      case 'VALIDATING':
      case 'EXTRACTING':
      case 'OCR':
      case 'CHUNKING':
      case 'EMBEDDING':
      case 'VECTOR_SYNC':
      case 'RETRYING':
        return <Badge variant="warning" className="animate-pulse">{status}</Badge>
      case 'FAILED':
        return <Badge variant="destructive">FAILED</Badge>
      case 'ARCHIVED':
        return <Badge variant="outline">ARCHIVED</Badge>
      case 'UPLOADED':
      case 'PENDING':
      default:
        return <Badge variant="subtle">{status}</Badge>
    }
  }

  const renderSortIcon = (field: string) => {
    if (sortBy !== field) {
      return <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground/60 ml-1 inline" />
    }
    return sortOrder === 'asc' ? (
      <ArrowUp className="h-3.5 w-3.5 text-primary ml-1 inline" />
    ) : (
      <ArrowDown className="h-3.5 w-3.5 text-primary ml-1 inline" />
    )
  }

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="space-y-4 animate-pulse">
          <div className="h-6 w-48 bg-muted rounded" />
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-12 w-full bg-muted/60 rounded" />
            ))}
          </div>
        </div>
      </Card>
    )
  }

  if (documents.length === 0) {
    return (
      <Card className="p-8">
        <EmptyState
          icon={FileCheck2}
          title="No Documents Found"
          description="No documents matched your criteria. Upload a document or adjust filters/search query."
        />
      </Card>
    )
  }

  return (
    <>
      <Card className="overflow-hidden border-border/80 shadow-sm">
        <div className="px-6 py-4 border-b border-border/50 flex flex-wrap items-center justify-between gap-3 bg-surface/50">
          <div>
            <h3 className="font-semibold text-foreground flex items-center gap-2">
              <Layers className="h-4 w-4 text-primary" />
              Document Registry & Knowledge Store
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Showing {Math.min(documents.length, totalCount)} of {totalCount} total items across tenant storage.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/20">
                <TableHead
                  className="w-[280px] cursor-pointer hover:text-foreground transition-colors select-none"
                  onClick={() => onSortChange('filename')}
                >
                  <span className="flex items-center">
                    Document Name {renderSortIcon('filename')}
                  </span>
                </TableHead>
                <TableHead
                  className="cursor-pointer hover:text-foreground transition-colors select-none"
                  onClick={() => onSortChange('status')}
                >
                  <span className="flex items-center">
                    Pipeline Status {renderSortIcon('status')}
                  </span>
                </TableHead>
                <TableHead
                  className="cursor-pointer hover:text-foreground transition-colors select-none"
                  onClick={() => onSortChange('word_count')}
                >
                  <span className="flex items-center">
                    Metrics {renderSortIcon('word_count')}
                  </span>
                </TableHead>
                <TableHead
                  className="cursor-pointer hover:text-foreground transition-colors select-none"
                  onClick={() => onSortChange('created_at')}
                >
                  <span className="flex items-center">
                    Ingested At {renderSortIcon('created_at')}
                  </span>
                </TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.map((doc) => (
                <TableRow key={doc.id} className="hover:bg-muted/40 transition-colors">
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-3">
                      <div className="h-9 w-9 rounded-lg bg-primary/10 flex items-center justify-center text-primary shrink-0">
                        <FileText className="h-4 w-4" />
                      </div>
                      <div className="overflow-hidden">
                        <div className="font-semibold text-foreground truncate max-w-[200px]" title={doc.filename}>
                          {doc.filename}
                        </div>
                        <div className="text-[11px] text-muted-foreground truncate max-w-[200px]" title={doc.original_filename}>
                          {doc.original_filename}
                        </div>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>{getStatusBadge(doc.status)}</TableCell>
                  <TableCell>
                    <div className="text-xs space-y-0.5">
                      <div><strong className="text-foreground">{doc.word_count.toLocaleString()}</strong> words</div>
                      <div className="text-muted-foreground">{doc.page_count} pages ({doc.language || 'en'})</div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Calendar className="h-3.5 w-3.5 shrink-0" />
                      <span>
                        {new Date(doc.created_at).toLocaleDateString()} {new Date(doc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      {/* Download Original */}
                      {onDownloadOriginal && (
                        <Button
                          variant="ghost"
                          size="sm"
                          title="Download Original File"
                          className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-muted"
                          onClick={() => onDownloadOriginal(doc)}
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                      )}

                      {/* Download Extracted Text */}
                      {onDownloadExtractedText && (doc.status === 'READY' || doc.status === 'PROCESSED') && (
                        <Button
                          variant="ghost"
                          size="sm"
                          title="Download Normalized Text"
                          className="h-8 w-8 p-0 text-primary hover:text-primary hover:bg-primary/10"
                          onClick={() => onDownloadExtractedText(doc)}
                        >
                          <FileText className="h-4 w-4" />
                        </Button>
                      )}

                      {/* Retry on Failed */}
                      {doc.status === 'FAILED' && onRetryDocument && (
                        <Button
                          variant="ghost"
                          size="sm"
                          title="Retry Failed Ingestion"
                          className="h-8 w-8 p-0 text-amber-500 hover:text-amber-600 hover:bg-amber-500/10"
                          isLoading={retryingDocId === doc.id}
                          onClick={() => handleRetry(doc.id)}
                        >
                          <RotateCw className="h-4 w-4" />
                        </Button>
                      )}

                      {/* Re-ingest on Completed */}
                      {(doc.status === 'READY' || doc.status === 'PROCESSED') && onReingestDocument && (
                        <Button
                          variant="ghost"
                          size="sm"
                          title="Re-ingest Document"
                          className="h-8 w-8 p-0 text-muted-foreground hover:text-primary hover:bg-primary/10"
                          onClick={() => setReingestConfirmDoc(doc)}
                        >
                          <RefreshCw className="h-4 w-4" />
                        </Button>
                      )}

                      {/* Details Drawer */}
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 px-2.5 text-xs flex items-center gap-1"
                        onClick={() => onSelectDocument(doc)}
                      >
                        <Eye className="h-3.5 w-3.5" />
                        Inspect
                      </Button>

                      {/* Archive / Restore */}
                      {doc.status === 'ARCHIVED' && onRestoreDocument ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 px-2 text-xs text-success hover:bg-success/10"
                          onClick={() => onRestoreDocument(doc.id)}
                        >
                          Restore
                        </Button>
                      ) : (
                        doc.status !== 'ARCHIVED' && onArchiveDocument && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 px-2 text-xs text-muted-foreground hover:text-warning hover:bg-warning/10"
                            onClick={() => setArchiveConfirmDoc(doc)}
                          >
                            Archive
                          </Button>
                        )
                      )}

                      {/* Delete */}
                      <Button
                        variant="ghost"
                        size="sm"
                        title="Delete Document"
                        className="h-8 w-8 p-0 text-muted-foreground hover:text-danger hover:bg-danger/10"
                        onClick={() => setDeleteConfirmDoc(doc)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* Pagination Bar */}
        <div className="px-6 py-3 border-t border-border/50 flex flex-wrap items-center justify-between gap-3 bg-surface/40 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <span>Rows per page:</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="bg-surface border border-border rounded px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
            <span className="ml-2">
              Page <strong>{page}</strong> of <strong>{totalPages || 1}</strong> ({totalCount} items)
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2"
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
            >
              <ChevronLeft className="h-3.5 w-3.5 mr-1" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2"
              disabled={page >= totalPages}
              onClick={() => onPageChange(page + 1)}
            >
              Next
              <ChevronRight className="h-3.5 w-3.5 ml-1" />
            </Button>
          </div>
        </div>
      </Card>

      {/* Delete Confirmation Modal */}
      <Dialog open={!!deleteConfirmDoc} onOpenChange={(open) => !open && setDeleteConfirmDoc(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-danger">
              <AlertCircle className="h-5 w-5" />
              Confirm Document Deletion
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to soft-delete <strong>{deleteConfirmDoc?.filename}</strong> and purge all physical version artifacts from storage?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-6">
            <Button variant="outline" onClick={() => setDeleteConfirmDoc(null)} disabled={isDeleting}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} isLoading={isDeleting}>
              Yes, Delete Permanently
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Archive Confirmation Modal */}
      <Dialog open={!!archiveConfirmDoc} onOpenChange={(open) => !open && setArchiveConfirmDoc(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-warning">
              <AlertCircle className="h-5 w-5" />
              Confirm Document Archive
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to archive <strong>{archiveConfirmDoc?.filename}</strong>? This will purge its vectors from Qdrant, making it unavailable for search, while keeping physical storage safe.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-6">
            <Button variant="outline" onClick={() => setArchiveConfirmDoc(null)} disabled={isArchiving}>
              Cancel
            </Button>
            <Button variant="default" onClick={handleArchive} isLoading={isArchiving}>
              Yes, Archive Document
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Re-ingest Confirmation Modal */}
      <Dialog open={!!reingestConfirmDoc} onOpenChange={(open) => !open && setReingestConfirmDoc(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-primary">
              <RefreshCw className="h-5 w-5" />
              Confirm Complete Re-ingestion
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to re-ingest <strong>{reingestConfirmDoc?.filename}</strong>? This will wipe existing vector index chunks and rerun the full extraction and embedding pipeline.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-6">
            <Button variant="outline" onClick={() => setReingestConfirmDoc(null)} disabled={isReingesting}>
              Cancel
            </Button>
            <Button variant="default" onClick={handleReingest} isLoading={isReingesting}>
              Yes, Re-ingest
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

