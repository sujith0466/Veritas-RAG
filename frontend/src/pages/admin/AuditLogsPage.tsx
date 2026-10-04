import { useState, useEffect, useCallback } from 'react'
import { Activity, Search, Filter, ChevronLeft, ChevronRight, X, Calendar, RefreshCw } from 'lucide-react'
import { adminService, AuditLog } from '@/services/adminService'
import { format } from 'date-fns'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'

const COMMON_ACTIONS = [
  'ALL',
  'WORKSPACE_SETTINGS_UPDATED',
  'MEMBER_INVITED',
  'MEMBER_REMOVED',
  'MEMBER_ROLE_UPDATED',
  'DOMAIN_ADDED',
  'DOMAIN_VERIFIED',
  'WEBHOOK_CREATED',
  'WEBHOOK_DELETED',
  'DOCUMENT_PURGED',
  'API_KEY_CREATED',
]

export function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(50)
  const [totalPages, setTotalPages] = useState(1)
  const [totalElements, setTotalElements] = useState(0)

  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedAction, setSelectedAction] = useState('ALL')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [showFilters, setShowFilters] = useState(false)

  const fetchLogs = useCallback(async (targetPage = page) => {
    setLoading(true)
    try {
      const filters = {
        query: searchQuery.trim() || undefined,
        action: selectedAction !== 'ALL' ? selectedAction : undefined,
        start_date: startDate ? new Date(startDate).toISOString() : undefined,
        end_date: endDate ? new Date(endDate).toISOString() : undefined,
      }

      const res = await adminService.getAuditLogs(targetPage, pageSize, filters)
      const items = res?.items || (res as any)?.data || []
      const pagination = res?.pagination || {
        page: targetPage,
        size: pageSize,
        total_elements: items.length,
        total_pages: 1,
      }

      setLogs(items)
      setTotalPages(pagination.total_pages || 1)
      setTotalElements(pagination.total_elements || items.length)
      setPage(pagination.page || targetPage)
    } catch (e) {
      console.error('Failed to fetch audit logs:', e)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, searchQuery, selectedAction, startDate, endDate])

  useEffect(() => {
    fetchLogs(1)
  }, [selectedAction, startDate, endDate])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    fetchLogs(1)
  }

  const handleResetFilters = () => {
    setSearchQuery('')
    setSelectedAction('ALL')
    setStartDate('')
    setEndDate('')
    setPage(1)
  }

  const hasActiveFilters = searchQuery || selectedAction !== 'ALL' || startDate || endDate

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Audit Logs</h2>
          <p className="text-muted-foreground">
            Immutable WORM audit ledger tracking administrative, security, and workspace events.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => fetchLogs(page)} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Search & Filter Bar */}
      <div className="space-y-3 bg-card border border-border p-4 rounded-lg">
        <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search by action, resource type, ID, or user..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-background border border-border rounded-md text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Button type="submit" size="sm" variant="default">
              Search
            </Button>
            <Button
              type="button"
              variant={showFilters ? 'default' : 'outline'}
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center gap-2"
            >
              <Filter className="h-4 w-4" />
              Filters
              {hasActiveFilters && (
                <span className="w-2 h-2 rounded-full bg-primary" />
              )}
            </Button>
            {hasActiveFilters && (
              <Button type="button" variant="ghost" size="sm" onClick={handleResetFilters} title="Clear Filters">
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        </form>

        {/* Filter Drawer / Expanded Section */}
        {showFilters && (
          <div className="pt-3 border-t border-border/60 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Action Type</label>
              <select
                value={selectedAction}
                onChange={(e) => setSelectedAction(e.target.value)}
                className="w-full h-9 rounded-md border border-input bg-background px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              >
                {COMMON_ACTIONS.map((act) => (
                  <option key={act} value={act}>
                    {act === 'ALL' ? 'All Actions' : act}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Start Date</label>
              <div className="relative">
                <Calendar className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="pl-8 h-9 text-xs"
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">End Date</label>
              <div className="relative">
                <Calendar className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="pl-8 h-9 text-xs"
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Ledger Table */}
      <div className="border border-border rounded-lg bg-card text-card-foreground overflow-hidden shadow-sm">
        {loading ? (
          <div className="p-12 flex flex-col items-center justify-center space-y-3">
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-muted-foreground">Querying audit ledger...</p>
          </div>
        ) : logs.length === 0 ? (
          <div className="p-12 flex flex-col items-center text-center">
            <Activity className="h-10 w-10 text-muted-foreground mb-4 opacity-40" />
            <h3 className="font-semibold text-lg text-foreground">No audit events found</h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-sm">
              {hasActiveFilters
                ? 'No events match the specified filter criteria. Try adjusting your query.'
                : 'Your workspace audit ledger is clean.'}
            </p>
            {hasActiveFilters && (
              <Button variant="outline" size="sm" onClick={handleResetFilters} className="mt-4">
                Reset Filters
              </Button>
            )}
          </div>
        ) : (
          <div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-muted/50 border-b border-border text-muted-foreground font-medium text-xs uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3">Timestamp</th>
                    <th className="px-4 py-3">Action</th>
                    <th className="px-4 py-3">Resource</th>
                    <th className="px-4 py-3">Actor</th>
                    <th className="px-4 py-3">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border text-xs">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-muted/20 transition-colors">
                      <td className="px-4 py-3 whitespace-nowrap tabular-nums text-muted-foreground">
                        {log.created_at ? format(new Date(log.created_at), 'MMM d, yyyy HH:mm:ss') : '-'}
                      </td>
                      <td className="px-4 py-3 font-medium">
                        <Badge variant="subtle" className="font-mono text-[11px]">
                          {log.action}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-foreground font-mono">
                        {log.resource_type || '-'}
                        {log.resource_id ? (
                          <span className="text-muted-foreground ml-1">({log.resource_id.slice(0, 8)}…)</span>
                        ) : null}
                      </td>
                      <td className="px-4 py-3 font-mono text-muted-foreground">
                        {log.user_id ? log.user_id.slice(0, 8) + '…' : 'System'}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground max-w-xs truncate font-mono">
                        {log.details ? JSON.stringify(log.details) : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-4 py-3 border-t border-border bg-muted/20 text-xs text-muted-foreground">
              <div>
                Showing <strong>{logs.length}</strong> of <strong>{totalElements}</strong> total audit events
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fetchLogs(page - 1)}
                  disabled={page <= 1 || loading}
                  className="h-8 px-2.5"
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Previous
                </Button>

                <span className="px-2">
                  Page <strong>{page}</strong> of <strong>{totalPages}</strong>
                </span>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fetchLogs(page + 1)}
                  disabled={page >= totalPages || loading}
                  className="h-8 px-2.5"
                >
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
