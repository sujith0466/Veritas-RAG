import * as React from 'react'
import { RefreshCw } from 'lucide-react'
import { Button, PageHeader } from '@/components/common'
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
} from './components'

export function ChunksPage() {
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

  // Detail drawer
  const [selectedChunkDetail, setSelectedChunkDetail] = React.useState<ChunkDetailResponse | null>(null)
  const [isDrawerOpen, setIsDrawerOpen] = React.useState<boolean>(false)

  const fetchInitialData = React.useCallback(async () => {
    try {
      const [stratList, docList, metricsSummary] = await Promise.all([
        chunkService.listStrategies(),
        documentService.listDocuments(1, 100, 'PROCESSED'),
        chunkService.getMetrics(),
      ])
      setStrategies(stratList || [])
      setDocuments(docList.items || [])
      setMetrics(metricsSummary)

      // Auto-select first document if available and not set
      if (docList.items && docList.items.length > 0 && !selectedDocId) {
        setSelectedDocId(docList.items[0].id)
      }
    } catch (err) {
      console.error('Failed to load chunking foundation initial data:', err)
    } finally {
      setIsLoadingInitial(false)
    }
  }, [selectedDocId])

  const fetchChunksForDoc = React.useCallback(async (docId: string, pageNum: number) => {
    if (!docId) return
    setIsLoadingChunks(true)
    try {
      const resp = await chunkService.listDocumentChunks(docId, pageNum, pageSize)
      setChunks(resp.items || [])
      setTotalChunks(resp.total || 0)
    } catch (err) {
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

  const handleTriggerChunking = async (docId: string, strategy: string | null, maxChars: number, overlap: number) => {
    setIsProcessing(true)
    try {
      // Execute synchronously or polling check for instant UI update demo
      await chunkService.processDocument(docId, { strategy, max_characters: maxChars, overlap_characters: overlap }, false)
      await fetchChunksForDoc(docId, 1)
      const updatedMetrics = await chunkService.getMetrics()
      setMetrics(updatedMetrics)
    } catch (err) {
      console.error('Chunking execution error:', err)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleInspectChunk = async (chunkSummary: ChunkResponse) => {
    try {
      const detail = await chunkService.getChunkDetail(chunkSummary.id)
      setSelectedChunkDetail(detail)
      setIsDrawerOpen(true)
    } catch (err) {
      console.error('Failed to inspect chunk:', err)
    }
  }

  const handleNavigateToChunkId = async (id: string) => {
    try {
      const detail = await chunkService.getChunkDetail(id)
      setSelectedChunkDetail(detail)
    } catch (err) {
      console.error('Failed to navigate to neighbor chunk:', err)
    }
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <PageHeader
        title="Knowledge Layer: Chunking Foundation"
        description="Transform normalized document text into structured, doubly-linked, and validated chunks with zero embedding leakage (`Phase 2 Milestone 1`)."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              fetchInitialData()
              if (selectedDocId) fetchChunksForDoc(selectedDocId, page)
            }}
            className="gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh Data
          </Button>
        }
      />

      <ChunkMetricsCard metrics={metrics} isLoading={isLoadingInitial} />

      <ChunkStrategySelector
        strategies={strategies}
        documents={documents}
        selectedDocId={selectedDocId}
        onSelectDocId={setSelectedDocId}
        onTriggerChunking={handleTriggerChunking}
        isProcessing={isProcessing}
      />

      <div className="mt-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-slate-100">Doubly-Linked Chunk Registry</h3>
            <p className="text-xs text-slate-400">Inspecting chunks for sequence index, breadcrumb headers, and doubly-linked graph continuity (`prev` ↔ `next`)</p>
          </div>
          <div className="text-xs font-mono bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg text-indigo-400">
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

      <ChunkDetailDrawer
        chunk={selectedChunkDetail}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onNavigateToChunkId={handleNavigateToChunkId}
      />
    </div>
  )
}
