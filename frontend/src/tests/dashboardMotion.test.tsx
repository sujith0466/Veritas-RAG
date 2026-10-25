import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ExecutiveKpiGrid } from '@/components/dashboard/ExecutiveKpiGrid'
import { RetrievalLatencyRadar } from '@/components/dashboard/RetrievalLatencyRadar'
import { KnowledgePipelineCard } from '@/components/dashboard/KnowledgePipelineCard'
import { OperationalAlertsBanner } from '@/components/dashboard/OperationalAlertsBanner'
import { CommandCenterHeader } from '@/components/dashboard/CommandCenterHeader'
import { DashboardPage } from '@/pages/dashboard/DashboardPage'
import { dashboardService } from '@/services/dashboardService'
import type {
  CommandKpisDTO,
  CommandReliabilityTrendPointDTO,
  CommandLatencyPercentilesDTO,
  CommandOutcomesBreakdownDTO,
  CommandKnowledgeHealthDTO,
  CommandCenterDTO,
  QueryExecutionLedgerDTO,
} from '@/types'

// Mock dashboard service
vi.mock('@/services/dashboardService', () => ({
  dashboardService: {
    getCommandCenter: vi.fn(),
    getExecutions: vi.fn(),
    getExecutionTrace: vi.fn(),
  },
}))

describe('Dashboard Motion & Restrained Visual Transitions', () => {
  const mockKpis: CommandKpisDTO = {
    total_queries: 1420,
    avg_reliability_score: 0.942,
    avg_confidence_score: 0.91,
    avg_latency_ms: 820,
    p95_latency_ms: 1250,
    self_correction_rate: 8.5,
    clarification_rate: 4.2,
    hallucination_prevention_count: 34,
    active_tenants: 12,
    active_workspaces: 18,
  }

  const mockTrendPoints: CommandReliabilityTrendPointDTO[] = [
    { timestamp: '2026-10-25T00:00:00Z', reliability: 0.92, query_count: 300 },
    { timestamp: '2026-10-25T06:00:00Z', reliability: 0.95, query_count: 450 },
    { timestamp: '2026-10-25T12:00:00Z', reliability: 0.94, query_count: 670 },
  ]

  const mockLatency: CommandLatencyPercentilesDTO = {
    p50_ms: 850,
    p90_ms: 1400,
    p95_ms: 2200,
    p99_ms: 4500,
    avg_ms: 1100,
  }

  const mockOutcomes: CommandOutcomesBreakdownDTO = {
    total_count: 500,
    success_count: 420,
    clarification_count: 45,
    aborted_hallucination_count: 25,
    aborted_low_confidence_count: 10,
    no_relevant_chunks_count: 0,
    policy_violation_count: 0,
  }

  const mockKnowledge: CommandKnowledgeHealthDTO = {
    total_documents: 48,
    processed_documents: 46,
    failed_documents: 2,
    total_chunks: 3410,
    total_embeddings: 3410,
    pending_jobs: 0,
    failed_jobs: 0,
    vector_status: 'HEALTHY',
  }

  const mockCommandCenter: CommandCenterDTO = {
    tenant_id: 'tenant-test-1',
    time_window: '24h',
    system_health: {
      status: 'OPERATIONAL',
      components: [
        { name: 'PostgreSQL', status: 'healthy', latency_ms: 1.2, detail: null },
        { name: 'Redis', status: 'healthy', latency_ms: 0.8, detail: null },
        { name: 'Qdrant', status: 'healthy', latency_ms: 2.1, detail: null },
      ],
    },
    kpis: mockKpis,
    reliability_trend: mockTrendPoints,
    latency_percentiles: mockLatency,
    outcomes: mockOutcomes,
    knowledge_health: mockKnowledge,
    alerts: [],
  }

  const mockLedger: QueryExecutionLedgerDTO = {
    items: [
      {
        id: 'query-1',
        correlation_id: 'corr-1',
        query_text: 'What are the SOC2 compliance controls?',
        outcome: 'SUCCESS',
        confidence_score: 0.95,
        reliability_score: 0.96,
        hallucination_score: 0.02,
        duration_ms: 780,
        retry_attempts: 0,
        is_safe_to_serve: true,
        timestamp: '2026-10-25T14:00:00Z',
        has_retrieval_trace: true,
      },
    ],
    total: 1,
    limit: 15,
    offset: 0,
    time_window: '24h',
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(dashboardService.getCommandCenter).mockResolvedValue(mockCommandCenter)
    vi.mocked(dashboardService.getExecutions).mockResolvedValue(mockLedger)
  })

  it('renders ExecutiveKpiGrid with all 4 metric cards and sparkline', () => {
    render(
      <ExecutiveKpiGrid
        kpis={mockKpis}
        trendPoints={mockTrendPoints}
        timeWindow="24h"
        isLoading={false}
        shouldAnimate={true}
      />
    )

    expect(screen.getByText('Composite Reliability')).toBeInTheDocument()
    expect(screen.getByText('94.2%')).toBeInTheDocument()
    expect(screen.getByText('Query Volume (24H)')).toBeInTheDocument()
    expect(screen.getByText('1,420')).toBeInTheDocument()
    expect(screen.getByText('P95 Execution Latency')).toBeInTheDocument()
    expect(screen.getByText('1,250 ms')).toBeInTheDocument()
    expect(screen.getByText('Self-Correction Rate')).toBeInTheDocument()
    expect(screen.getByText('8.5%')).toBeInTheDocument()
    expect(screen.getByText(/34 safety interventions triggered/)).toBeInTheDocument()
  })

  it('renders RetrievalLatencyRadar percentiles and animated outcome distribution', () => {
    render(
      <RetrievalLatencyRadar
        latency={mockLatency}
        outcomes={mockOutcomes}
        isLoading={false}
      />
    )

    expect(screen.getByText('Latency Decomposition & SLA Compliance')).toBeInTheDocument()
    expect(screen.getByText('P50 Median')).toBeInTheDocument()
    expect(screen.getByText('850 ms')).toBeInTheDocument()
    expect(screen.getByText('P95 Percentile')).toBeInTheDocument()
    expect(screen.getByText('2,200 ms')).toBeInTheDocument()
    expect(screen.getByText('Outcome Distribution')).toBeInTheDocument()
    expect(screen.getByText('500 total')).toBeInTheDocument()
  })

  it('renders KnowledgePipelineCard and OperationalAlertsBanner with balanced metrics', () => {
    render(
      <MemoryRouter>
        <KnowledgePipelineCard knowledge={mockKnowledge} isLoading={false} />
        <OperationalAlertsBanner alerts={[]} isLoading={false} />
      </MemoryRouter>
    )

    expect(screen.getByText('Knowledge Base & Vector Sync Health')).toBeInTheDocument()
    expect(screen.getByText('48')).toBeInTheDocument()
    expect(screen.getAllByText('3,410')).toHaveLength(2)
    expect(screen.getByText('Safety & Autonomous Interventions')).toBeInTheDocument()
    expect(screen.getByText('Zero Safety Interventions in Window')).toBeInTheDocument()
  })

  it('renders CommandCenterHeader with animated time-window pill controls', () => {
    const handleTimeWindow = vi.fn()
    const handleAutoRefresh = vi.fn()
    const handleRefresh = vi.fn()

    render(
      <CommandCenterHeader
        timeWindow="24h"
        onTimeWindowChange={handleTimeWindow}
        autoRefreshInterval={0}
        onAutoRefreshChange={handleAutoRefresh}
        isLoading={false}
        onRefresh={handleRefresh}
        systemStatus="OPERATIONAL"
      />
    )

    expect(screen.getByText('Veritas RAG')).toBeInTheDocument()
    expect(screen.getByText('Command Center')).toBeInTheDocument()
    expect(screen.queryByText('OPERATIONAL')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('OPERATIONAL')).not.toBeInTheDocument()
    expect(screen.getByText('24H')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: '24H' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: '7D' })).toHaveAttribute('aria-checked', 'false')
  })

  it('renders correctly when shouldAnimate is false (refetch / tab switch)', () => {
    render(
      <ExecutiveKpiGrid
        kpis={mockKpis}
        trendPoints={mockTrendPoints}
        timeWindow="7d"
        isLoading={false}
        shouldAnimate={false}
      />
    )

    expect(screen.getByText('Composite Reliability')).toBeInTheDocument()
    expect(screen.getByText('94.2%')).toBeInTheDocument()
  })

  it('confirms Subsystem & Infrastructure Health is completely absent from DashboardPage', async () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Latency Decomposition & SLA Compliance')).toBeInTheDocument()
    })

    // Subsystem & Infrastructure Health MUST NOT exist for any role
    expect(screen.queryByText(/Subsystem & Infrastructure Health/i)).not.toBeInTheDocument()

    // Preserved analytical and forensic panels MUST be present
    expect(screen.getByText('Knowledge Base & Vector Sync Health')).toBeInTheDocument()
    expect(screen.getByText('Safety & Autonomous Interventions')).toBeInTheDocument()
    expect(screen.getByText('AI Execution Flight Recorder & Audit Ledger')).toBeInTheDocument()
    expect(screen.getByText('Composite Reliability')).toBeInTheDocument()
    expect(screen.getByText('P95 Execution Latency')).toBeInTheDocument()
  })

  it('handles polling refresh without error and preserves stable rendered state', async () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Composite Reliability')).toBeInTheDocument()
    })

    // Trigger second data fetch simulating auto-refresh
    await act(async () => {
      const refreshBtn = screen.getByRole('button', { name: /refresh/i })
      refreshBtn.click()
    })

    expect(dashboardService.getCommandCenter).toHaveBeenCalledTimes(2)
    expect(screen.getByText('Latency Decomposition & SLA Compliance')).toBeInTheDocument()
    expect(screen.getByText('AI Execution Flight Recorder & Audit Ledger')).toBeInTheDocument()
  })
})
