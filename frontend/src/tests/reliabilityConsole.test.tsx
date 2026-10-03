import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import {
  toPresentationPercentage,
  formatPresentationPercentage,
  toCanonicalScore,
} from '../utils/telemetryAdapters'
import { ForensicTraceDrawer } from '../pages/analytics/components/ForensicTraceDrawer'
import { DiagnosticSandboxTab } from '../pages/analytics/components/DiagnosticSandboxTab'
import { ReliabilityDashboardPage } from '../pages/analytics/ReliabilityDashboardPage'
import type { QueryTraceDetailDTO } from '../types'

// Mock analytics service
vi.mock('@/services/analyticsService', () => ({
  analyticsService: {
    getSuccessRate: vi.fn().mockResolvedValue({
      total_queries: 100,
      success_count: 95,
      success_rate_percentage: 95.0,
      clarification_count: 3,
      aborted_low_confidence_count: 2,
      aborted_hallucination_count: 0,
    }),
    getLatencyAnalytics: vi.fn().mockResolvedValue({
      avg_ms: 120,
      p50_ms: 110,
      p90_ms: 180,
      p95_ms: 220,
      p99_ms: 310,
      stage_breakdown: {},
    }),
    getConfidenceAnalytics: vi.fn().mockResolvedValue({
      mean_confidence: 0.88,
      median_confidence: 0.89,
      std_deviation: 0.05,
      confidence_histogram: [],
    }),
    getQueryTrends: vi.fn().mockResolvedValue({
      time_series: [],
      period_label: 'daily',
    }),
    getReliabilityHistory: vi.fn().mockResolvedValue({
      dates: ['2026-10-01', '2026-10-02'],
      scores: [0.92, 0.95],
      moving_average_scores: [0.91, 0.93],
    }),
    getReliabilityTrends: vi.fn().mockResolvedValue([
      { date: '2026-10-01', average_score: 0.92, total_queries: 50 },
      { date: '2026-10-02', average_score: 0.95, total_queries: 50 },
    ]),
    getSearchAnalytics: vi.fn().mockResolvedValue({
      total_searches: 80,
      avg_dense_candidates: 10,
      avg_sparse_candidates: 10,
      avg_merged_unique: 15,
      avg_retrieval_duration_ms: 45.2,
      stage_breakdowns: {},
    }),
    getQueryHistory: vi.fn().mockResolvedValue({
      items: [
        {
          id: 'q1',
          tenant_id: 'test-tenant',
          correlation_id: 'corr-101',
          query_text: 'What is data retention policy?',
          confidence_score: 0.89,
          hallucination_score: 0.05,
          reliability_score: 0.89,
          outcome: 'SUCCESS',
          retry_attempts: 0,
          total_duration_ms: 125.0,
          is_safe_to_serve: true,
          created_at: new Date().toISOString(),
        },
      ],
      total: 1,
    }),
    getQueryTraceDetail: vi.fn().mockResolvedValue({
      record: {
        id: 'q1',
        tenant_id: 'test-tenant',
        correlation_id: 'corr-101',
        query_text: 'What is data retention policy?',
        confidence_score: 0.89,
        hallucination_score: 0.05,
        reliability_score: 0.89,
        outcome: 'SUCCESS',
        retry_attempts: 0,
        total_duration_ms: 125.0,
        is_safe_to_serve: true,
        created_at: new Date().toISOString(),
      },
      stage_traces: [
        {
          stage_name: 'Dense Retrieval',
          duration_ms: 25.0,
          status: 'COMPLETED',
          metadata: {},
          is_authoritative: true,
        },
      ],
      retrieval_candidates: [],
      confidence_signals: [],
      self_corrections: [],
      is_authoritative: true,
    }),
    executeSandboxQuery: vi.fn().mockResolvedValue({
      correlation_id: 'sandbox-corr-1',
      outcome: 'SUCCESS',
      final_answer: 'Enterprise retention is 7 years under SOC 2.',
      trace_detail: {
        record: {
          id: 's1',
          tenant_id: 'test-tenant',
          correlation_id: 'sandbox-corr-1',
          query_text: 'Test sandbox query',
          confidence_score: 0.92,
          hallucination_score: 0.02,
          reliability_score: 0.92,
          outcome: 'SUCCESS',
          retry_attempts: 0,
          total_duration_ms: 110.0,
          is_safe_to_serve: true,
          created_at: new Date().toISOString(),
        },
        stage_traces: [
          {
            stage_name: 'Hybrid Retrieval',
            duration_ms: 30.0,
            status: 'COMPLETED',
            metadata: {},
            is_authoritative: true,
          },
        ],
        retrieval_candidates: [],
        confidence_signals: [],
        self_corrections: [],
        is_authoritative: true,
      },
    }),
  },
}))

describe('Telemetry Presentation Adapters (UNIT-OPS-03)', () => {
  it('converts canonical 0.0000–1.0000 backend scores to percentage (0.0%–100.0%)', () => {
    expect(toPresentationPercentage(0.854)).toBe(85.4)
    expect(toPresentationPercentage(1.0)).toBe(100.0)
    expect(toPresentationPercentage(0.0)).toBe(0.0)
    expect(toPresentationPercentage(0.9502)).toBe(95.0)
  })

  it('safely tolerates legacy scores already in 0–100 range', () => {
    expect(toPresentationPercentage(85.4)).toBe(85.4)
    expect(toPresentationPercentage(95.0)).toBe(95.0)
    expect(toPresentationPercentage(100.0)).toBe(100.0)
  })

  it('handles null and undefined with specified fallback', () => {
    expect(toPresentationPercentage(null, 95.0)).toBe(95.0)
    expect(toPresentationPercentage(undefined, 0.0)).toBe(0.0)
  })

  it('formats presentation percentage string accurately', () => {
    expect(formatPresentationPercentage(0.854)).toBe('85.4%')
    expect(formatPresentationPercentage(null)).toBe('N/A')
  })

  it('converts presentation percentage back to canonical score float', () => {
    expect(toCanonicalScore(85.4)).toBe(0.854)
    expect(toCanonicalScore(100)).toBe(1.0)
    expect(toCanonicalScore(null)).toBeNull()
  })
})

describe('ForensicTraceDrawer (Telemetry Truth & Authority)', () => {
  const authoritativeTrace: QueryTraceDetailDTO = {
    record: {
      id: 'rec-1',
      tenant_id: 'test-tenant',
      correlation_id: 'corr-auth-123',
      query_text: 'What are the enterprise retention terms?',
      confidence_score: 0.92,
      hallucination_score: 0.02,
      reliability_score: 0.92,
      outcome: 'SUCCESS',
      retry_attempts: 0,
      total_duration_ms: 140.0,
      is_safe_to_serve: true,
      created_at: new Date().toISOString(),
    },
    stage_traces: [
      {
        stage_name: 'Dense Retrieval',
        duration_ms: 35.0,
        status: 'COMPLETED',
        metadata: {},
        is_authoritative: true,
      },
    ],
    retrieval_candidates: [],
    confidence_signals: [],
    self_corrections: [],
    is_authoritative: true,
  }

  const estimatedTrace: QueryTraceDetailDTO = {
    ...authoritativeTrace,
    is_authoritative: false,
    stage_traces: [
      {
        stage_name: 'Dense Retrieval',
        duration_ms: 35.0,
        status: 'COMPLETED',
        metadata: {},
        is_authoritative: false,
      },
    ],
  }

  it('displays [Hardware Telemetry Verified] badge when is_authoritative is true', () => {
    render(
      <ForensicTraceDrawer
        isOpen={true}
        onClose={vi.fn()}
        initialTrace={authoritativeTrace}
      />
    )

    expect(screen.getByText('[Hardware Telemetry Verified]')).toBeInTheDocument()
    expect(
      screen.getByText(/Hardware stage durations recorded directly from database queries/i)
    ).toBeInTheDocument()
  })

  it('displays [Estimated / Model Approximation] banner when is_authoritative is false', () => {
    render(
      <ForensicTraceDrawer
        isOpen={true}
        onClose={vi.fn()}
        initialTrace={estimatedTrace}
      />
    )

    expect(screen.getByText('[Estimated / Model Approximation]')).toBeInTheDocument()
    expect(screen.getByText(/historical telemetry record prior to hardware instrumentation/i)).toBeInTheDocument()
  })
})

describe('DiagnosticSandboxTab (Simulation Mode)', () => {
  it('displays [Simulation & Dry-Run Mode] banner with clear non-mutating badge', () => {
    render(<DiagnosticSandboxTab onInspectTrace={vi.fn()} />)

    expect(screen.getByText('[Simulation & Dry-Run Mode]')).toBeInTheDocument()
    expect(screen.getByText('Non-Mutating Sandbox')).toBeInTheDocument()
    expect(screen.getByText(/Execute ad-hoc diagnostic tests against real retrieval vectors/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Run Sandbox Dry-Run/i })).toBeInTheDocument()
  })
})

describe('ReliabilityDashboardPage Tabs & Navigation', () => {
  it('renders Overview tab by default and allows switching between tabs', async () => {
    render(
      <MemoryRouter initialEntries={['/reliability']}>
        <Routes>
          <Route path="/reliability" element={<ReliabilityDashboardPage />} />
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('AI Reliability & Diagnostics Console')).toBeInTheDocument()
    })

    // Overview components present
    expect(screen.getByText('Unified AI Reliability Score')).toBeInTheDocument()

    // Switch to Diagnostic Sandbox
    const sandboxTabButton = screen.getByRole('button', { name: /Diagnostic Sandbox/i })
    fireEvent.click(sandboxTabButton)

    await waitFor(() => {
      expect(screen.getByText('[Simulation & Dry-Run Mode]')).toBeInTheDocument()
      expect(screen.getByText('Pipeline Test Parameters')).toBeInTheDocument()
    })

    // Switch to Query Explorer
    const explorerTabButton = screen.getByRole('button', { name: /Query Explorer/i })
    fireEvent.click(explorerTabButton)

    await waitFor(() => {
      expect(screen.getByText(/Direct Trace ID Lookup:/i)).toBeInTheDocument()
    })
  })
})
