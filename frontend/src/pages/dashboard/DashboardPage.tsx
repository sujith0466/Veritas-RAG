import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import {
  dashboardAnalyticalGroupVariants,
  dashboardAnalyticalItemVariants,
  dashboardFlightRecorderVariants,
} from '@/motion'
import { PageTransition } from '@/components/layouts'
import { ErrorState } from '@/components/common/ErrorState'
import { dashboardService } from '@/services/dashboardService'
import { useAuthStore, selectUser } from '@/stores/authStore'
import {
  getDashboardPreferences,
  saveDashboardPreferences,
  validateAutoRefreshInterval,
  type DashboardTimeWindow,
} from '@/utils/dashboardPreferences'
import type { CommandCenterDTO, QueryExecutionLedgerDTO } from '@/types'
import {
  CommandCenterHeader,
  ExecutiveKpiGrid,
  RetrievalLatencyRadar,
  KnowledgePipelineCard,
  OperationalAlertsBanner,
  ExecutionFlightRecorder,
  ExecutionTraceDrawer,
} from '@/components/dashboard'

export function DashboardPage() {
  const shouldReduceMotion = useReducedMotion()
  const hasLoadedInitialDataRef = useRef(false)
  const isFetchingRef = useRef(false)
  const isMountedRef = useRef(true)

  const user = useAuthStore(selectUser)
  const userId = user?.id || null
  const prevUserIdRef = useRef<string | null>(userId)

  // Initialize timeWindow and autoRefreshInterval from stored user preferences
  const [timeWindow, setTimeWindow] = useState<DashboardTimeWindow>(() => {
    const initialUser = useAuthStore.getState().user
    return getDashboardPreferences(initialUser?.id).timeWindow
  })
  const [autoRefreshInterval, setAutoRefreshInterval] = useState<number>(() => {
    const initialUser = useAuthStore.getState().user
    return getDashboardPreferences(initialUser?.id).autoRefreshInterval
  })
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Track mount status for race-condition and cleanup safety
  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  // Synchronize state when authenticated user identity changes (e.g. login/logout/user-switch)
  useEffect(() => {
    if (userId !== prevUserIdRef.current) {
      prevUserIdRef.current = userId
      const prefs = getDashboardPreferences(userId)
      setTimeWindow(prefs.timeWindow)
      setAutoRefreshInterval(prefs.autoRefreshInterval)
      setPage(1)
    }
  }, [userId])

  // Command Center Telemetry State
  const [commandCenter, setCommandCenter] = useState<CommandCenterDTO | null>(null)

  // Execution Ledger State
  const [ledger, setLedger] = useState<QueryExecutionLedgerDTO | null>(null)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const pageSize = 15

  // Trace Drawer State
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null)

  // Fetch telemetry and ledger data
  const loadDashboardData = useCallback(async (isSilent = false) => {
    // Prevent overlapping requests
    if (isFetchingRef.current) return
    isFetchingRef.current = true

    if (!isSilent) {
      setIsLoading(true)
    }
    setError(null)

    try {
      const [ccData, ledgerData] = await Promise.all([
        dashboardService.getCommandCenter(timeWindow),
        dashboardService.getExecutions({
          timeWindow,
          limit: pageSize,
          offset: (page - 1) * pageSize,
          status: statusFilter !== 'ALL' ? statusFilter : undefined,
          search: search.trim() || undefined,
        }),
      ])
      if (isMountedRef.current) {
        setCommandCenter(ccData)
        setLedger(ledgerData)
        hasLoadedInitialDataRef.current = true
      }
    } catch (err) {
      console.error('Failed to load command center telemetry:', err)
      if (isMountedRef.current && (!isSilent || !hasLoadedInitialDataRef.current)) {
        setError('Unable to fetch command center metrics. Please check network connection and try again.')
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false)
      }
      isFetchingRef.current = false
    }
  }, [timeWindow, page, search, statusFilter])

  // Initial load and filter change trigger
  useEffect(() => {
    loadDashboardData(false)
  }, [loadDashboardData])

  // Auto-refresh timer interval
  useEffect(() => {
    if (autoRefreshInterval <= 0) return

    const timer = setInterval(() => {
      loadDashboardData(true)
    }, autoRefreshInterval * 1000)

    return () => clearInterval(timer)
  }, [autoRefreshInterval, loadDashboardData])

  // Persisted time-window changer
  const handleTimeWindowChange = (w: DashboardTimeWindow) => {
    setTimeWindow(w)
    setPage(1)
    saveDashboardPreferences(userId, { timeWindow: w })
  }

  // Persisted auto-refresh interval changer
  const handleAutoRefreshChange = (interval: number) => {
    const validInterval = validateAutoRefreshInterval(interval)
    setAutoRefreshInterval(validInterval)
    saveDashboardPreferences(userId, { autoRefreshInterval: validInterval })
  }

  // Manual refresh handler
  const handleManualRefresh = () => {
    loadDashboardData(false)
  }

  // Reset page to 1 when search or status filter changes
  const handleSearchChange = (newSearch: string) => {
    setSearch(newSearch)
    setPage(1)
  }

  const handleStatusFilterChange = (newStatus: string) => {
    setStatusFilter(newStatus)
    setPage(1)
  }

  return (
    <PageTransition variant="workspace">
      <div className="space-y-6 pb-12 max-w-7xl mx-auto">
        {/* ZONE 1: Command Center Header */}
        <motion.div
          initial={shouldReduceMotion || hasLoadedInitialDataRef.current ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
        >
          <CommandCenterHeader
            timeWindow={timeWindow}
            onTimeWindowChange={handleTimeWindowChange}
            autoRefreshInterval={autoRefreshInterval}
            onAutoRefreshChange={handleAutoRefreshChange}
            isLoading={isLoading}
            onRefresh={handleManualRefresh}
            systemStatus={commandCenter?.system_health.status || 'OPERATIONAL'}
          />
        </motion.div>

        {error ? (
          <div className="py-8">
            <ErrorState
              title="Command Center Error"
              error={new Error(error)}
              onRetry={loadDashboardData}
            />
          </div>
        ) : (
          <>
            {/* ZONE 2: Executive Reliability & KPI Intelligence */}
            {commandCenter ? (
              <ExecutiveKpiGrid
                kpis={commandCenter.kpis}
                trendPoints={commandCenter.reliability_trend}
                timeWindow={timeWindow}
                isLoading={isLoading}
                shouldAnimate={!hasLoadedInitialDataRef.current}
              />
            ) : isLoading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="h-32 rounded-lg border border-border/60 bg-card/40" />
                ))}
              </div>
            ) : null}

            {/* ZONE 3: Core Analytical Telemetry (Balanced 3-Column Coordinated Reveal) */}
            {commandCenter ? (
              <motion.div
                variants={shouldReduceMotion ? undefined : dashboardAnalyticalGroupVariants}
                initial={shouldReduceMotion || hasLoadedInitialDataRef.current ? false : 'hidden'}
                animate="visible"
                className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
              >
                <motion.div
                  variants={shouldReduceMotion ? undefined : dashboardAnalyticalItemVariants}
                  className="col-span-1"
                >
                  <RetrievalLatencyRadar
                    latency={commandCenter.latency_percentiles}
                    outcomes={commandCenter.outcomes}
                    isLoading={isLoading}
                  />
                </motion.div>

                <motion.div
                  variants={shouldReduceMotion ? undefined : dashboardAnalyticalItemVariants}
                  className="col-span-1"
                >
                  <KnowledgePipelineCard
                    knowledge={commandCenter.knowledge_health}
                    isLoading={isLoading}
                  />
                </motion.div>

                <motion.div
                  variants={shouldReduceMotion ? undefined : dashboardAnalyticalItemVariants}
                  className="col-span-1 md:col-span-2 lg:col-span-1"
                >
                  <OperationalAlertsBanner
                    alerts={commandCenter.alerts}
                    isLoading={isLoading}
                  />
                </motion.div>
              </motion.div>
            ) : isLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-pulse">
                <div className="col-span-1 h-72 rounded-lg border border-border/60 bg-card/40" />
                <div className="col-span-1 h-72 rounded-lg border border-border/60 bg-card/40" />
                <div className="col-span-1 md:col-span-2 lg:col-span-1 h-72 rounded-lg border border-border/60 bg-card/40" />
              </div>
            ) : null}

            {/* ZONE 4: Interactive Execution Flight Recorder & Audit Ledger */}
            <motion.div
              variants={shouldReduceMotion ? undefined : dashboardFlightRecorderVariants}
              initial={shouldReduceMotion || hasLoadedInitialDataRef.current ? false : 'hidden'}
              animate="visible"
            >
              <ExecutionFlightRecorder
                items={ledger?.items || []}
                total={ledger?.total || 0}
                page={page}
                pageSize={pageSize}
                onPageChange={setPage}
                search={search}
                onSearchChange={handleSearchChange}
                statusFilter={statusFilter}
                onStatusFilterChange={handleStatusFilterChange}
                onInspectTrace={(queryId) => setSelectedTraceId(queryId)}
                isLoading={isLoading}
                timeWindow={timeWindow}
              />
            </motion.div>
          </>
        )}

        {/* ZONE 5: Execution Trace Drawer */}
        <ExecutionTraceDrawer
          queryId={selectedTraceId}
          onClose={() => setSelectedTraceId(null)}
        />
      </div>
    </PageTransition>
  )
}
