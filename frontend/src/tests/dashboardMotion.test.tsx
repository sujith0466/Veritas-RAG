import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ExecutiveKpiGrid } from '@/components/dashboard/ExecutiveKpiGrid'
import { RetrievalLatencyRadar } from '@/components/dashboard/RetrievalLatencyRadar'
import type { CommandKpisDTO, CommandReliabilityTrendPointDTO, CommandLatencyPercentilesDTO, CommandOutcomesBreakdownDTO } from '@/types'

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

  beforeEach(() => {
    vi.clearAllMocks()
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
})
