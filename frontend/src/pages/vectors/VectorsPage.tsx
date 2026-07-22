import { useEffect, useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  Database,
  RefreshCw,
  Layers,
  HardDrive,
  ShieldCheck,
  Search,
} from 'lucide-react'
import { Button } from '@/components/common'
import { PageTransition } from '@/components/layouts'
import { vectorService } from '@/services/vectorService'
import type { QdrantClusterHealthDTO, VectorIndexMetadataDTO } from '@/types'
import { CollectionHealthCard, IndexSyncTable } from './components'

export function VectorsPage() {
  const [health, setHealth] = useState<QdrantClusterHealthDTO | null>(null)
  const [records, setRecords] = useState<VectorIndexMetadataDTO[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchDocId, setSearchDocId] = useState('')
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const healthData = await vectorService.getHealth()
      setHealth(healthData)

      if (searchDocId.trim()) {
        const docRecords = await vectorService.getDocumentStatus(searchDocId.trim())
        setRecords(docRecords)
      } else {
        // Default simulated tracking records for demo / clean overview if search is empty
        setRecords([])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch vector cluster statistics.')
    } finally {
      setIsLoading(false)
    }
  }, [searchDocId])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleResync = async (documentId: string, versionId: string) => {
    try {
      await vectorService.syncDocument(versionId, { document_id: documentId })
      fetchData()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to resynchronize document vectors.')
    }
  }

  const handleDelete = async (documentId: string) => {
    if (!confirm(`Are you sure you want to purge all points for document ${documentId}?`)) return
    try {
      await vectorService.deleteDocumentPoints(documentId)
      fetchData()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete document points.')
    }
  }

  return (
    <PageTransition className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-6">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-primary-subtle flex items-center justify-center text-primary">
            <Database className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
              Vector Storage Foundation
            </h1>
            <p className="text-sm text-muted-foreground">
              Qdrant Payload Filter Indexing & HNSW Quantization
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchData}
            disabled={isLoading}
            className="flex items-center gap-1.5"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh Cluster</span>
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-danger/20 bg-danger-subtle p-4 text-xs text-danger font-medium">
          <strong>Cluster Communication Error:</strong> {error}
        </div>
      )}

      {/* Cluster Summary Banner */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="rounded-xl border border-border bg-surface p-4 flex items-center gap-3.5 shadow-sm">
          <div className="w-10 h-10 rounded-lg bg-success-subtle flex items-center justify-center text-success">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block">
              Qdrant Status
            </span>
            <span className="text-lg font-bold text-foreground mt-0.5 block">
              {health ? health.status : 'CHECKING...'}
            </span>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-surface p-4 flex items-center gap-3.5 shadow-sm">
          <div className="w-10 h-10 rounded-lg bg-primary-subtle flex items-center justify-center text-primary">
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

        <div className="rounded-xl border border-border bg-surface p-4 flex items-center gap-3.5 shadow-sm">
          <div className="w-10 h-10 rounded-lg bg-info-subtle flex items-center justify-center text-info">
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

        <div className="rounded-xl border border-border bg-surface p-4 flex items-center gap-3.5 shadow-sm">
          <div className="w-10 h-10 rounded-lg bg-warning-subtle flex items-center justify-center text-warning">
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
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
            <Layers className="w-4 h-4 text-primary" />
            Active Tenant Vector Collections
          </h2>
          <span className="text-xs text-muted-foreground">
            Strict payload indexing enforced (`tenant_id`, `document_id`)
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {health && health.collections.length > 0 ? (
            health.collections.map((col) => (
              <CollectionHealthCard key={col.collection_name} collection={col} status={health.status} />
            ))
          ) : (
            <div className="col-span-3 rounded-xl border border-border border-dashed bg-surface/50 p-8 text-center text-muted-foreground text-xs font-medium">
              No active collections instantiated yet. Collections are auto-created on first document ingestion.
            </div>
          )}
        </div>
      </div>

      {/* Index Synchronization State Table */}
      <div className="space-y-4 pt-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
              <Database className="w-4 h-4 text-primary" />
              Document Version Synchronization Tracking
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Inspect or resynchronize staged points across Qdrant namespaces
            </p>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative w-full md:w-64">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Filter by Document UUID..."
                value={searchDocId}
                onChange={(e) => setSearchDocId(e.target.value)}
                className="w-full rounded-lg border border-border bg-background pl-9 pr-3 py-1.5 text-xs text-foreground placeholder-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary shadow-sm"
              />
            </div>
          </div>
        </div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <IndexSyncTable
            records={records}
            isLoading={isLoading}
            onResync={handleResync}
            onDelete={handleDelete}
          />
        </motion.div>
      </div>
    </PageTransition>
  )
}
