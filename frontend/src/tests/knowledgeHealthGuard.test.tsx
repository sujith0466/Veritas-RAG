import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { DestructivePurgeModal } from '../components/knowledge/DestructivePurgeModal'
import { KnowledgeHealthPanel } from '../components/knowledge/KnowledgeHealthPanel'
import { documentService } from '../services/documentService'
import { useKnowledgeHealthStore } from '../stores/knowledgeHealthStore'

vi.mock('@/services/documentService', () => ({
  documentService: {
    getDocumentDetail: vi.fn(),
  },
}))

describe('DestructivePurgeModal (UNIT-OPS-04 Preflight & Confirmation Guard)', () => {
  const mockDocId = 'doc-test-1234'

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('performs preflight check and displays document title and verified status', async () => {
    vi.mocked(documentService.getDocumentDetail).mockResolvedValueOnce({
      id: mockDocId,
      workspace_id: 'ws-1',
      original_filename: 'Enterprise Architecture Spec.pdf',
      filename: 'architecture.pdf',
      status: 'READY',
      source_type: 'FILE_UPLOAD',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      versions: [],
    } as any)

    render(
      <DestructivePurgeModal
        isOpen={true}
        onClose={vi.fn()}
        documentId={mockDocId}
      />
    )

    expect(screen.getByText('Preflight Destruction Guard')).toBeInTheDocument()
    expect(screen.getByText(mockDocId)).toBeInTheDocument()

    await waitFor(() => {
      expect(documentService.getDocumentDetail).toHaveBeenCalledWith(mockDocId)
      expect(screen.getByText('Enterprise Architecture Spec.pdf')).toBeInTheDocument()
      expect(screen.getByText('Verified in DB')).toBeInTheDocument()
    })
  })

  it('keeps purge button disabled until user explicitly types PURGE', async () => {
    vi.mocked(documentService.getDocumentDetail).mockResolvedValueOnce({
      id: mockDocId,
      title: 'Confidential HR Guide',
      status: 'READY',
    } as any)

    render(
      <DestructivePurgeModal
        isOpen={true}
        onClose={vi.fn()}
        documentId={mockDocId}
      />
    )

    const purgeButton = screen.getByRole('button', { name: /Execute Purge/i })
    expect(purgeButton).toBeDisabled()

    const confirmInput = screen.getByPlaceholderText('PURGE')

    // Typing lowercase 'purge' keeps it disabled
    fireEvent.change(confirmInput, { target: { value: 'purge' } })
    expect(purgeButton).toBeDisabled()

    // Typing partial 'PUR' keeps it disabled
    fireEvent.change(confirmInput, { target: { value: 'PUR' } })
    expect(purgeButton).toBeDisabled()

    // Typing exact 'PURGE' enables it
    fireEvent.change(confirmInput, { target: { value: 'PURGE' } })
    expect(purgeButton).not.toBeDisabled()
  })

  it('executes purge and displays success telemetry', async () => {
    vi.mocked(documentService.getDocumentDetail).mockResolvedValueOnce({
      id: mockDocId,
      title: 'Target File',
      status: 'READY',
    } as any)

    // Mock store purgeDocument
    const purgeSpy = vi.fn().mockResolvedValueOnce({
      document_id: mockDocId,
      qdrant_points_deleted: 42,
      pg_chunks_deleted: 42,
      duration_ms: 18.5,
    })

    useKnowledgeHealthStore.setState({
      purgeDocument: purgeSpy,
    })

    render(
      <DestructivePurgeModal
        isOpen={true}
        onClose={vi.fn()}
        documentId={mockDocId}
      />
    )

    const confirmInput = screen.getByPlaceholderText('PURGE')
    fireEvent.change(confirmInput, { target: { value: 'PURGE' } })

    const purgeButton = screen.getByRole('button', { name: /Execute Purge/i })
    fireEvent.click(purgeButton)

    await waitFor(() => {
      expect(purgeSpy).toHaveBeenCalledWith(mockDocId)
      expect(screen.getByText('Purge Executed Successfully')).toBeInTheDocument()
      expect(screen.getByText('42 purged')).toBeInTheDocument()
      expect(screen.getByText('42 removed')).toBeInTheDocument()
      expect(screen.getByText('18.5 ms')).toBeInTheDocument()
    })
  })
})

describe('KnowledgeHealthPanel (OPS-04 Consolidation)', () => {
  it('renders Real-Time Parity Audit and triggers purge modal', async () => {
    vi.mocked(documentService.getDocumentDetail).mockResolvedValue({
      id: 'doc-target-99',
      title: 'Target 99 Doc',
      status: 'READY',
    } as any)

    useKnowledgeHealthStore.setState({
      isLoading: false,
      isScanning: false,
      error: null,
      fetchParity: vi.fn(),
      fetchScanHistory: vi.fn(),
    })

    render(<KnowledgeHealthPanel />)

    expect(screen.getByText('Real-Time 1:1 Parity Audit')).toBeInTheDocument()
    expect(screen.getByText(/Two-Phase Document Purge/i)).toBeInTheDocument()

    const docInput = screen.getByLabelText(/Document UUID/i)
    fireEvent.change(docInput, { target: { value: 'doc-target-99' } })

    const purgeSubmitBtn = screen.getByRole('button', { name: /Execute Two-Phase Hard Purge/i })
    expect(purgeSubmitBtn).not.toBeDisabled()
    fireEvent.click(purgeSubmitBtn)

    await waitFor(() => {
      expect(screen.getByText('Preflight Destruction Guard')).toBeInTheDocument()
      expect(screen.getByText('doc-target-99')).toBeInTheDocument()
    })
  })
})
