import * as React from 'react'
import {
  FileText,
  Eye,
  Trash2,
  Calendar,
  Layers,
  AlertCircle,
  FileCheck2,
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
  onSelectDocument: (doc: DocumentResponse) => void
  onDeleteDocument: (docId: string) => Promise<void>
}

export function DocumentList({
  documents,
  isLoading,
  onSelectDocument,
  onDeleteDocument,
}: DocumentListProps) {
  const [deleteConfirmDoc, setDeleteConfirmDoc] = React.useState<DocumentResponse | null>(null)
  const [isDeleting, setIsDeleting] = React.useState(false)

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

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'PROCESSED':
        return <Badge variant="success">PROCESSED</Badge>
      case 'VALIDATING':
      case 'EXTRACTING':
      case 'RETRYING':
        return <Badge variant="warning" className="animate-pulse">{status}</Badge>
      case 'FAILED':
        return <Badge variant="destructive">FAILED</Badge>
      default:
        return <Badge variant="subtle">{status}</Badge>
    }
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
          title="No Documents Ingested"
          description="Upload documents using the dropzone above to begin provider-independent ingestion, extraction, and validation."
        />
      </Card>
    )
  }

  return (
    <>
      <Card className="overflow-hidden border-border/80">
        <div className="px-6 py-4 border-b border-border/50 flex items-center justify-between bg-surface/50">
          <div>
            <h3 className="font-semibold text-foreground flex items-center gap-2">
              <Layers className="h-4 w-4 text-primary" />
              Tenant Document Registry
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Showing {documents.length} ingested aggregate roots across versioned storage.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[300px]">Document</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Metrics</TableHead>
                <TableHead>Ingested At</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.map((doc) => (
                <TableRow key={doc.id} className="hover:bg-muted/40 transition-colors">
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-3">
                      <div className="h-9 w-9 rounded bg-primary/10 flex items-center justify-center text-primary shrink-0">
                        <FileText className="h-4 w-4" />
                      </div>
                      <div className="overflow-hidden">
                        <div className="font-semibold text-foreground truncate max-w-[220px]" title={doc.filename}>
                          {doc.filename}
                        </div>
                        <div className="text-[11px] text-muted-foreground truncate max-w-[220px]">
                          Original: {doc.original_filename}
                        </div>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>{getStatusBadge(doc.status)}</TableCell>
                  <TableCell>
                    <div className="text-xs space-y-0.5">
                      <div><strong className="text-foreground">{doc.word_count}</strong> words</div>
                      <div className="text-muted-foreground">{doc.page_count} pages ({doc.language || 'en'})</div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Calendar className="h-3.5 w-3.5 shrink-0" />
                      <span>{new Date(doc.created_at).toLocaleDateString()} {new Date(doc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onSelectDocument(doc)}
                      >
                        <Eye className="mr-2 h-3.5 w-3.5" />
                        Details & Manifest
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-muted-foreground hover:text-danger hover:bg-danger/10"
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
              Are you sure you want to soft-delete <strong>{deleteConfirmDoc?.filename}</strong> and purge all physical version artifacts (`/original`, `/normalized/text.txt`, `/metadata`) from storage?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-6">
            <Button variant="outline" onClick={() => setDeleteConfirmDoc(null)} disabled={isDeleting}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} isLoading={isDeleting}>
              Delete & Purge Storage
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
