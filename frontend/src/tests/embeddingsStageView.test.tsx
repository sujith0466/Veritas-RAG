import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { EmbeddingsStageView } from '../pages/embeddings/components/EmbeddingsStageView'
import { embeddingService } from '@/services/embeddingService'
import { documentService } from '@/services/documentService'

vi.mock('@/services/embeddingService', () => ({
  embeddingService: {
    listProviders: vi.fn(),
    getMetrics: vi.fn(),
    listJobs: vi.fn(),
    createJob: vi.fn(),
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

describe('EmbeddingsStageView Component (UNIT-KP-04)', () => {
  const mockProviders = [
    {
      provider: 'openai',
      display_name: 'OpenAI Embeddings',
      description: 'Standard text embedding models by OpenAI',
      is_available: true,
      models: [
        {
          model_name: 'text-embedding-3-large',
          dimension: 3072,
          max_input_tokens: 8191,
          is_default: true,
        },
      ],
    },
    {
      provider: 'cohere',
      display_name: 'Cohere Embed',
      description: 'Multilingual and English dense embedding models',
      is_available: false,
      models: [
        {
          model_name: 'embed-english-v3.0',
          dimension: 1024,
          max_input_tokens: 512,
          is_default: true,
        },
      ],
    },
  ]

  const mockMetrics = {
    total_vectors_stored: 15420,
    active_jobs_count: 1,
    completed_jobs_count: 38,
    failed_jobs_count: 0,
    total_tokens_consumed: 350000,
    monthly_token_quota: 1000000,
    remaining_tokens: 650000,
    provider_breakdown: { openai: 38 },
  }

  const mockDocuments = {
    items: [
      {
        id: 'doc-ready-1',
        filename: 'handbook.pdf',
        original_filename: 'handbook.pdf',
        status: 'READY',
        word_count: 5000,
        page_count: 12,
        latest_version_id: 'ver-1',
        created_at: '2026-10-01T00:00:00Z',
      },
      {
        id: 'doc-processed-2',
        filename: 'spec.md',
        original_filename: 'spec.md',
        status: 'PROCESSED',
        word_count: 3200,
        page_count: 4,
        latest_version_id: 'ver-2',
        created_at: '2026-10-02T00:00:00Z',
      },
      {
        id: 'doc-extracting-3',
        filename: 'draft.docx',
        original_filename: 'draft.docx',
        status: 'EXTRACTING',
        word_count: 0,
        page_count: 0,
        latest_version_id: 'ver-3',
        created_at: '2026-10-03T00:00:00Z',
      },
    ],
    total: 3,
    page: 1,
    page_size: 100,
    pages: 1,
  }

  const mockJobs = {
    items: [
      {
        job_id: 'job-pending-1',
        tenant_id: 'tenant-1',
        document_id: 'doc-ready-1',
        document_version_id: 'ver-1',
        provider: 'openai',
        model_name: 'text-embedding-3-large',
        total_chunks: 50,
        processed_chunks: 25,
        failed_chunks: 0,
        total_tokens_consumed: 12500,
        progress_percentage: 50.0,
        status: 'PROCESSING',
        created_at: '2026-10-03T08:00:00Z',
        completed_at: null,
        error_message: null,
      },
    ],
    total: 1,
    page: 1,
    size: 20,
    pages: 1,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(embeddingService.listProviders).mockResolvedValue(mockProviders as any)
    vi.mocked(embeddingService.getMetrics).mockResolvedValue(mockMetrics as any)
    vi.mocked(documentService.listDocuments).mockResolvedValue(mockDocuments as any)
    vi.mocked(embeddingService.listJobs).mockResolvedValue(mockJobs as any)
  })

  it('renders stage header, registered engines, token telemetry, and jobs table', async () => {
    render(<EmbeddingsStageView />)

    expect(screen.getByText('Stage 2: Vector Embeddings & Token Budget')).toBeInTheDocument()
    expect(screen.getByText(/Manage semantic embedding models, monitor token budget consumption/i)).toBeInTheDocument()

    await waitFor(() => {
      // Providers
      expect(screen.getByText('OpenAI Embeddings')).toBeInTheDocument()
      expect(screen.getByText('Cohere Embed')).toBeInTheDocument()
      expect(screen.getByText('1 of 2 engines online')).toBeInTheDocument()

      // Telemetry
      expect(screen.getByText('Token Quota')).toBeInTheDocument()
      expect(screen.getByText('Vectors Generated')).toBeInTheDocument()
      expect(screen.getByText('15,420')).toBeInTheDocument()

      // Table & Jobs
      expect(screen.getByText('Embedding Pipeline Jobs')).toBeInTheDocument()
      expect(screen.getByText('50.0%')).toBeInTheDocument()
      expect(screen.getByText('25 / 50 chunks')).toBeInTheDocument()
    })
  })

  it('filters documents to include READY and PROCESSED and excludes non-extracted statuses in new job dialog', async () => {
    render(<EmbeddingsStageView />)

    await waitFor(() => {
      expect(screen.getByText('New Embedding Job')).toBeInTheDocument()
      expect(documentService.listDocuments).toHaveBeenCalled()
      expect(screen.getByText('OpenAI Embeddings')).toBeInTheDocument()
    })

    const openModalBtn = screen.getByText('New Embedding Job')
    fireEvent.click(openModalBtn)

    await waitFor(() => {
      expect(screen.getByText(/Initiate Batch Embedding Job/i)).toBeInTheDocument()
      expect(screen.getByDisplayValue(/handbook\.pdf/i)).toBeInTheDocument()
      expect(screen.getByRole('option', { name: /spec\.md/i })).toBeInTheDocument()
      expect(screen.queryByRole('option', { name: /draft\.docx/i })).not.toBeInTheDocument()
    })
  })

  it('preserves 3-second active-job polling when jobs are in progress', async () => {
    const setIntervalSpy = vi.spyOn(window, 'setInterval')

    render(<EmbeddingsStageView />)

    await waitFor(() => {
      expect(screen.getByText('Embedding Pipeline Jobs')).toBeInTheDocument()
      expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 3000)
    })
  })

  it('initiates a new batch embedding job with configured options', async () => {
    vi.mocked(embeddingService.createJob).mockResolvedValue({
      job_id: 'new-job-1',
      status: 'PENDING',
    } as any)

    render(<EmbeddingsStageView />)

    await waitFor(() => {
      expect(screen.getByText('New Embedding Job')).toBeInTheDocument()
    })

    const openModalBtn = screen.getByText('New Embedding Job')
    fireEvent.click(openModalBtn)

    await waitFor(() => {
      expect(screen.getByText(/Initiate Batch Embedding Job/i)).toBeInTheDocument()
      expect(screen.getByText('Start Vectorization')).toBeInTheDocument()
    })

    const submitBtn = screen.getByText('Start Vectorization')
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(embeddingService.createJob).toHaveBeenCalledWith(
        expect.objectContaining({
          document_id: 'doc-ready-1',
          document_version_id: 'ver-1',
          provider: 'openai',
          model_name: 'text-embedding-3-large',
          batch_size: 100,
          force_reembed: false,
        })
      )
    })
  })

  it('displays isolated stage error and allows retry when initial loading fails', async () => {
    vi.mocked(embeddingService.listProviders).mockRejectedValueOnce(new Error('Network gateway timeout'))

    render(<EmbeddingsStageView />)

    await waitFor(() => {
      expect(screen.getByText('Network gateway timeout')).toBeInTheDocument()
      expect(screen.getByText('Retry')).toBeInTheDocument()
    })

    // Click retry
    vi.mocked(embeddingService.listProviders).mockResolvedValueOnce(mockProviders as any)
    const retryBtn = screen.getByText('Retry')
    fireEvent.click(retryBtn)

    await waitFor(() => {
      expect(screen.queryByText('Network gateway timeout')).not.toBeInTheDocument()
      expect(screen.getByText('OpenAI Embeddings')).toBeInTheDocument()
    })
  })
})
