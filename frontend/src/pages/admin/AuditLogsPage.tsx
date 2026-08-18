import { useState, useEffect } from 'react'
import { Activity, Search, Filter } from 'lucide-react'
import { adminService, AuditLog } from '@/services/adminService'
import { format } from 'date-fns'
import { Badge } from '@/components/common/Badge'

export function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  const [page] = useState(1)

  useEffect(() => {
    const fetchLogs = async () => {
      setLoading(true)
      try {
        const res = await adminService.getAuditLogs(page, 50)
        setLogs((res as any)?.items || (res as any)?.data || [])
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    fetchLogs()
  }, [page])

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Audit Logs</h2>
        <p className="text-muted-foreground">
          View security and access events for your workspace.
        </p>
      </div>

      <div className="flex items-center justify-between gap-4 bg-card border border-border p-3 rounded-lg">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search by action, user, or resource..."
            className="w-full pl-9 pr-4 py-2 bg-background border border-border rounded-md text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all"
          />
        </div>
        <button className="flex items-center gap-2 px-4 py-2 border border-border rounded-md bg-background text-sm font-medium hover:bg-muted transition-colors">
          <Filter className="h-4 w-4" />
          Filter
        </button>
      </div>

      <div className="border border-border rounded-lg bg-card text-card-foreground overflow-hidden">
        {loading ? (
          <div className="p-8 flex justify-center">
            <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : logs.length === 0 ? (
          <div className="p-12 flex flex-col items-center text-center">
            <Activity className="h-8 w-8 text-muted-foreground mb-4 opacity-50" />
            <h3 className="font-medium text-lg">No audit events found</h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-sm">
              Your workspace audit ledger is empty.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-muted/50 border-b border-border text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Timestamp</th>
                  <th className="px-4 py-3 font-medium">Action</th>
                  <th className="px-4 py-3 font-medium">Resource</th>
                  <th className="px-4 py-3 font-medium">Actor ID</th>
                  <th className="px-4 py-3 font-medium">IP Address</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {logs.map(log => (
                  <tr key={log.id} className="hover:bg-muted/20 transition-colors">
                    <td className="px-4 py-3 whitespace-nowrap tabular-nums text-muted-foreground">
                      {format(new Date(log.created_at), 'MMM d, yyyy HH:mm:ss')}
                    </td>
                    <td className="px-4 py-3 font-medium">
                      <Badge variant="subtle">{log.action}</Badge>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {log.resource_type} {log.resource_id ? `(${log.resource_id})` : ''}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">
                      {log.user_id || 'System'}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {log.details?.ip_address || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
