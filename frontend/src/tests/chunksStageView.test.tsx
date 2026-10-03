import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { ChunksStageView } from '../pages/chunks/components/ChunksStageView'
import { chunkService } from '@/services/chunkService'
import { documentService } from '@/services/documentService'

vi.mock('@/services/chunkService', () => ({
  chunkService: {
    listStrategies: vi.fn(),
    getMetrics: vi.fn(),
    listDocumentChunks: vi.fn(),
    processDocument: vi.fn(),
    getChunkDetail: vi.fn(),
  },
}))

vi.mock('@/services/documentService', () => ({
  documentService: {
    listDocuments: vi.fn(),
  },
}))

describe('ChunksStageView Component (UNIT-KP-03)', () => {
  const mockStrategies = {
    supported: [
      {
        id: 'recursive',
        name: 'Recursive Text Splitter',
        description: 'Standard recursive splitting on paragraph and sentence boundaries',
        status: 'supported',
        default_max_characters: 1000,
        default_overlap_characters: 200,
      },
    ],
    experimental: [],
    disabled: [],
  }

  const mockDocuments = {
    items: [
      {
        id: 'doc-ready-1',
        filename: 'handbook.pdf',
        original_filename: 'handbook.pdf',
        status: 'READY',
        word_count: 5000,
        created_at: '2026-10-01T00:00:00Z',
      },
      {
        id: 'doc-processed-2',
        filename: 'spec.md',
        original_filename: 'spec.md',
        status: 'PROCESSED',
        word_count: 3200,
        created_at: '2026-10-02T00:00:00Z',
      },
      {
        id: 'doc-extracting-3',
        filename: 'draft.docx',
        original_filename: 'draft.docx',
        status: 'EXTRACTING',
        word_count: 0,
        created_at: '2026-10-03T00:00:00Z',
      },
    ],
    total: 3,
    page: 1,
    page_size: 100,
    pages: 1,
  }

  const mockMetrics = {
    total_chunks: 42,
    average_chunk_tokens: 250,
    average_chunk_characters: 1000,
    strategy_breakdown: { recursive: 42 },
    is_embedded_count: 0,
  }

  const mockChunks = {
    items: [
      {
        id: 'chunk-1',
        document_id: 'doc-ready-1',
        chunk_index: 0,
        content: 'This is the first chunk of text from the ready document.',
        strategy_used: 'recursive',
        token_count: 120,
        character_count: 480,
        section_path: ['Introduction'],
        previous_chunk_id: null,
        next_chunk_id: 'chunk-2',
      },
      {
        id: 'chunk-2',
        document_id: 'doc-ready-1',
        chunk_index: 1,
        content: 'This is the second chunk following the doubly-linked graph.',
        strategy_used: 'recursive',
        token_count: 130,
        character_count: 510,
        section_path: ['Introduction', 'Overview'],
        previous_chunk_id: 'chunk-1',
        next_chunk_id: null,
      },
    ],
    total: 2,
    page: 1,
    size: 50,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(chunkService.listStrategies).mockResolvedValue(mockStrategies as any)
    vi.mocked(documentService.listDocuments).mockResolvedValue(mockDocuments as any)
    vi.mocked(chunkService.getMetrics).mockResolvedValue(mockMetrics as any)
    vi.mocked(chunkService.listDocumentChunks).mockResolvedValue(mockChunks as any)
  })

  it('renders stage header and metrics card', async () => {
    render(<ChunksStageView />)

    expect(screen.getByText('Stage 1: Document Chunking Foundation')).toBeInTheDocument()
    expect(screen.getByText(/Transform normalized text into structured/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Total Chunks')).toBeInTheDocument()
      expect(screen.getByText('42')).toBeInTheDocument()
      expect(screen.getByText('250')).toBeInTheDocument()
    })
  })

  it('includes both READY and PROCESSED documents and filters out ineligible statuses', async () => {
    render(<ChunksStageView />)

    await waitFor(() => {
      // The selector should have options for READY and PROCESSED documents
      const readyOption = screen.getByText('handbook.pdf (READY)')
      const processedOption = screen.getByText('spec.md (PROCESSED)')
      expect(readyOption).toBeInTheDocument()
      expect(processedOption).toBeInTheDocument()

      // Ineligible document should NOT appear in options
      expect(screen.queryByText('draft.docx (EXTRACTING)')).not.toBeInTheDocument()
    })
  })

  it('auto-selects first eligible document and fetches its chunks', async () => {
    render(<ChunksStageView />)

    await waitFor(() => {
      expect(chunkService.listDocumentChunks).toHaveBeenCalledWith('doc-ready-1', 1, 50)
      expect(screen.getByText(/This is the first chunk of text/i)).toBeInTheDocument()
      expect(screen.getByText(/This is the second chunk following/i)).toBeInTheDocument()
    })
  })

  it('allows triggering chunking on the selected document', async () => {
    vi.mocked(chunkService.processDocument).mockResolvedValue({ status: 'completed' } as any)

    render(<ChunksStageView />)

    await waitFor(() => {
      expect(screen.getByText('Execute Chunking Pipeline')).toBeInTheDocument()
    })

    const executeBtn = screen.getByText('Execute Chunking Pipeline')
    fireEvent.click(executeBtn)

    await waitFor(() => {
      expect(chunkService.processDocument).toHaveBeenCalledWith(
        'doc-ready-1',
        { strategy: 'recursive', max_characters: 1000, overlap_characters: 200 },
        false
      )
    })
  })

  it('opens chunk detail drawer and displays neighbor navigation', async () => {
    const mockDetail = {
      id: 'chunk-1',
      chunk_index: 0,
      content: 'This is the first chunk of text from the ready document.',
      strategy_used: 'recursive',
      token_count: 120,
      character_count: 480,
      section_path: ['Introduction'],
      previous_chunk_id: null,
      next_chunk_id: 'chunk-2',
      content_hash: 'abc123hash',
      is_embedded: false,
      metadata_json: {},
    }
    vi.mocked(chunkService.getChunkDetail).mockResolvedValue(mockDetail as any)

    render(<ChunksStageView />)

    await waitFor(() => {
      expect(screen.getByText(/This is the first chunk of text/i)).toBeInTheDocument()
    })

    const viewButtons = screen.getAllByTitle('Inspect Chunk Details')
    fireEvent.click(viewButtons[0])

    await waitFor(() => {
      expect(chunkService.getChunkDetail).toHaveBeenCalledWith('chunk-1')
      expect(screen.getByText('Document Chunk Detail')).toBeInTheDocument()
      expect(screen.getByText('Next Chunk')).toBeInTheDocument()
    })
  })
})
