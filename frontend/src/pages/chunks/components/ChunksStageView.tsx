import * as React from 'react'
import { RefreshCw, AlertCircle } from 'lucide-react'
import { Button } from '@/components/common'
import { chunkService } from '@/services/chunkService'
import { documentService } from '@/services/documentService'
import type {
  ChunkDetailResponse,
  ChunkMetricsDTO,
  ChunkResponse,
  DocumentResponse,
  StrategyInfoDTO,
} from '@/types'
import {
  ChunkDetailDrawer,
  ChunkListTable,
  ChunkMetricsCard,
  ChunkStrategySelector,
} from './index'

/**
 * Valid document statuses eligible for chunking or chunk inspection.
 * Includes READY (steady-state ingested documents) and PROCESSED (manifest generated, awaiting chunking).
 */
const ELIGIBLE_DOCUMENT_STATUSES = new Set([
  'READY',
  'PROCESSED',
  'CHUNKED',
  'EMBEDDING',
  'EMBEDDED',
  'VECTOR_SYNC',
])

export function ChunksStageView() {
  const [strategies, setStrategies] = React.useState<StrategyInfoDTO[]>([])
  const [documents, setDocuments] = React.useState<DocumentResponse[]>([])
  const [metrics, setMetrics] = React.useState<ChunkMetricsDTO | null>(null)

  // Selection & filter state
  const [selectedDocId, setSelectedDocId] = React.useState<string>('')
  const [chunks, setChunks] = React.useState<ChunkResponse[]>([])
  const [totalChunks, setTotalChunks] = React.useState<number>(0)
  const [page, setPage] = React.useState<number>(1)
  const pageSize = 50

  const [isLoadingInitial, setIsLoadingInitial] = React.useState<boolean>(true)
  const [isProcessing, setIsProcessing] = React.useState<boolean>(false)
  const [isLoadingChunks, setIsLoadingChunks] = React.useState<boolean>(false)
  const [stageError, setStageError] = React.useState<string | null>(null)

  // Detail drawer
  const [selectedChunkDetail, setSelectedChunkDetail] = React.useState<ChunkDetailResponse | null>(null)
  const [isDrawerOpen, setIsDrawerOpen] = React.useState<boolean>(false)

  const fetchInitialData = React.useCallback(async () => {
    setIsLoadingInitial(true)
    setStageError(null)
    try {
      const [stratList, docList, metricsSummary] = await Promise.all([
        chunkService.listStrategies().catch((err) => {
          console.error('Failed to load strategies:', err)
          return null
        }),
        // Fetch without status filter so backend returns all active documents,
        // allowing client-side inclusion of both READY and PROCESSED documents.
        documentService.listDocuments(1, 100).catch((err) => {
          console.error('Failed to load documents:', err)
          return { items: [], total: 0, page: 1, page_size: 100, pages: 1 }
        }),
        chunkService.getMetrics().catch((err) => {
          console.error('Failed to load chunk metrics:', err)
          return null
        }),
      ])

      const allStrategies = stratList
        ? [
            ...(stratList.supported || []),
            ...(stratList.experimental || []),
            ...(stratList.disabled || []),
          ]
        : []
      setStrategies(allStrategies)

      // Filter documents to those with extracted text eligible for chunking or chunk viewing
      const rawDocs = docList.items || []
      const eligibleDocs = rawDocs.filter((d) =>
        ELIGIBLE_DOCUMENT_STATUSES.has(d.status?.toUpperCase() || '')
      )
      setDocuments(eligibleDocs)
      setMetrics(metricsSummary)

      // Auto-select first document if available and current selection is empty or invalid
      if (eligibleDocs.length > 0) {
        setSelectedDocId((prev) => {
          const exists = eligibleDocs.some((d) => d.id === prev)
          return exists ? prev : eligibleDocs[0].id
        })
      }
    } catch (err: any) {
      console.error('Failed to load chunking foundation initial data:', err)
      setStageError(err?.message || 'Unable to load chunking workspace data.')
    } finally {
      setIsLoadingInitial(false)
    }
  }, [])

  const fetchChunksForDoc = React.useCallback(async (docId: string, pageNum: number) => {
    if (!docId) return
    setIsLoadingChunks(true)
    try {
      const resp = await chunkService.listDocumentChunks(docId, pageNum, pageSize)
      setChunks(resp.items || [])
      setTotalChunks(resp.total || 0)
    } catch (err: any) {
      console.error('Failed to fetch chunks for document:', err)
      setChunks([])
      setTotalChunks(0)
    } finally {
      setIsLoadingChunks(false)
    }
  }, [])

  React.useEffect(() => {
    fetchInitialData()
  }, [fetchInitialData])

  React.useEffect(() => {
    if (selectedDocId) {
      setPage(1)
      fetchChunksForDoc(selectedDocId, 1)
    } else {
      setChunks([])
      setTotalChunks(0)
    }
  }, [selectedDocId, fetchChunksForDoc])

  const handleTriggerChunking = async (
    docId: string,
    strategy: string | null,
    maxChars: number,
    overlap: number
  ) => {
    setIsProcessing(true)
    setStageError(null)
    try {
      await chunkService.processDocument(
        docId,
        { strategy, max_characters: maxChars, overlap_characters: overlap },
        false
      )
      await fetchChunksForDoc(docId, 1)
      const updatedMetrics = await chunkService.getMetrics()
      setMetrics(updatedMetrics)
    } catch (err: any) {
      console.error('Chunking execution error:', err)
      setStageError(err?.message || 'Chunking process failed. Please check the document format.')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleInspectChunk = async (chunkSummary: ChunkResponse) => {
    try {
      const detail = await chunkService.getChunkDetail(chunkSummary.id)
      setSelectedChunkDetail(detail)
      setIsDrawerOpen(true)
    } catch (err: any) {
      console.error('Failed to inspect chunk:', err)
    }
  }

  const handleNavigateToChunkId = async (id: string) => {
    try {
      const detail = await chunkService.getChunkDetail(id)
      setSelectedChunkDetail(detail)
    } catch (err: any) {
      console.error('Failed to navigate to neighbor chunk:', err)
    }
  }

  return (
    <div className="space-y-6">
      {/* Stage Action Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-2 border-b border-border/60">
        <div>
          <h2 className="text-base font-bold text-foreground">
            Stage 1: Document Chunking Foundation
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Transform normalized text into structured, doubly-linked chunks with verified sequence integrity.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            fetchInitialData()
            if (selectedDocId) fetchChunksForDoc(selectedDocId, page)
          }}
          disabled={isLoadingInitial || isLoadingChunks}
          className="gap-2 shrink-0"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoadingInitial ? 'animate-spin' : ''}`} />
          Refresh Stage
        </Button>
      </div>

      {/* Stage-Level Error Alert (Isolated) */}
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

      {/* Chunk Metrics */}
      <ChunkMetricsCard metrics={metrics} isLoading={isLoadingInitial} />

      {/* Strategy Selector & Execution */}
      <ChunkStrategySelector
        strategies={strategies}
        documents={documents}
        selectedDocId={selectedDocId}
        onSelectDocId={setSelectedDocId}
        onTriggerChunking={handleTriggerChunking}
        isProcessing={isProcessing}
      />

      {/* Doubly-Linked Registry Table */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-foreground">
              Doubly-Linked Chunk Registry
            </h3>
            <p className="text-xs text-muted-foreground">
              Inspecting chunks for sequence index, breadcrumb headers, and graph continuity (`prev` ↔ `next`)
            </p>
          </div>
          <div className="text-xs font-mono bg-surface border border-border px-3 py-1.5 rounded-lg text-primary self-start sm:self-auto">
            Active Document: {selectedDocId || 'None Selected'}
          </div>
        </div>

        <ChunkListTable
          chunks={chunks}
          total={totalChunks}
          page={page}
          size={pageSize}
          onPageChange={(p) => {
            setPage(p)
            fetchChunksForDoc(selectedDocId, p)
          }}
          onSelectChunk={handleInspectChunk}
          isLoading={isLoadingChunks}
        />
      </div>

      {/* Detail Drawer */}
      <ChunkDetailDrawer
        chunk={selectedChunkDetail}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onNavigateToChunkId={handleNavigateToChunkId}
      />
    </div>
  )
}
