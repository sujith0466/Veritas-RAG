import { useState } from 'react'
import {
  Database,
  RefreshCw,
  Trash2,
  CheckCircle2,
  XCircle,
  Clock,
  Code,
  AlertCircle,
} from 'lucide-react'
import { Badge, Button } from '@/components/common'
import type { VectorIndexMetadataDTO } from '@/types'
import { PayloadInspectorModal } from './PayloadInspectorModal'

interface IndexSyncTableProps {
  records: VectorIndexMetadataDTO[]
  isLoading: boolean
  onResync: (documentId: string, versionId: string) => void
  onDelete: (documentId: string) => void
}

export function IndexSyncTable({
  records,
  isLoading,
  onResync,
  onDelete,
}: IndexSyncTableProps) {
  const [selectedRecord, setSelectedRecord] = useState<VectorIndexMetadataDTO | null>(null)
  const [isInspectorOpen, setIsInspectorOpen] = useState(false)

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return (
          <Badge variant="success" className="flex items-center gap-1 w-fit text-xs px-2.5 py-0.5">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            <span>Completed</span>
          </Badge>
        )
      case 'PROCESSING':
        return (
          <Badge variant="warning" className="flex items-center gap-1 w-fit text-xs px-2.5 py-0.5">
            <RefreshCw className="w-3 h-3 animate-spin text-amber-400" />
            <span>Processing</span>
          </Badge>
        )
      case 'FAILED':
        return (
          <Badge variant="destructive" className="flex items-center gap-1 w-fit text-xs px-2.5 py-0.5">
            <XCircle className="w-3 h-3 text-rose-400" />
            <span>Failed</span>
          </Badge>
        )
      default:
        return (
          <Badge variant="secondary" className="flex items-center gap-1 w-fit text-xs px-2.5 py-0.5">
            <Clock className="w-3 h-3 text-muted-foreground" />
            <span>{status}</span>
          </Badge>
        )
    }
  }

  if (isLoading) {
    return (
      <div className="rounded-xl border border-border bg-surface/60 p-12 text-center">
        <RefreshCw className="mx-auto h-8 w-8 animate-spin text-indigo-400" />
        <p className="mt-3 text-sm font-medium text-foreground">Loading index records...</p>
      </div>
    )
  }

  if (records.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface/60 p-12 text-center">
        <Database className="mx-auto h-10 w-10 text-muted-foreground" />
        <h3 className="mt-4 text-base font-semibold text-foreground">No Vector Index Records Found</h3>
        <p className="mt-1 text-sm text-muted-foreground max-w-md mx-auto">
          Synchronize document versions after batch embedding to stage points inside Qdrant collections.
        </p>
      </div>
    )
  }

  return (
    <>
      <div className="overflow-hidden rounded-xl border border-border bg-surface/60 shadow-md">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-foreground">
            <thead className="bg-background/60 text-muted-foreground border-b border-border uppercase font-semibold">
              <tr>
                <th className="px-4 py-3.5">Document ID</th>
                <th className="px-4 py-3.5">Version ID</th>
                <th className="px-4 py-3.5">Collection</th>
                <th className="px-4 py-3.5">Points</th>
                <th className="px-4 py-3.5">Status</th>
                <th className="px-4 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60 font-mono">
              {records.map((rec) => (
                <tr key={rec.id} className="hover:bg-border/40 transition-colors">
                  <td className="px-4 py-3 font-medium text-foreground">
                    {rec.document_id.slice(0, 8)}...
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {rec.document_version_id.slice(0, 8)}...
                  </td>
                  <td className="px-4 py-3 text-indigo-300">{rec.collection_name}</td>
                  <td className="px-4 py-3 font-semibold text-foreground">
                    {rec.points_count.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 font-sans">
                    <div className="flex flex-col gap-1">
                      {renderStatusBadge(rec.status)}
                      {rec.error_message && (
                        <span className="text-[10px] text-rose-400 flex items-center gap-1 truncate max-w-xs font-sans">
                          <AlertCircle className="w-3 h-3 shrink-0" />
                          {rec.error_message}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right font-sans">
                    <div className="flex items-center justify-end gap-1.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setSelectedRecord(rec)
                          setIsInspectorOpen(true)
                        }}
                        title="Inspect indexed payload JSON"
                        className="h-8 px-2 text-indigo-400 hover:text-indigo-300 hover:bg-indigo-500/10"
                      >
                        <Code className="w-4 h-4 mr-1" />
                        Payload
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onResync(rec.document_id, rec.document_version_id)}
                        title="Resynchronize vector points"
                        className="h-8 px-2.5 text-foreground border-border hover:bg-border"
                      >
                        <RefreshCw className="w-3.5 h-3.5 mr-1" />
                        Resync
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onDelete(rec.document_id)}
                        title="Purge all document points"
                        className="h-8 px-2 text-rose-400 hover:text-rose-300 hover:bg-rose-500/10"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <PayloadInspectorModal
        isOpen={isInspectorOpen}
        onClose={() => setIsInspectorOpen(false)}
        metadataRecord={selectedRecord}
      />
    </>
  )
}
