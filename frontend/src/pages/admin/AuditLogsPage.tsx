import { useState, useEffect, useCallback } from 'react'
import {
  Activity,
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  X,
  Calendar,
  RefreshCw,
  Eye,
  FileCode,
  ShieldCheck,
  User,
} from 'lucide-react'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { adminService, AuditLog } from '@/services/adminService'
import { format } from 'date-fns'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import { AdminPageHeader } from '@/components/admin/AdminPageHeader'
import { cn } from '@/utils/cn'

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
  const shouldReduceMotion = useReducedMotion()
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

  // Detail Modal
  const [activeLogDetail, setActiveLogDetail] = useState<AuditLog | null>(null)

  const fetchLogs = useCallback(
    async (targetPage = page) => {
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
    },
    [page, pageSize, searchQuery, selectedAction, startDate, endDate]
  )

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

  const getActionBadgeStyle = (action: string) => {
    if (action.includes('SETTINGS')) {
      return 'bg-teal-500/10 text-teal-400 border-teal-500/25'
    }
    if (action.includes('MEMBER') || action.includes('INVITE')) {
      return 'bg-indigo-500/10 text-indigo-400 border-indigo-500/25'
    }
    if (action.includes('DELETE') || action.includes('PURGE')) {
      return 'bg-rose-500/10 text-rose-400 border-rose-500/25'
    }
    if (action.includes('DOMAIN') || action.includes('WEBHOOK')) {
      return 'bg-violet-500/10 text-violet-400 border-violet-500/25'
    }
    return 'bg-primary/10 text-primary border-primary/20'
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <AdminPageHeader
        eyebrow="ADMINISTRATION / AUDIT"
        title="Audit Logs"
        description="Immutable WORM audit ledger tracking administrative, security, and workspace events."
        badge={
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-2xs font-mono font-medium bg-primary/10 text-primary border border-primary/20">
            <ShieldCheck className="h-3 w-3" />
            {totalElements} Total Event{totalElements !== 1 ? 's' : ''}
          </span>
        }
        actions={
          <Button variant="outline" size="sm" onClick={() => fetchLogs(page)} disabled={loading} className="shadow-xs">
            <RefreshCw className={cn('h-3.5 w-3.5 mr-2', loading && 'animate-spin')} />
            Refresh
          </Button>
        }
      />

      {/* Search & Filter Bar */}
      <div className="space-y-3 bg-card border border-border p-4 rounded-xl shadow-xs">
        <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search by action, resource type, ID, or user..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-background border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Button type="submit" size="sm" variant="default" className="shadow-xs">
              Search
            </Button>
            <Button
              type="button"
              variant={showFilters ? 'default' : 'outline'}
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center gap-2"
            >
              <Filter className="h-3.5 w-3.5" />
              <span>Filters</span>
              {hasActiveFilters && <span className="w-2 h-2 rounded-full bg-primary" />}
            </Button>
            {hasActiveFilters && (
              <Button type="button" variant="ghost" size="sm" onClick={handleResetFilters} title="Clear Filters" className="px-2">
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        </form>

        {/* Filter Drawer / Expanded Section */}
        <AnimatePresence>
          {showFilters && (
            <motion.div
              initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className="pt-3 border-t border-border/60 grid grid-cols-1 sm:grid-cols-3 gap-3"
            >
              <div>
                <label className="text-2xs font-semibold uppercase tracking-wider text-muted-foreground mb-1 block font-mono">
                  Action Category
                </label>
                <select
                  value={selectedAction}
                  onChange={e => setSelectedAction(e.target.value)}
                  className="w-full h-9 rounded-md border border-input bg-background px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  {COMMON_ACTIONS.map(act => (
                    <option key={act} value={act}>
                      {act === 'ALL' ? 'All Actions' : act}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-2xs font-semibold uppercase tracking-wider text-muted-foreground mb-1 block font-mono">
                  Start Date
                </label>
                <div className="relative">
                  <Calendar className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                  <Input
                    type="date"
                    value={startDate}
                    onChange={e => setStartDate(e.target.value)}
                    className="pl-8 h-9 text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="text-2xs font-semibold uppercase tracking-wider text-muted-foreground mb-1 block font-mono">
                  End Date
                </label>
                <div className="relative">
                  <Calendar className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                  <Input
                    type="date"
                    value={endDate}
                    onChange={e => setEndDate(e.target.value)}
                    className="pl-8 h-9 text-xs"
                  />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Ledger Table */}
      <div className="border border-border rounded-xl bg-card text-card-foreground overflow-hidden shadow-xs">
        {loading ? (
          <div className="p-16 flex flex-col items-center justify-center space-y-3">
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <p className="text-xs font-mono text-muted-foreground">Querying immutable audit ledger...</p>
          </div>
        ) : logs.length === 0 ? (
          <div className="p-16 flex flex-col items-center text-center">
            <Activity className="h-10 w-10 text-muted-foreground mb-3 opacity-30" />
            <h3 className="font-semibold text-base text-foreground">No audit events found</h3>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm">
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
                <thead className="bg-muted/40 border-b border-border text-muted-foreground font-semibold text-2xs uppercase font-mono tracking-wider">
                  <tr>
                    <th className="px-4 py-3.5">Timestamp</th>
                    <th className="px-4 py-3.5">Action</th>
                    <th className="px-4 py-3.5">Target Resource</th>
                    <th className="px-4 py-3.5">Actor / User</th>
                    <th className="px-4 py-3.5">Details</th>
                    <th className="px-4 py-3.5 text-right">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60 text-xs">
                  {logs.map(log => (
                    <tr key={log.id} className="hover:bg-muted/30 transition-colors group">
                      <td className="px-4 py-3 whitespace-nowrap tabular-nums text-muted-foreground font-mono">
                        {log.created_at ? format(new Date(log.created_at), 'MMM d, yyyy HH:mm:ss') : '-'}
                      </td>
                      <td className="px-4 py-3 font-medium">
                        <span
                          className={cn(
                            'inline-flex items-center px-2 py-0.5 rounded-full text-2xs font-mono font-semibold border',
                            getActionBadgeStyle(log.action)
                          )}
                        >
                          {log.action}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-foreground font-mono">
                        <span className="font-semibold">{log.resource_type || '-'}</span>
                        {log.resource_id ? (
                          <span className="text-muted-foreground ml-1.5 text-2xs">
                            ({log.resource_id.slice(0, 8)}…)
                          </span>
                        ) : null}
                      </td>
                      <td className="px-4 py-3 font-mono text-muted-foreground">
                        <span className="inline-flex items-center gap-1.5">
                          <User className="h-3 w-3 text-muted-foreground/60" />
                          {log.user_id ? log.user_id.slice(0, 8) + '…' : 'System'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground max-w-xs truncate font-mono text-2xs">
                        {log.details ? JSON.stringify(log.details) : '-'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => setActiveLogDetail(log)}
                          title="Inspect raw event payload"
                          className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors opacity-70 group-hover:opacity-100"
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-4 py-3.5 border-t border-border bg-muted/20 text-xs text-muted-foreground font-mono">
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

      {/* Detail Inspection Modal */}
      <AnimatePresence>
        {activeLogDetail && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setActiveLogDetail(null)}
              className="fixed inset-0 bg-background/80 backdrop-blur-sm"
              aria-hidden="true"
            />
            <motion.div
              initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.96 }}
              className="relative bg-card border border-border rounded-xl p-6 w-full max-w-lg shadow-2xl space-y-4 z-10 font-sans"
            >
              <div className="flex items-center justify-between border-b border-border/60 pb-3">
                <div className="flex items-center gap-2">
                  <FileCode className="h-4 w-4 text-primary" />
                  <h3 className="font-bold text-sm text-foreground">Audit Log Event Inspection</h3>
                </div>
                <button
                  onClick={() => setActiveLogDetail(null)}
                  className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="space-y-3 text-xs">
                <div className="grid grid-cols-2 gap-2 p-3 bg-muted/30 rounded-lg border border-border/50 font-mono">
                  <div>
                    <span className="text-muted-foreground block text-2xs uppercase">Event ID</span>
                    <span className="text-foreground">{activeLogDetail.id}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block text-2xs uppercase">Action</span>
                    <span className="text-primary font-semibold">{activeLogDetail.action}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block text-2xs uppercase">Actor UUID</span>
                    <span className="text-foreground">{activeLogDetail.user_id || 'SYSTEM'}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block text-2xs uppercase">Resource</span>
                    <span className="text-foreground">
                      {activeLogDetail.resource_type} ({activeLogDetail.resource_id || 'N/A'})
                    </span>
                  </div>
                </div>

                <div>
                  <span className="font-semibold text-muted-foreground block mb-1">Payload Snapshot:</span>
                  <pre className="p-3 bg-background border border-border/80 rounded-lg text-2xs font-mono text-foreground overflow-x-auto max-h-60 leading-relaxed">
                    {JSON.stringify(activeLogDetail.details, null, 2)}
                  </pre>
                </div>
              </div>

              <div className="flex justify-end pt-2 border-t border-border/60">
                <Button size="sm" variant="outline" onClick={() => setActiveLogDetail(null)}>
                  Close
                </Button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  )
}
