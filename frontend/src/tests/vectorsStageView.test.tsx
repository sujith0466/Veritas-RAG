import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { VectorsStageView } from '../pages/vectors/components/VectorsStageView'
import { vectorService } from '@/services/vectorService'
import { documentService } from '@/services/documentService'

vi.mock('@/services/vectorService', () => ({
  vectorService: {
    getHealth: vi.fn(),
    listCollections: vi.fn(),
    getDocumentStatus: vi.fn(),
    syncDocument: vi.fn(),
    deleteDocumentPoints: vi.fn(),
  },
}))

vi.mock('@/services/documentService', () => ({
  documentService: {
    listDocuments: vi.fn(),
  },
}))

vi.mock('@/components/common', async () => {
  const actual = await vi.importActual<any>('@/components/common')
  return {
    ...actual,
    Dialog: ({ children, open }: any) => (open ? <div data-testid="dialog-root">{children}</div> : null),
    DialogContent: ({ children }: any) => <div data-testid="dialog-content">{children}</div>,
    DialogHeader: ({ children }: any) => <div>{children}</div>,
    DialogFooter: ({ children }: any) => <div>{children}</div>,
    DialogTitle: ({ children }: any) => <h2>{children}</h2>,
    DialogDescription: ({ children }: any) => <p>{children}</p>,
  }
})

describe('VectorsStageView Component (UNIT-KP-05)', () => {
  const mockHealth = {
    status: 'ONLINE',
    active_collections_count: 1,
    total_points_stored: 25400,
    collections: [
      {
        collection_name: 'raguard_knowledge_test_tenant',
        total_points: 25400,
        indexed_versions_count: 4,
      },
    ],
  }

  const mockDocuments = {
    items: [
      {
        id: 'doc-ready-1',
        filename: 'security_handbook.pdf',
        original_filename: 'security_handbook.pdf',
        status: 'READY',
        word_count: 5000,
        page_count: 12,
        latest_version_id: 'ver-ready-1',
      },
      {
        id: 'doc-embedded-2',
        filename: 'api_spec.pdf',
        original_filename: 'api_spec.pdf',
        status: 'EMBEDDED',
        word_count: 3200,
        page_count: 8,
        latest_version_id: 'ver-embedded-2',
      },
      {
        id: 'doc-ineligible-3',
        filename: 'corrupted_file.pdf',
        original_filename: 'corrupted_file.pdf',
        status: 'FAILED',
        word_count: 0,
        page_count: 0,
        latest_version_id: 'ver-3',
      },
    ],
    total: 3,
  }

  const mockRecords = [
    {
      id: 'meta-1',
      tenant_id: 'test-tenant',
      document_id: 'doc-ready-1',
      document_version_id: 'ver-ready-1',
      collection_name: 'raguard_knowledge_test_tenant',
      points_count: 50,
      status: 'COMPLETED',
      sync_status: 'COMPLETED',
      last_synced_at: '2026-10-03T10:00:00Z',
      error_message: null,
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(vectorService.getHealth).mockResolvedValue(mockHealth as any)
    vi.mocked(documentService.listDocuments).mockResolvedValue(mockDocuments as any)
    vi.mocked(vectorService.getDocumentStatus).mockResolvedValue(mockRecords as any)
  })

  it('renders stage header, cluster KPIs, collection cards, and records table', async () => {
    render(<VectorsStageView />)

    expect(screen.getByText('Stage 3: Vector Storage Foundation (Qdrant)')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getAllByText('ONLINE').length).toBeGreaterThan(0)
      expect(screen.getAllByText('25,400').length).toBeGreaterThan(0)
      expect(screen.getAllByText('raguard_knowledge_test_tenant').length).toBeGreaterThan(0)
      expect(screen.getByText('Document Version Synchronization Tracking')).toBeInTheDocument()
    })
  })

  it('filters documents by eligibility including READY and EMBEDDED while excluding FAILED', async () => {
    render(<VectorsStageView />)

    await waitFor(() => {
      const selectElement = screen.getByLabelText(/Select Indexed Document/i) as HTMLSelectElement
      expect(selectElement).toBeInTheDocument()

      const options = Array.from(selectElement.options).map((opt) => opt.text)
      expect(options.some((t) => t.includes('security_handbook.pdf'))).toBe(true)
      expect(options.some((t) => t.includes('api_spec.pdf'))).toBe(true)
      expect(options.some((t) => t.includes('corrupted_file.pdf'))).toBe(false)
    })
  })

  it('queries vector status when a document is selected', async () => {
    render(<VectorsStageView />)

    await waitFor(() => {
      expect(vectorService.getDocumentStatus).toHaveBeenCalledWith('doc-ready-1')
      expect(screen.getByText('50')).toBeInTheDocument()
    })

    const selectElement = screen.getByLabelText(/Select Indexed Document/i)
    fireEvent.change(selectElement, { target: { value: 'doc-embedded-2' } })

    await waitFor(() => {
      expect(vectorService.getDocumentStatus).toHaveBeenCalledWith('doc-embedded-2')
    })
  })

  it('triggers vector synchronization when Sync Vector Points CTA is clicked', async () => {
    vi.mocked(vectorService.syncDocument).mockResolvedValue({
      id: 'meta-new',
      sync_status: 'PENDING',
    } as any)

    render(<VectorsStageView />)

    await waitFor(() => {
      expect(screen.getByText('Sync Vector Points')).toBeInTheDocument()
    })

    const syncBtn = screen.getByText('Sync Vector Points')
    fireEvent.click(syncBtn)

    await waitFor(() => {
      expect(vectorService.syncDocument).toHaveBeenCalledWith('ver-ready-1', {
        document_id: 'doc-ready-1',
      })
    })
  })

  it('displays isolated stage error when cluster health fails and allows retry', async () => {
    vi.mocked(vectorService.getHealth).mockRejectedValueOnce(new Error('Qdrant connection refused'))

    render(<VectorsStageView />)

    await waitFor(() => {
      expect(screen.getByText(/Qdrant connection refused/i)).toBeInTheDocument()
      expect(screen.getByText('Retry')).toBeInTheDocument()
    })

    vi.mocked(vectorService.getHealth).mockResolvedValue(mockHealth as any)
    const retryBtn = screen.getByText('Retry')
    fireEvent.click(retryBtn)

    await waitFor(() => {
      expect(screen.queryByText(/Qdrant connection refused/i)).not.toBeInTheDocument()
      expect(screen.getAllByText('ONLINE').length).toBeGreaterThan(0)
    })
  })

  it('renders empty states cleanly when no collections or records exist', async () => {
    vi.mocked(vectorService.getHealth).mockResolvedValue({
      status: 'ONLINE',
      active_collections_count: 0,
      total_points_stored: 0,
      collections: [],
    } as any)
    vi.mocked(documentService.listDocuments).mockResolvedValue({
      items: [],
      total: 0,
    } as any)
    vi.mocked(vectorService.getDocumentStatus).mockResolvedValue([] as any)

    render(<VectorsStageView />)

    await waitFor(() => {
      expect(
        screen.getByText(/No active collections instantiated yet/i)
      ).toBeInTheDocument()
      expect(
        screen.getByText(/No Vector Index Records Found/i)
      ).toBeInTheDocument()
    })
  })
})
