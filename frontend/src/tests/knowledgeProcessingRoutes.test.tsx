import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route, Navigate } from 'react-router-dom'
import { KnowledgeProcessingPage } from '../pages/knowledge-processing'

describe('KnowledgeProcessingPage & Routing (KP-01)', () => {
  it('renders overview stage by default when no stage param is provided', () => {
    render(
      <MemoryRouter initialEntries={['/knowledge-processing']}>
        <KnowledgeProcessingPage />
      </MemoryRouter>
    )

    expect(screen.getByRole('heading', { level: 1, name: 'Knowledge Processing' })).toBeInTheDocument()
    expect(screen.getByText('Active Stage: Overview')).toBeInTheDocument()
    expect(screen.getByText('Stage 01')).toBeInTheDocument()
    expect(screen.getByText('Stage 02')).toBeInTheDocument()
    expect(screen.getByText('Stage 03')).toBeInTheDocument()
  })

  it('renders chunks stage when ?stage=chunks is passed', () => {
    render(
      <MemoryRouter initialEntries={['/knowledge-processing?stage=chunks']}>
        <KnowledgeProcessingPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Active Stage: Chunks')).toBeInTheDocument()
    expect(screen.getByText('Stage 1: Document Chunking Foundation')).toBeInTheDocument()
  })

  it('renders embeddings stage when ?stage=embeddings is passed', () => {
    render(
      <MemoryRouter initialEntries={['/knowledge-processing?stage=embeddings']}>
        <KnowledgeProcessingPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Active Stage: Embeddings')).toBeInTheDocument()
    expect(screen.getByText('Stage 2: Vector Embeddings & Token Budget')).toBeInTheDocument()
  })

  it('renders vectors stage when ?stage=vectors is passed', () => {
    render(
      <MemoryRouter initialEntries={['/knowledge-processing?stage=vectors']}>
        <KnowledgeProcessingPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Active Stage: Vectors')).toBeInTheDocument()
    expect(screen.getByText('Stage 3: Vector Storage Foundation (Qdrant)')).toBeInTheDocument()
  })

  it('renders activity stage when ?stage=activity is passed', () => {
    render(
      <MemoryRouter initialEntries={['/knowledge-processing?stage=activity']}>
        <KnowledgeProcessingPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Active Stage: Activity')).toBeInTheDocument()
    expect(screen.getByText('Pipeline Processing Activity')).toBeInTheDocument()
  })

  it('safely falls back to overview when an unknown stage param is provided', () => {
    render(
      <MemoryRouter initialEntries={['/knowledge-processing?stage=unknown_stage']}>
        <KnowledgeProcessingPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Active Stage: Overview')).toBeInTheDocument()
    expect(screen.getByText('Unified Processing Architecture (KP-01)')).toBeInTheDocument()
  })

  it('navigates to chunks stage when clicking the Chunks tab', () => {
    render(
      <MemoryRouter initialEntries={['/knowledge-processing']}>
        <KnowledgeProcessingPage />
      </MemoryRouter>
    )

    const chunksTab = screen.getByRole('tab', { name: /Chunks/i })
    fireEvent.click(chunksTab)

    expect(screen.getByText('Active Stage: Chunks')).toBeInTheDocument()
    expect(screen.getByText('Stage 1: Document Chunking Foundation')).toBeInTheDocument()
  })

  it('correctly handles backward compatibility redirects from /chunks, /embeddings, /vectors', () => {
    const renderWithRoutes = (initialUrl: string) =>
      render(
        <MemoryRouter initialEntries={[initialUrl]}>
          <Routes>
            <Route path="/knowledge-processing" element={<KnowledgeProcessingPage />} />
            <Route path="/chunks" element={<Navigate to="/knowledge-processing?stage=chunks" replace />} />
            <Route path="/embeddings" element={<Navigate to="/knowledge-processing?stage=embeddings" replace />} />
            <Route path="/vectors" element={<Navigate to="/knowledge-processing?stage=vectors" replace />} />
          </Routes>
        </MemoryRouter>
      )

    const { unmount: unmount1 } = renderWithRoutes('/chunks')
    expect(screen.getByText('Active Stage: Chunks')).toBeInTheDocument()
    unmount1()

    const { unmount: unmount2 } = renderWithRoutes('/embeddings')
    expect(screen.getByText('Active Stage: Embeddings')).toBeInTheDocument()
    unmount2()

    const { unmount: unmount3 } = renderWithRoutes('/vectors')
    expect(screen.getByText('Active Stage: Vectors')).toBeInTheDocument()
    unmount3()
  })
})
