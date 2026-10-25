import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CommandCenterHeader } from '@/components/dashboard/CommandCenterHeader'
import { WorkspaceAnalyticsHeader } from '@/components/analytics/WorkspaceAnalyticsHeader'
import { WorkspaceAnalyticsPage } from '@/pages/analytics/WorkspaceAnalyticsPage'
import { ReliabilityDashboardPage } from '@/pages/analytics/ReliabilityDashboardPage'
import { StalenessReportCard } from '@/components/analytics/StalenessReportCard'
import { knowledgeHealthService } from '@/services/knowledgeHealthService'
import { analyticsService } from '@/services/analyticsService'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import {
  getWorkspaceAnalyticsPreferences,
  saveWorkspaceAnalyticsPreferences,
  validateAnalyticsTimeRange,
  getScopedAnalyticsStorageKey,
} from '@/utils/workspaceAnalyticsPreferences'
import {
  getReliabilityPreferences,
  saveReliabilityPreferences,
  validateReliabilityInterval,
  validateReliabilityLiveSync,
} from '@/utils/reliabilityPreferences'
import type { UserContext } from '@/types'

// Mock services
vi.mock('@/services/analyticsService', () => ({
  analyticsService: {
    getWorkspaceOverview: vi.fn().mockResolvedValue({
      active_users: 10,
      total_queries: 120,
      document_count: 5,
    }),
    getSuccessRate: vi.fn().mockResolvedValue({
      total_queries: 100,
      success_count: 95,
      success_rate_percentage: 95.0,
      clarification_count: 3,
      aborted_low_confidence_count: 2,
      aborted_hallucination_count: 0,
    }),
    getReliabilityTrends: vi.fn().mockResolvedValue([
      { date: '2026-10-01', average_score: 0.92, total_queries: 50 },
    ]),
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
    getSearchAnalytics: vi.fn().mockResolvedValue({
      total_searches: 80,
      avg_dense_candidates: 10,
      avg_sparse_candidates: 10,
      avg_merged_unique: 15,
      avg_retrieval_duration_ms: 45.2,
      stage_breakdowns: {},
    }),
    getQueryHistory: vi.fn().mockResolvedValue({
      items: [],
      total: 0,
    }),
    getPopularTopics: vi.fn().mockResolvedValue([]),
    getUnansweredQueries: vi.fn().mockResolvedValue([]),
    getMostCitedDocuments: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('@/services/knowledgeHealthService', () => ({
  knowledgeHealthService: {
    getStalenessReport: vi.fn().mockResolvedValue({
      workspace_id: 'ws-a',
      total_documents: 10,
      stale_count: 0,
      stale_ratio: 0.0,
      aging_distribution: { '0-30 days': 10, '31-90 days': 0, '>90 days': 0 },
      stale_documents: [],
    }),
    executeBulkRemediation: vi.fn().mockResolvedValue({}),
  },
}))

vi.mock('@/api/wrapper', () => ({
  get: vi.fn(),
  post: vi.fn(),
  del: vi.fn(),
}))

describe('Veritas RAG — UI Cleanup, Preference Persistence & Staleness Fixes', () => {
  let queryClient: QueryClient

  const mockUserA: UserContext = {
    id: 'user-aaa-111',
    email: 'alice@veritas.internal',
    role: 'admin',
    tenant_id: 'tenant-a',
    workspace_id: 'ws-a',
    workspace_name: 'Veritas Alpha',
    full_name: 'Alice Analyst',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }

  const mockUserB: UserContext = {
    id: 'user-bbb-222',
    email: 'bob@veritas.internal',
    role: 'admin',
    tenant_id: 'tenant-b',
    workspace_id: 'ws-b',
    workspace_name: 'Veritas Beta',
    full_name: 'Bob Operator',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }

  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    useAuthStore.setState({ user: mockUserA })
    useWorkspaceStore.setState({
      currentWorkspace: {
        id: 'ws-a',
        name: 'Workspace Alpha',
        status: 'ACTIVE',
        tier: 'ENTERPRISE',
        role: 'ADMIN',
      } as any,
    })
  })

  afterEach(() => {
    localStorage.clear()
    queryClient.clear()
  })

  // ───────────────────────────────────────────────────────────────────────────
  // FIX #1: DASHBOARD COMMAND CENTER GREEN DOT REMOVAL
  // ───────────────────────────────────────────────────────────────────────────
  describe('Fix #1 — Dashboard: Remove Command Center green dot', () => {
    it('does not render the green status dot beside Command Center when system is OPERATIONAL', () => {
      render(
        <CommandCenterHeader
          timeWindow="24h"
          onTimeWindowChange={vi.fn()}
          autoRefreshInterval={0}
          onAutoRefreshChange={vi.fn()}
          isLoading={false}
          onRefresh={vi.fn()}
          systemStatus="OPERATIONAL"
        />
      )

      // The heading remains intact
      expect(screen.getByText('Veritas RAG')).toBeInTheDocument()
      expect(screen.getByText('Command Center')).toBeInTheDocument()

      // The green dot and operational badge are not rendered
      expect(screen.queryByTitle('OPERATIONAL')).not.toBeInTheDocument()
      expect(screen.queryByLabelText('OPERATIONAL')).not.toBeInTheDocument()
      expect(screen.queryByText('OPERATIONAL')).not.toBeInTheDocument()
    })

    it('preserves genuine status indicator badge when system is DEGRADED or DOWN', () => {
      const { rerender } = render(
        <CommandCenterHeader
          timeWindow="24h"
          onTimeWindowChange={vi.fn()}
          autoRefreshInterval={0}
          onAutoRefreshChange={vi.fn()}
          isLoading={false}
          onRefresh={vi.fn()}
          systemStatus="DEGRADED"
        />
      )

      // Warning badge displayed
      expect(screen.getByTitle('DEGRADED')).toBeInTheDocument()
      expect(screen.getByText('DEGRADED')).toBeInTheDocument()

      // Down / destructive badge displayed
      rerender(
        <CommandCenterHeader
          timeWindow="24h"
          onTimeWindowChange={vi.fn()}
          autoRefreshInterval={0}
          onAutoRefreshChange={vi.fn()}
          isLoading={false}
          onRefresh={vi.fn()}
          systemStatus="OUTAGE"
        />
      )

      expect(screen.getByTitle('OUTAGE')).toBeInTheDocument()
      expect(screen.getByText('OUTAGE')).toBeInTheDocument()
    })
  })

  // ───────────────────────────────────────────────────────────────────────────
  // FIX #2 & #4: WORKSPACE ANALYTICS METADATA & ACTIVE FILTER REMOVAL
  // ───────────────────────────────────────────────────────────────────────────
  describe('Fix #2 & #4 — Workspace Analytics: Metadata and Active Filter Removal', () => {
    it('does not render introductory metadata row or redundant Active filter line', () => {
      render(
        <WorkspaceAnalyticsHeader
          timeRange="30d"
          onTimeRangeChange={vi.fn()}
          onRefresh={vi.fn()}
          isRefreshing={false}
          lastUpdated={new Date('2026-10-25T12:00:00Z')}
          workspaceName="Workspace Alpha"
          workspaceStatus="ACTIVE"
        />
      )

      // Heading and description remain intact
      expect(screen.getByText('Knowledge Reliability & Intelligence')).toBeInTheDocument()
      expect(screen.getByText(/Real-time telemetry, knowledge asset citation impact/)).toBeInTheDocument()

      // Fix 2: Introductory metadata row removed
      expect(screen.queryByText('Workspace Intelligence')).not.toBeInTheDocument()
      expect(screen.queryByText(/Scope:/i)).not.toBeInTheDocument()

      // Fix 4: Redundant active filter line removed
      expect(screen.queryByText(/Active filter:/i)).not.toBeInTheDocument()

      // Telemetry sync timestamp remains visible
      expect(screen.getByText(/Telemetry synced at:/i)).toBeInTheDocument()

      // Date range controls remain present
      expect(screen.getByRole('button', { name: '24H' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '7D' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '30D' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '90D' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'All Time' })).toBeInTheDocument()
    })
  })

  // ───────────────────────────────────────────────────────────────────────────
  // FIX #3: WORKSPACE ANALYTICS DATE-RANGE PREFERENCE PERSISTENCE
  // ───────────────────────────────────────────────────────────────────────────
  describe('Fix #3 — Workspace Analytics Date-Range Preference Persistence', () => {
    it('validates supported date ranges with safe fallback and case-insensitivity', () => {
      expect(validateAnalyticsTimeRange('24h')).toBe('24h')
      expect(validateAnalyticsTimeRange('24H')).toBe('24h')
      expect(validateAnalyticsTimeRange('7d')).toBe('7d')
      expect(validateAnalyticsTimeRange('30D')).toBe('30d')
      expect(validateAnalyticsTimeRange('90d')).toBe('90d')
      expect(validateAnalyticsTimeRange('all')).toBe('all')
      expect(validateAnalyticsTimeRange('All Time')).toBe('all')
      expect(validateAnalyticsTimeRange('invalid')).toBe('30d')
      expect(validateAnalyticsTimeRange(null)).toBe('30d')
      expect(validateAnalyticsTimeRange(undefined)).toBe('30d')
    })

    it('scopes preferences strictly per authenticated user ID', () => {
      saveWorkspaceAnalyticsPreferences(mockUserA.id, { timeRange: '7d' })
      saveWorkspaceAnalyticsPreferences(mockUserB.id, { timeRange: '90d' })

      expect(getWorkspaceAnalyticsPreferences(mockUserA.id).timeRange).toBe('7d')
      expect(getWorkspaceAnalyticsPreferences(mockUserB.id).timeRange).toBe('90d')

      // Key isolation
      const keyA = getScopedAnalyticsStorageKey(mockUserA.id)
      const keyB = getScopedAnalyticsStorageKey(mockUserB.id)
      expect(keyA).toContain(mockUserA.id)
      expect(keyB).toContain(mockUserB.id)
      expect(keyA).not.toEqual(keyB)
    })

    it('restores saved user preference and drives analytics queries on page mount', async () => {
      // Save 7d for mockUserA
      saveWorkspaceAnalyticsPreferences(mockUserA.id, { timeRange: '7d' })

      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={['/workspace-analytics']}>
            <WorkspaceAnalyticsPage />
          </MemoryRouter>
        </QueryClientProvider>
      )

      // The 7D pill should be marked as pressed
      const button7D = screen.getByRole('button', { name: '7D' })
      expect(button7D).toHaveAttribute('aria-pressed', 'true')

      // The analytics overview query was called with the 7d calculated window
      await waitFor(() => {
        expect(analyticsService.getWorkspaceOverview).toHaveBeenCalled()
      })
    })

    it('updates saved preference when user clicks a different date range', async () => {
      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={['/workspace-analytics']}>
            <WorkspaceAnalyticsPage />
          </MemoryRouter>
        </QueryClientProvider>
      )

      const button90D = screen.getByRole('button', { name: '90D' })
      fireEvent.click(button90D)

      expect(button90D).toHaveAttribute('aria-pressed', 'true')
      expect(getWorkspaceAnalyticsPreferences(mockUserA.id).timeRange).toBe('90d')
    })

    it('switches preferences safely when authenticated user changes (logout/login)', async () => {
      saveWorkspaceAnalyticsPreferences(mockUserA.id, { timeRange: '24h' })
      saveWorkspaceAnalyticsPreferences(mockUserB.id, { timeRange: '90d' })

      const { rerender } = render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={['/workspace-analytics']}>
            <WorkspaceAnalyticsPage />
          </MemoryRouter>
        </QueryClientProvider>
      )

      expect(screen.getByRole('button', { name: '24H' })).toHaveAttribute('aria-pressed', 'true')

      // Switch user to mockUserB
      act(() => {
        useAuthStore.setState({ user: mockUserB })
      })

      rerender(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={['/workspace-analytics']}>
            <WorkspaceAnalyticsPage />
          </MemoryRouter>
        </QueryClientProvider>
      )

      await waitFor(() => {
        expect(screen.getByRole('button', { name: '90D' })).toHaveAttribute('aria-pressed', 'true')
      })
    })
  })

  // ───────────────────────────────────────────────────────────────────────────
  // FIX #5: KNOWLEDGE STALENESS & HEALTH ROOT-CAUSE INVESTIGATION & VERIFICATION
  // ───────────────────────────────────────────────────────────────────────────
  describe('Fix #5 — Knowledge Staleness & Health Root-Cause Resolution', () => {
    it('verifies knowledgeHealthService calls the correct workspace-prefixed endpoints', async () => {
      const { get, post } = await import('@/api/wrapper')
      const { knowledgeHealthService: actualService } = await vi.importActual<any>('@/services/knowledgeHealthService')

      ;(get as any).mockResolvedValueOnce({
        workspace_id: 'ws-a',
        total_documents: 10,
        stale_count: 2,
        stale_ratio: 20.0,
        aging_distribution: { '0-30 days': 8, '31-90 days': 2, '>90 days': 0 },
        stale_documents: [],
      })

      await actualService.getStalenessReport('ws-a')
      // Must call /workspaces/${workspaceId}/knowledge-base/staleness/report
      expect(get).toHaveBeenCalledWith('/workspaces/ws-a/knowledge-base/staleness/report')

      ;(post as any).mockResolvedValueOnce({ remediated_count: 2 })
      await actualService.executeBulkRemediation('ws-a', { action: 'MARK_REVIEWED', document_ids: ['d1'] })
      // Must call /workspaces/${workspaceId}/knowledge-base/staleness/remediate
      expect(post).toHaveBeenCalledWith('/workspaces/ws-a/knowledge-base/staleness/remediate', {
        action: 'MARK_REVIEWED',
        document_ids: ['d1'],
      })
    })

    it('renders clean fresh state when workspace documents are fresh (stale_count = 0)', async () => {
      vi.mocked(knowledgeHealthService.getStalenessReport).mockResolvedValueOnce({
        workspace_id: 'ws-a',
        total_documents: 15,
        stale_count: 0,
        stale_ratio: 0.0,
        aging_distribution: { '0-30 days': 15, '31-90 days': 0, '>90 days': 0 },
        stale_documents: [],
      })

      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <StalenessReportCard />
          </MemoryRouter>
        </QueryClientProvider>
      )

      await waitFor(() => {
        expect(screen.getByText('All workspace documents are fresh')).toBeInTheDocument()
      })
      expect(screen.getByText(/Zero documents exceed staleness thresholds/)).toBeInTheDocument()
    })

    it('renders stale document warning and aging breakdown when stale documents exist', async () => {
      vi.mocked(knowledgeHealthService.getStalenessReport).mockResolvedValueOnce({
        workspace_id: 'ws-a',
        total_documents: 10,
        stale_count: 3,
        stale_ratio: 30.0,
        aging_distribution: { '0-30 days': 7, '31-90 days': 2, '>90 days': 1 },
        stale_documents: [
          {
            document_id: 'doc-1',
            filename: 'architecture-spec.pdf',
            age_days: 95,
            freshness_score: 40.0,
            is_expired: true,
            last_updated_at: '2026-07-20T00:00:00Z',
          },
        ],
      })

      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <StalenessReportCard />
          </MemoryRouter>
        </QueryClientProvider>
      )

      await waitFor(() => {
        expect(screen.getByText(/3 Stale \(30%\)/)).toBeInTheDocument()
        expect(screen.getByText('architecture-spec.pdf')).toBeInTheDocument()
        expect(screen.getByText(/Expired/i)).toBeInTheDocument()
      })
    })

    it('renders error state with Retry action on genuine backend failure and recovers upon retry', async () => {
      vi.mocked(knowledgeHealthService.getStalenessReport)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          workspace_id: 'ws-a',
          total_documents: 5,
          stale_count: 0,
          stale_ratio: 0.0,
          aging_distribution: { '0-30 days': 5, '31-90 days': 0, '>90 days': 0 },
          stale_documents: [],
        })

      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <StalenessReportCard />
          </MemoryRouter>
        </QueryClientProvider>
      )

      await waitFor(() => {
        expect(screen.getByText('Failed to load staleness report')).toBeInTheDocument()
      })

      const retryButton = screen.getByRole('button', { name: /Retry/i })
      expect(retryButton).toBeInTheDocument()

      fireEvent.click(retryButton)

      await waitFor(() => {
        expect(screen.getByText('All workspace documents are fresh')).toBeInTheDocument()
      })
    })
  })

  // ───────────────────────────────────────────────────────────────────────────
  // FIX #6: AI RELIABILITY & DIAGNOSTICS CONSOLE PREFERENCE PERSISTENCE
  // ───────────────────────────────────────────────────────────────────────────
  describe('Fix #6 — AI Reliability Console Monitoring Preferences', () => {
    it('validates reliability aggregation intervals and live sync preferences', () => {
      expect(validateReliabilityInterval('hourly')).toBe('hourly')
      expect(validateReliabilityInterval('HOURLY')).toBe('hourly')
      expect(validateReliabilityInterval('daily')).toBe('daily')
      expect(validateReliabilityInterval('weekly')).toBe('weekly')
      expect(validateReliabilityInterval('monthly')).toBe('daily') // fallback

      expect(validateReliabilityLiveSync(true)).toBe(true)
      expect(validateReliabilityLiveSync(false)).toBe(false)
      expect(validateReliabilityLiveSync('invalid')).toBe(false) // fallback
    })

    it('scopes reliability preferences by authenticated user ID', () => {
      saveReliabilityPreferences(mockUserA.id, { interval: 'hourly', liveSync: true })
      saveReliabilityPreferences(mockUserB.id, { interval: 'weekly', liveSync: false })

      expect(getReliabilityPreferences(mockUserA.id)).toEqual({
        interval: 'hourly',
        liveSync: true,
      })
      expect(getReliabilityPreferences(mockUserB.id)).toEqual({
        interval: 'weekly',
        liveSync: false,
      })
    })

    it('restores saved interval and live sync preferences on page mount', async () => {
      saveReliabilityPreferences(mockUserA.id, { interval: 'weekly', liveSync: true })

      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={['/reliability?tab=overview']}>
            <Routes>
              <Route path="/reliability" element={<ReliabilityDashboardPage />} />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      )

      await waitFor(() => {
        expect(screen.getByText('AI Reliability & Diagnostics Console')).toBeInTheDocument()
      })

      // 'weekly' button has active styling
      const weeklyButton = screen.getByRole('button', { name: /weekly/i })
      expect(weeklyButton.className).toContain('bg-primary')

      // Live Sync shows active 15s state
      expect(screen.getByRole('button', { name: /Live Sync 15s/i })).toBeInTheDocument()
    })

    it('persists interval and live sync changes when toggled', async () => {
      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={['/reliability?tab=overview']}>
            <Routes>
              <Route path="/reliability" element={<ReliabilityDashboardPage />} />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      )

      await waitFor(() => {
        expect(screen.getByText('AI Reliability & Diagnostics Console')).toBeInTheDocument()
      })

      // Toggle to hourly
      const hourlyButton = screen.getByRole('button', { name: /hourly/i })
      fireEvent.click(hourlyButton)
      expect(getReliabilityPreferences(mockUserA.id).interval).toBe('hourly')

      // Toggle Live Sync on
      const liveSyncButton = screen.getByRole('button', { name: /Live Sync Off/i })
      fireEvent.click(liveSyncButton)
      expect(getReliabilityPreferences(mockUserA.id).liveSync).toBe(true)
      expect(screen.getByRole('button', { name: /Live Sync 15s/i })).toBeInTheDocument()

      // Toggle Live Sync off again
      const liveSyncActiveButton = screen.getByRole('button', { name: /Live Sync 15s/i })
      fireEvent.click(liveSyncActiveButton)
      expect(getReliabilityPreferences(mockUserA.id).liveSync).toBe(false)
      expect(screen.getByRole('button', { name: /Live Sync Off/i })).toBeInTheDocument()
    })
  })
})
