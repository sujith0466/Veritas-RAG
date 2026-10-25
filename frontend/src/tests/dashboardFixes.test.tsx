import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { DashboardPage } from '@/pages/dashboard/DashboardPage'
import { CommandCenterHeader } from '@/components/dashboard/CommandCenterHeader'
import { ExecutionFlightRecorder } from '@/components/dashboard/ExecutionFlightRecorder'
import { dashboardService } from '@/services/dashboardService'
import { useAuthStore } from '@/stores/authStore'
import { storage, STORAGE_KEYS } from '@/utils/storage'
import {
  getDashboardPreferences,
  saveDashboardPreferences,
  validateTimeWindow,
  validateAutoRefreshInterval,
  getScopedDashboardStorageKey,
} from '@/utils/dashboardPreferences'
import type {
  CommandCenterDTO,
  QueryExecutionLedgerDTO,
  UserContext,
} from '@/types'

// Mock dashboard service
vi.mock('@/services/dashboardService', () => ({
  dashboardService: {
    getCommandCenter: vi.fn(),
    getExecutions: vi.fn(),
    getExecutionTrace: vi.fn(),
  },
}))

describe('Veritas RAG — Targeted Dashboard Fixes Verification', () => {
  const mockCommandCenter: CommandCenterDTO = {
    tenant_id: 'tenant-1',
    time_window: '24h',
    system_health: {
      status: 'OPERATIONAL',
      components: [
        { name: 'PostgreSQL', status: 'healthy', latency_ms: 1.0, detail: null },
      ],
    },
    kpis: {
      total_queries: 1200,
      avg_reliability_score: 0.95,
      avg_confidence_score: 0.92,
      avg_latency_ms: 650,
      p95_latency_ms: 1100,
      self_correction_rate: 6.2,
      clarification_rate: 3.1,
      hallucination_prevention_count: 22,
      active_tenants: 8,
      active_workspaces: 14,
    },
    reliability_trend: [
      { timestamp: '2026-10-25T00:00:00Z', reliability: 0.94, query_count: 200 },
      { timestamp: '2026-10-25T12:00:00Z', reliability: 0.96, query_count: 400 },
    ],
    latency_percentiles: {
      p50_ms: 600,
      p90_ms: 1000,
      p95_ms: 1500,
      p99_ms: 3200,
      avg_ms: 800,
    },
    outcomes: {
      total_count: 400,
      success_count: 360,
      clarification_count: 25,
      aborted_hallucination_count: 15,
      aborted_low_confidence_count: 0,
      no_relevant_chunks_count: 0,
      policy_violation_count: 0,
    },
    knowledge_health: {
      total_documents: 30,
      processed_documents: 29,
      failed_documents: 1,
      total_chunks: 1800,
      total_embeddings: 1800,
      pending_jobs: 0,
      failed_jobs: 0,
      vector_status: 'HEALTHY',
    },
    alerts: [],
  }

  const mockLedger: QueryExecutionLedgerDTO = {
    items: [
      {
        id: 'trace-1',
        correlation_id: 'corr-1',
        query_text: 'Explain HIPAA compliance requirements',
        outcome: 'SUCCESS',
        confidence_score: 0.98,
        reliability_score: 0.97,
        hallucination_score: 0.01,
        duration_ms: 620,
        retry_attempts: 0,
        is_safe_to_serve: true,
        timestamp: '2026-10-25T15:00:00Z',
        has_retrieval_trace: true,
      },
    ],
    total: 1,
    limit: 15,
    offset: 0,
    time_window: '24h',
  }

  const userA: UserContext = {
    id: 'usr-aaa-111',
    email: 'usera@veritas.ai',
    role: 'owner',
    tenant_id: 'ws-test',
    workspace_name: 'Veritas Alpha',
    full_name: 'User Alpha',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }

  const userB: UserContext = {
    id: 'usr-bbb-222',
    email: 'userb@veritas.ai',
    role: 'member',
    tenant_id: 'ws-test-2',
    workspace_name: 'Veritas Beta',
    full_name: 'User Beta',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    useAuthStore.setState({
      status: 'AUTHENTICATED',
      user: userA,
      token: 'jwt-alpha',
      error: undefined,
    })
    vi.mocked(dashboardService.getCommandCenter).mockResolvedValue(mockCommandCenter)
    vi.mocked(dashboardService.getExecutions).mockResolvedValue(mockLedger)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // ───────────────────────────────────────────────────────────────────────────
  // FIX #1: DROPDOWN VISIBILITY & DARK MODE STYLING
  // ───────────────────────────────────────────────────────────────────────────
  describe('Fix #1 — Dropdown Visibility & Dark Mode Rendering', () => {
    it('renders CommandCenterHeader auto-refresh select with dark mode support and contrast options', () => {
      const handleAutoRefresh = vi.fn()
      render(
        <CommandCenterHeader
          timeWindow="24h"
          onTimeWindowChange={vi.fn()}
          autoRefreshInterval={0}
          onAutoRefreshChange={handleAutoRefresh}
          isLoading={false}
          onRefresh={vi.fn()}
          systemStatus="OPERATIONAL"
        />
      )

      const select = screen.getByRole('combobox', { name: /auto refresh interval/i })
      expect(select).toBeInTheDocument()
      // Verifies color-scheme adapts natively to dark mode without breaking light mode
      expect(select.className).toContain('[color-scheme:light]')
      expect(select.className).toContain('dark:[color-scheme:dark]')

      // Verify all options exist with appropriate high-contrast styling in both dark and light modes
      const options = select.querySelectorAll('option')
      expect(options.length).toBe(4) // Off, 10s, 30s, 60s
      options.forEach((opt) => {
        expect(opt.className).toContain('bg-white')
        expect(opt.className).toContain('text-slate-900')
        expect(opt.className).toContain('dark:bg-slate-900')
        expect(opt.className).toContain('dark:text-slate-100')
      })
    })

    it('renders ExecutionFlightRecorder outcome filter select with dark mode styling and accessible focus', () => {
      render(
        <ExecutionFlightRecorder
          items={mockLedger.items}
          total={1}
          page={1}
          pageSize={15}
          onPageChange={vi.fn()}
          search=""
          onSearchChange={vi.fn()}
          statusFilter="ALL"
          onStatusFilterChange={vi.fn()}
          onInspectTrace={vi.fn()}
          isLoading={false}
          timeWindow="24h"
        />
      )

      const select = screen.getByRole('combobox', { name: /filter by outcome/i })
      expect(select).toBeInTheDocument()
      expect(select.className).toContain('[color-scheme:light]')
      expect(select.className).toContain('dark:[color-scheme:dark]')
      expect(select.className).toContain('focus:ring-primary/50')

      const options = select.querySelectorAll('option')
      expect(options.length).toBe(5)
      options.forEach((opt) => {
        expect(opt.className).toContain('dark:bg-slate-900')
        expect(opt.className).toContain('dark:text-slate-100')
      })
    })

    it('allows changing dropdown selection without error', () => {
      const handleAutoRefresh = vi.fn()
      render(
        <CommandCenterHeader
          timeWindow="24h"
          onTimeWindowChange={vi.fn()}
          autoRefreshInterval={0}
          onAutoRefreshChange={handleAutoRefresh}
          isLoading={false}
          onRefresh={vi.fn()}
          systemStatus="OPERATIONAL"
        />
      )

      const select = screen.getByRole('combobox', { name: /auto refresh interval/i })
      fireEvent.change(select, { target: { value: '30' } })
      expect(handleAutoRefresh).toHaveBeenCalledWith(30)
    })
  })

  // ───────────────────────────────────────────────────────────────────────────
  // FIX #2: PERSISTENCE OF SELECTED TIME PERIOD
  // ───────────────────────────────────────────────────────────────────────────
  describe('Fix #2 — Time Period Preference Persistence', () => {
    it('validates time window values correctly with case-insensitivity and safe default', () => {
      expect(validateTimeWindow('1h')).toBe('1h')
      expect(validateTimeWindow('24H')).toBe('24h')
      expect(validateTimeWindow('7D')).toBe('7d')
      expect(validateTimeWindow('30d')).toBe('30d')
      expect(validateTimeWindow('ALL')).toBe('all')
      expect(validateTimeWindow('invalid_window')).toBe('24h')
      expect(validateTimeWindow(null)).toBe('24h')
      expect(validateTimeWindow(undefined)).toBe('24h')
    })

    it('initializes DashboardPage with saved time period and drives API queries', async () => {
      // Pre-save 7D for userA
      saveDashboardPreferences(userA.id, { timeWindow: '7d' })

      render(
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText('Composite Reliability')).toBeInTheDocument()
      })

      // CommandCenter query was invoked with 7d
      expect(dashboardService.getCommandCenter).toHaveBeenCalledWith('7d')
      expect(dashboardService.getExecutions).toHaveBeenCalledWith(
        expect.objectContaining({ timeWindow: '7d' })
      )

      // Time window button shows 7D as checked
      const btn7d = screen.getByRole('radio', { name: '7D' })
      expect(btn7d).toHaveAttribute('aria-checked', 'true')
    })

    it('falls back safely to 24h when stored preference is missing or corrupted', async () => {
      // Write corrupted preference
      storage.set(getScopedDashboardStorageKey(userA.id), { timeWindow: 'CORRUPTED_VALUE' })

      render(
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText('Composite Reliability')).toBeInTheDocument()
      })

      expect(dashboardService.getCommandCenter).toHaveBeenCalledWith('24h')
      expect(screen.getByRole('radio', { name: '24H' })).toHaveAttribute('aria-checked', 'true')
    })

    it('persists new time period to storage when user selects another window', async () => {
      render(
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText('Composite Reliability')).toBeInTheDocument()
      })

      const btn30d = screen.getByRole('radio', { name: '30D' })
      await act(async () => {
        btn30d.click()
      })

      expect(btn30d).toHaveAttribute('aria-checked', 'true')
      expect(dashboardService.getCommandCenter).toHaveBeenCalledWith('30d')

      // Verify stored preference updated in storage
      const saved = getDashboardPreferences(userA.id)
      expect(saved.timeWindow).toBe('30d')
    })
  })

  // ───────────────────────────────────────────────────────────────────────────
  // FIX #3: AUTO-REFRESH PERSISTENCE & BEHAVIOR
  // ───────────────────────────────────────────────────────────────────────────
  describe('Fix #3 — Auto-refresh Persistence & Polling Execution', () => {
    it('validates auto-refresh intervals correctly with safe default', () => {
      expect(validateAutoRefreshInterval(0)).toBe(0)
      expect(validateAutoRefreshInterval(10)).toBe(10)
      expect(validateAutoRefreshInterval(30)).toBe(30)
      expect(validateAutoRefreshInterval(60)).toBe(60)
      expect(validateAutoRefreshInterval(123)).toBe(0)
      expect(validateAutoRefreshInterval(-10)).toBe(0)
      expect(validateAutoRefreshInterval('10')).toBe(0)
      expect(validateAutoRefreshInterval(null)).toBe(0)
    })

    it('restores saved auto-refresh setting on dashboard initialization', async () => {
      saveDashboardPreferences(userA.id, { autoRefreshInterval: 30 })

      render(
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText('Composite Reliability')).toBeInTheDocument()
      })

      const select = screen.getByRole('combobox', { name: /auto refresh interval/i }) as HTMLSelectElement
      expect(select.value).toBe('30')
    })

    it('triggers periodic polling when auto-refresh is active and cleans up on unmount', async () => {
      vi.useFakeTimers()
      saveDashboardPreferences(userA.id, { autoRefreshInterval: 10 })

      const { unmount } = render(
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      )

      // Initial query resolves
      await act(async () => {
        await Promise.resolve()
      })

      expect(dashboardService.getCommandCenter).toHaveBeenCalledTimes(1)

      // Advance clock by 10s to trigger first auto-refresh
      await act(async () => {
        vi.advanceTimersByTime(10000)
        await Promise.resolve()
      })
      expect(dashboardService.getCommandCenter).toHaveBeenCalledTimes(2)

      // Advance clock by another 10s to trigger second auto-refresh
      await act(async () => {
        vi.advanceTimersByTime(10000)
        await Promise.resolve()
      })
      expect(dashboardService.getCommandCenter).toHaveBeenCalledTimes(3)

      // Unmount component -> timer MUST be cleaned up
      unmount()

      // Advancing clock further should NOT trigger additional calls
      await act(async () => {
        vi.advanceTimersByTime(30000)
        await Promise.resolve()
      })
      expect(dashboardService.getCommandCenter).toHaveBeenCalledTimes(3)
    })

    it('does not trigger polling when auto-refresh is set to Off (0)', async () => {
      vi.useFakeTimers()
      saveDashboardPreferences(userA.id, { autoRefreshInterval: 0 })

      render(
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      )

      await act(async () => {
        await Promise.resolve()
      })
      expect(dashboardService.getCommandCenter).toHaveBeenCalledTimes(1)

      await act(async () => {
        vi.advanceTimersByTime(60000)
        await Promise.resolve()
      })

      // Still only 1 call
      expect(dashboardService.getCommandCenter).toHaveBeenCalledTimes(1)
    })

    it('keeps manual refresh functional independently without resetting settings', async () => {
      saveDashboardPreferences(userA.id, { timeWindow: '7d', autoRefreshInterval: 10 })

      render(
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText('Composite Reliability')).toBeInTheDocument()
      })

      expect(dashboardService.getCommandCenter).toHaveBeenCalledTimes(1)

      // Click manual Refresh
      const refreshBtn = screen.getByRole('button', { name: /refresh/i })
      await act(async () => {
        refreshBtn.click()
      })

      expect(dashboardService.getCommandCenter).toHaveBeenCalledTimes(2)
      expect(dashboardService.getCommandCenter).toHaveBeenLastCalledWith('7d')

      // Verify time window and auto-refresh remain unchanged
      expect(screen.getByRole('radio', { name: '7D' })).toHaveAttribute('aria-checked', 'true')
      const select = screen.getByRole('combobox', { name: /auto refresh interval/i }) as HTMLSelectElement
      expect(select.value).toBe('10')
    })

    it('changing time period does not reset auto-refresh preference and vice versa', async () => {
      saveDashboardPreferences(userA.id, { timeWindow: '1h', autoRefreshInterval: 30 })

      render(
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText('Composite Reliability')).toBeInTheDocument()
      })

      // Change time window to 7D
      const btn7d = screen.getByRole('radio', { name: '7D' })
      await act(async () => {
        btn7d.click()
      })

      // Auto-refresh should remain 30 in state and in storage
      const select = screen.getByRole('combobox', { name: /auto refresh interval/i }) as HTMLSelectElement
      expect(select.value).toBe('30')
      expect(getDashboardPreferences(userA.id).autoRefreshInterval).toBe(30)
      expect(getDashboardPreferences(userA.id).timeWindow).toBe('7d')

      // Change auto-refresh to 60s
      fireEvent.change(select, { target: { value: '60' } })
      expect(getDashboardPreferences(userA.id).autoRefreshInterval).toBe(60)
      expect(getDashboardPreferences(userA.id).timeWindow).toBe('7d')
    })
  })

  // ───────────────────────────────────────────────────────────────────────────
  // AUTHENTICATION LIFECYCLE & MULTI-USER ISOLATION
  // ───────────────────────────────────────────────────────────────────────────
  describe('Authentication Lifecycle & Multi-User Preference Isolation', () => {
    it('executes the full authentication lifecycle: login A -> configure -> reload -> logout -> login A -> login B isolation', async () => {
      // 1. Log in as User A
      useAuthStore.setState({
        status: 'AUTHENTICATED',
        user: userA,
        token: 'token-alpha-123',
      })

      // 2. Select 7D and enable 10s Auto-refresh for User A
      saveDashboardPreferences(userA.id, { timeWindow: '7d', autoRefreshInterval: 10 })

      // 3. Mount dashboard as User A (simulating reload) and verify both settings
      const { unmount: unmountUserA } = render(
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText('Composite Reliability')).toBeInTheDocument()
      })

      expect(screen.getByRole('radio', { name: '7D' })).toHaveAttribute('aria-checked', 'true')
      const selectA = screen.getByRole('combobox', { name: /auto refresh interval/i }) as HTMLSelectElement
      expect(selectA.value).toBe('10')
      expect(dashboardService.getCommandCenter).toHaveBeenCalledWith('7d')

      unmountUserA()

      // 4. Log out -> clearAuth() clears sensitive tokens and user context
      act(() => {
        useAuthStore.getState().clearAuth()
      })

      expect(useAuthStore.getState().status).toBe('UNAUTHENTICATED')
      expect(useAuthStore.getState().user).toBeNull()
      expect(useAuthStore.getState().token).toBeNull()
      expect(storage.get(STORAGE_KEYS.SESSION_HINT, false)).toBe(false)

      // 5. Log back in as User A -> verify preferences restored
      act(() => {
        useAuthStore.getState().setAuth(userA, 'token-alpha-relogin')
      })

      const { unmount: unmountUserARelogin } = render(
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText('Composite Reliability')).toBeInTheDocument()
      })

      expect(screen.getByRole('radio', { name: '7D' })).toHaveAttribute('aria-checked', 'true')
      const selectARelogin = screen.getByRole('combobox', { name: /auto refresh interval/i }) as HTMLSelectElement
      expect(selectARelogin.value).toBe('10')

      unmountUserARelogin()

      // 6. Log out, then log in as User B -> verify User A's preferences DO NOT leak into User B
      act(() => {
        useAuthStore.getState().clearAuth()
        useAuthStore.getState().setAuth(userB, 'token-beta-456')
      })

      const { unmount: unmountUserB } = render(
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText('Composite Reliability')).toBeInTheDocument()
      })

      // User B must receive system defaults, NOT User A's 7D or 10s!
      expect(screen.getByRole('radio', { name: '24H' })).toHaveAttribute('aria-checked', 'true')
      expect(screen.getByRole('radio', { name: '7D' })).toHaveAttribute('aria-checked', 'false')
      const selectB = screen.getByRole('combobox', { name: /auto refresh interval/i }) as HTMLSelectElement
      expect(selectB.value).toBe('0') // Off

      // User B chooses 30D and 60s
      const btn30d = screen.getByRole('radio', { name: '30D' })
      await act(async () => {
        btn30d.click()
      })
      fireEvent.change(selectB, { target: { value: '60' } })

      // User B preferences stored under User B's key
      expect(getDashboardPreferences(userB.id)).toEqual({
        timeWindow: '30d',
        autoRefreshInterval: 60,
      })

      // User A preferences in storage remain intact and isolated
      expect(getDashboardPreferences(userA.id)).toEqual({
        timeWindow: '7d',
        autoRefreshInterval: 10,
      })

      unmountUserB()
    })
  })
})
