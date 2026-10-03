import * as React from 'react'
import {
  Database,
  RefreshCw,
  Layers,
  HardDrive,
  ShieldCheck,
  Search,
  AlertCircle,
  Play,
  Loader2,
} from 'lucide-react'
import { Button } from '@/components/common'
import { vectorService } from '@/services/vectorService'
import { documentService } from '@/services/documentService'
import type {
  QdrantClusterHealthDTO,
  VectorIndexMetadataDTO,
  DocumentResponse,
} from '@/types'
import { CollectionHealthCard, IndexSyncTable } from './index'

/**
 * Valid document statuses eligible for vector indexing and synchronization.
 * Includes documents with extracted chunks, embeddings, or verified steady-state content.
 */
const ELIGIBLE_DOCUMENT_STATUSES = new Set([
  'READY',
  'PROCESSED',
  'EMBEDDED',
  'VECTOR_SYNC',
  'CHUNKED',
  'EMBEDDING',
])

export function VectorsStageView() {
  const [health, setHealth] = React.useState<QdrantClusterHealthDTO | null>(null)
  const [records, setRecords] = React.useState<VectorIndexMetadataDTO[]>([])
  const [documents, setDocuments] = React.useState<DocumentResponse[]>([])
  const [selectedDocId, setSelectedDocId] = React.useState<string>('')
  const [searchDocId, setSearchDocId] = React.useState<string>('')

  const [isLoadingInitial, setIsLoadingInitial] = React.useState<boolean>(true)
  const [isLoadingRecords, setIsLoadingRecords] = React.useState<boolean>(false)
  const [isSyncing, setIsSyncing] = React.useState<boolean>(false)
  const [stageError, setStageError] = React.useState<string | null>(null)
  const [actionNotice, setActionNotice] = React.useState<string | null>(null)

  const fetchRecordsForDoc = React.useCallback(async (docId: string) => {
    if (!docId.trim()) {
      setRecords([])
      return
    }
    setIsLoadingRecords(true)
    try {
      const docRecords = await vectorService.getDocumentStatus(docId.trim())
      setRecords(docRecords || [])
    } catch (err: any) {
      console.error('Failed to fetch document vector status:', err)
      setRecords([])
    } finally {
      setIsLoadingRecords(false)
    }
  }, [])

  const fetchInitialData = React.useCallback(async () => {
    setIsLoadingInitial(true)
    setStageError(null)
    try {
      const [healthData, docListResponse] = await Promise.all([
        vectorService.getHealth(),
        documentService.listDocuments(1, 100),
      ])

      setHealth(healthData)

      const eligibleDocs = (docListResponse?.items || []).filter((doc: DocumentResponse) =>
        ELIGIBLE_DOCUMENT_STATUSES.has(doc.status?.toUpperCase())
      )
      setDocuments(eligibleDocs)

      const initialDocId = searchDocId.trim() || (eligibleDocs.length > 0 ? eligibleDocs[0].id : '')
      if (initialDocId) {
        setSelectedDocId(initialDocId)
        await fetchRecordsForDoc(initialDocId)
      } else {
        setRecords([])
      }
    } catch (err: any) {
      console.error('Failed to initialize vector stage:', err)
      setStageError(err?.message || 'Failed to fetch vector cluster statistics.')
    } finally {
      setIsLoadingInitial(false)
    }
  }, [searchDocId, fetchRecordsForDoc])

  React.useEffect(() => {
    fetchInitialData()
  }, [fetchInitialData])

  const handleDocumentSelect = async (docId: string) => {
    setSelectedDocId(docId)
    setSearchDocId(docId)
    await fetchRecordsForDoc(docId)
  }

  const handleSearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (searchDocId.trim()) {
      setSelectedDocId(searchDocId.trim())
      await fetchRecordsForDoc(searchDocId.trim())
    } else if (documents.length > 0) {
      setSelectedDocId(documents[0].id)
      await fetchRecordsForDoc(documents[0].id)
    } else {
      setRecords([])
    }
  }

  const handleTriggerSync = async () => {
    if (!selectedDocId) return
    const activeDoc = documents.find((d) => d.id === selectedDocId)
    const versionId = activeDoc?.latest_version_id || selectedDocId

    setIsSyncing(true)
    setActionNotice(null)
    setStageError(null)
    try {
      await vectorService.syncDocument(versionId, { document_id: selectedDocId })
      setActionNotice(`Vector synchronization dispatched for document version ${versionId.slice(0, 8)}...`)
      await fetchRecordsForDoc(selectedDocId)
      const updatedHealth = await vectorService.getHealth().catch(() => null)
      if (updatedHealth) setHealth(updatedHealth)
    } catch (err: any) {
      console.error('Failed to trigger vector sync:', err)
      setStageError(err?.message || 'Failed to trigger vector synchronization.')
    } finally {
      setIsSyncing(false)
    }
  }

  const handleResync = async (documentId: string, versionId: string) => {
    setIsSyncing(true)
    setActionNotice(null)
    try {
      await vectorService.syncDocument(versionId, { document_id: documentId })
      setActionNotice(`Resynchronization initiated for version ${versionId.slice(0, 8)}...`)
      await fetchRecordsForDoc(documentId)
      const updatedHealth = await vectorService.getHealth().catch(() => null)
      if (updatedHealth) setHealth(updatedHealth)
    } catch (err: any) {
      alert(err instanceof Error ? err.message : 'Failed to resynchronize document vectors.')
    } finally {
      setIsSyncing(false)
    }
  }

  const handleDelete = async (documentId: string) => {
    if (!confirm(`Are you sure you want to purge all points for document ${documentId}?`)) return
    setActionNotice(null)
    try {
      const summary = await vectorService.deleteDocumentPoints(documentId)
      setActionNotice(`Purged ${summary?.purged_points_count ?? 0} points for document ${documentId.slice(0, 8)}...`)
      await fetchRecordsForDoc(documentId)
      const updatedHealth = await vectorService.getHealth().catch(() => null)
      if (updatedHealth) setHealth(updatedHealth)
    } catch (err: any) {
      alert(err instanceof Error ? err.message : 'Failed to delete document points.')
    }
  }

  return (
    <div className="space-y-6">
      {/* Stage Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-2 border-b border-border/60">
        <div>
          <h2 className="text-base font-bold text-foreground">
            Stage 3: Vector Storage Foundation (Qdrant)
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Qdrant cluster health, multi-tenant collections, and version synchronization state.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={fetchInitialData}
          disabled={isLoadingInitial}
          className="gap-2 shrink-0"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoadingInitial ? 'animate-spin' : ''}`} />
          Refresh Cluster
        </Button>
      </div>

      {/* Stage Error Alert (Isolated) */}
      {stageError && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 flex items-center justify-between text-xs text-destructive">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{stageError}</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchInitialData}
            className="text-xs border-destructive/30 hover:bg-destructive/20 text-destructive h-7 px-2.5"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Action Notification Banner */}
      {actionNotice && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-400 flex items-center justify-between">
          <span>{actionNotice}</span>
          <button
            onClick={() => setActionNotice(null)}
            className="text-muted-foreground hover:text-foreground text-xs"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Cluster Summary Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-xl border border-border/80 bg-surface/60 backdrop-blur-sm p-4 flex items-center gap-3.5 shadow-sm">
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block">
              Qdrant Status
            </span>
            <span className="text-lg font-bold text-foreground mt-0.5 block">
              {health ? health.status : (isLoadingInitial ? 'CHECKING...' : 'UNKNOWN')}
            </span>
          </div>
        </div>

        <div className="rounded-xl border border-border/80 bg-surface/60 backdrop-blur-sm p-4 flex items-center gap-3.5 shadow-sm">
          <div className="w-10 h-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block">
              Active Collections
            </span>
            <span className="text-lg font-bold text-foreground mt-0.5 block">
              {health ? health.active_collections_count : 0}
            </span>
          </div>
        </div>

        <div className="rounded-xl border border-border/80 bg-surface/60 backdrop-blur-sm p-4 flex items-center gap-3.5 shadow-sm">
          <div className="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
            <Database className="w-5 h-5" />
          </div>
          <div>
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block">
              Total Points Stored
            </span>
            <span className="text-lg font-bold text-foreground mt-0.5 block">
              {health ? health.total_points_stored.toLocaleString() : 0}
            </span>
          </div>
        </div>

        <div className="rounded-xl border border-border/80 bg-surface/60 backdrop-blur-sm p-4 flex items-center gap-3.5 shadow-sm">
          <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <HardDrive className="w-5 h-5" />
          </div>
          <div>
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block">
              Scalar Quantization
            </span>
            <span className="text-lg font-bold text-foreground mt-0.5 block">INT8 (75% Saved)</span>
          </div>
        </div>
      </div>

      {/* Active Collections Topology */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
            <Layers className="w-4 h-4 text-primary" />
            Active Tenant Vector Collections
          </h3>
          <span className="text-xs text-muted-foreground font-medium">
            Strict payload indexing enforced (`tenant_id`, `document_id`)
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {health && health.collections && health.collections.length > 0 ? (
            health.collections.map((col) => (
              <CollectionHealthCard key={col.collection_name} collection={col} status={health.status} />
            ))
          ) : (
            <div className="col-span-3 rounded-xl border border-border border-dashed bg-surface/40 p-8 text-center text-muted-foreground text-xs font-medium">
              No active collections instantiated yet. Collections are auto-created on first document ingestion.
            </div>
          )}
        </div>
      </section>

      {/* Document Version Synchronization Tracking */}
      <section className="space-y-4 pt-2">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
              <Database className="w-4 h-4 text-primary" />
              Document Version Synchronization Tracking
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Inspect or resynchronize staged points across Qdrant namespaces
            </p>
          </div>

          {/* Sync Trigger CTA */}
          {selectedDocId && (
            <Button
              variant="default"
              size="sm"
              onClick={handleTriggerSync}
              disabled={isSyncing || isLoadingRecords}
              className="bg-indigo-600 hover:bg-indigo-500 text-white flex items-center gap-1.5 self-start md:self-auto shrink-0"
            >
              {isSyncing ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Syncing...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Sync Vector Points</span>
                </>
              )}
            </Button>
          )}
        </div>

        {/* Filters and Selector Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 bg-surface/40 border border-border/80 rounded-xl p-3">
          {/* Document Picker */}
          {documents.length > 0 && (
            <div className="flex-1 min-w-[200px]">
              <label htmlFor="vector-doc-select" className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block mb-1">
                Select Indexed Document
              </label>
              <select
                id="vector-doc-select"
                value={selectedDocId}
                onChange={(e) => handleDocumentSelect(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary shadow-sm"
              >
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.original_filename || doc.filename} ({doc.status})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* UUID Search Form */}
          <form onSubmit={handleSearchSubmit} className="flex-1 min-w-[200px]">
            <label htmlFor="vector-uuid-search" className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block mb-1">
              Search by Document UUID
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <input
                id="vector-uuid-search"
                type="text"
                placeholder="Paste Document UUID..."
                value={searchDocId}
                onChange={(e) => setSearchDocId(e.target.value)}
                className="w-full rounded-lg border border-border bg-background pl-9 pr-3 py-1.5 text-xs text-foreground placeholder-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary shadow-sm"
              />
            </div>
          </form>
        </div>

        {/* Index Records Table */}
        <IndexSyncTable
          records={records}
          isLoading={isLoadingRecords || isLoadingInitial}
          onResync={handleResync}
          onDelete={handleDelete}
        />
      </section>
    </div>
  )
}
