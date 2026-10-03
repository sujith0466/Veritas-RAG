import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { PipelineVisualizer } from '../pages/knowledge-processing/components/PipelineVisualizer'
import { documentService } from '@/services/documentService'

vi.mock('@/services/documentService', () => ({
  documentService: {
    listDocuments: vi.fn(),
  },
}))

describe('PipelineVisualizer Component (UNIT-KP-06)', () => {
  const mockDocuments = {
    items: [
      {
        id: 'doc-ready-1',
        filename: 'architecture_guide.pdf',
        original_filename: 'architecture_guide.pdf',
        status: 'READY',
        word_count: 7500,
        page_count: 14,
        latest_version_id: 'ver-ready-100',
      },
      {
        id: 'doc-failed-2',
        filename: 'malformed_file.pdf',
        original_filename: 'malformed_file.pdf',
        status: 'FAILED',
        word_count: 0,
        page_count: 0,
        latest_version_id: 'ver-failed-200',
      },
    ],
    total: 2,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(documentService.listDocuments).mockResolvedValue(mockDocuments as any)
  })

  it('renders all 5 deterministic pipeline entities', async () => {
    render(<PipelineVisualizer />)

    expect(screen.getByText('Pipeline Architecture Visualizer')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Document')).toBeInTheDocument()
      expect(screen.getByText('Document Version')).toBeInTheDocument()
      expect(screen.getByText('Chunk')).toBeInTheDocument()
      expect(screen.getByText('Embedding')).toBeInTheDocument()
      expect(screen.getByText('Qdrant Point')).toBeInTheDocument()
    })
  })

  it('reflects selected document metadata truthfully without fabricated telemetry', async () => {
    render(<PipelineVisualizer />)

    await waitFor(() => {
      expect(screen.getByText('architecture_guide.pdf')).toBeInTheDocument()
      expect(screen.getByText('14 pages')).toBeInTheDocument()
      expect(screen.getByText('7,500 words')).toBeInTheDocument()
      expect(screen.getByText(/SHA-256 Content Hash Verified/i)).toBeInTheDocument()
      expect(screen.getByText(/3072d \(OpenAI\) \/ 1024d \(Cohere\)/i)).toBeInTheDocument()
      expect(screen.getByText(/INT8 Scalar Quantization/i)).toBeInTheDocument()
    })
  })

  it('honestly represents failed documents by marking downstream stages halted', async () => {
    render(<PipelineVisualizer />)

    await waitFor(() => {
      expect(screen.getByText('architecture_guide.pdf')).toBeInTheDocument()
    })

    const select = screen.getByLabelText(/Inspect Document:/i) as HTMLSelectElement
    fireEvent.change(select, { target: { value: 'doc-failed-2' } })

    await waitFor(() => {
      expect(screen.getByText('malformed_file.pdf')).toBeInTheDocument()
      const haltedBadges = screen.getAllByText('Halted')
      expect(haltedBadges.length).toBeGreaterThanOrEqual(1)
    })
  })

  it('calls onSelectStage when stage inspect buttons are clicked or activated via keyboard', async () => {
    const handleSelectStage = vi.fn()
    render(<PipelineVisualizer onSelectStage={handleSelectStage} />)

    await waitFor(() => {
      expect(screen.getByLabelText('Navigate to Chunk workspace')).toBeInTheDocument()
    })

    // Click chunk card
    const chunkCard = screen.getByLabelText('Navigate to Chunk workspace')
    fireEvent.click(chunkCard)
    expect(handleSelectStage).toHaveBeenCalledWith('chunks')

    // Keyboard activate embedding card
    const embeddingCard = screen.getByLabelText('Navigate to Embedding workspace')
    fireEvent.keyDown(embeddingCard, { key: 'Enter' })
    expect(handleSelectStage).toHaveBeenCalledWith('embeddings')

    // Click vectors card
    const vectorCard = screen.getByLabelText('Navigate to Qdrant Point workspace')
    fireEvent.click(vectorCard)
    expect(handleSelectStage).toHaveBeenCalledWith('vectors')
  })

  it('renders structural schema model cleanly when document list is empty', async () => {
    vi.mocked(documentService.listDocuments).mockResolvedValue({ items: [], total: 0 } as any)
    render(<PipelineVisualizer />)

    await waitFor(() => {
      expect(screen.getByText(/No documents found/i)).toBeInTheDocument()
      expect(screen.getAllByText(/Schema Model/i).length).toBeGreaterThanOrEqual(1)
    })
  })
})
