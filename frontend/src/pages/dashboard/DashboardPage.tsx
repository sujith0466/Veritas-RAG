import { useState, useEffect, useCallback } from 'react'
import { PageTransition } from '@/components/layouts'
import { ErrorState } from '@/components/common/ErrorState'
import { dashboardService } from '@/services/dashboardService'
import type { CommandCenterDTO, QueryExecutionLedgerDTO } from '@/types'
import {
  CommandCenterHeader,
  ExecutiveKpiGrid,
  SystemHealthRadar,
  RetrievalLatencyRadar,
  KnowledgePipelineCard,
  OperationalAlertsBanner,
  ExecutionFlightRecorder,
  ExecutionTraceDrawer,
} from '@/components/dashboard'

export function DashboardPage() {
  const [timeWindow, setTimeWindow] = useState<'1h' | '24h' | '7d' | '30d' | 'all'>('24h')
  const [autoRefreshInterval, setAutoRefreshInterval] = useState<number>(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
  const loadDashboardData = useCallback(async () => {
    setIsLoading(true)
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
      setCommandCenter(ccData)
      setLedger(ledgerData)
    } catch (err) {
      console.error('Failed to load command center telemetry:', err)
      setError('Unable to fetch command center metrics. Please check network connection and try again.')
    } finally {
      setIsLoading(false)
    }
  }, [timeWindow, page, search, statusFilter])

  // Initial load and filter change trigger
  useEffect(() => {
    loadDashboardData()
  }, [loadDashboardData])

  // Auto-refresh timer interval
  useEffect(() => {
    if (autoRefreshInterval <= 0) return

    const timer = setInterval(() => {
      loadDashboardData()
    }, autoRefreshInterval * 1000)

    return () => clearInterval(timer)
  }, [autoRefreshInterval, loadDashboardData])

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
    <PageTransition>
      <div className="space-y-6 pb-12 max-w-7xl mx-auto">
        {/* ZONE 1: Command Center Header */}
        <CommandCenterHeader
          timeWindow={timeWindow}
          onTimeWindowChange={(w) => {
            setTimeWindow(w)
            setPage(1)
          }}
          autoRefreshInterval={autoRefreshInterval}
          onAutoRefreshChange={setAutoRefreshInterval}
          isLoading={isLoading}
          onRefresh={loadDashboardData}
          systemStatus={commandCenter?.system_health.status || 'OPERATIONAL'}
        />

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
            {commandCenter && (
              <ExecutiveKpiGrid
                kpis={commandCenter.kpis}
                trendPoints={commandCenter.reliability_trend}
                timeWindow={timeWindow}
                isLoading={isLoading}
              />
            )}

            {/* ZONE 3 & ZONE 4: Subsystem Health & Latency Decomposition */}
            {commandCenter && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <div className="lg:col-span-6">
                  <SystemHealthRadar
                    systemHealth={commandCenter.system_health}
                    activeTenants={commandCenter.kpis.active_tenants}
                    activeWorkspaces={commandCenter.kpis.active_workspaces}
                    isLoading={isLoading}
                  />
                </div>

                <div className="lg:col-span-6">
                  <RetrievalLatencyRadar
                    latency={commandCenter.latency_percentiles}
                    outcomes={commandCenter.outcomes}
                    isLoading={isLoading}
                  />
                </div>
              </div>
            )}

            {/* ZONE 4 & ZONE 5: Knowledge Pipeline Health & Safety Interventions */}
            {commandCenter && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <div className="lg:col-span-7">
                  <KnowledgePipelineCard
                    knowledge={commandCenter.knowledge_health}
                    isLoading={isLoading}
                  />
                </div>

                <div className="lg:col-span-5">
                  <OperationalAlertsBanner
                    alerts={commandCenter.alerts}
                    isLoading={isLoading}
                  />
                </div>
              </div>
            )}

            {/* ZONE 6: Interactive Execution Flight Recorder & Audit Ledger */}
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
          </>
        )}

        {/* ZONE 7: Execution Trace Drawer */}
        <ExecutionTraceDrawer
          queryId={selectedTraceId}
          onClose={() => setSelectedTraceId(null)}
        />
      </div>
    </PageTransition>
  )
}
