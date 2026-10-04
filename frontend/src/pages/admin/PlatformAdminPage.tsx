import { useState, useEffect } from 'react'
import {
  ShieldAlert,
  Activity,
  Users,
  Database,
  Search,
  Building2,
  Shield,
} from 'lucide-react'
import { motion, useReducedMotion } from 'framer-motion'
import { adminService, WorkspaceSummary } from '@/services/adminService'
import { useAuthStore } from '@/stores/authStore'
import { AdminPageHeader } from '@/components/admin/AdminPageHeader'
import { Card } from '@/components/common/Card'
import { Input } from '@/components/common/Input'

export function PlatformAdminPage() {
  const shouldReduceMotion = useReducedMotion()
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [filterQuery, setFilterQuery] = useState('')
  const user = useAuthStore(s => s.user)
  const isPlatformAdmin = String(user?.role || '').trim().toLowerCase() === 'platform_admin'

  useEffect(() => {
    if (!isPlatformAdmin) return

    const fetchData = async () => {
      setLoading(true)
      try {
        const res = await adminService.getGlobalWorkspaces(1, 50)
        const items = Array.isArray(res) ? res : ((res as any)?.data || (res as any)?.items || [])
        setWorkspaces(items)
      } catch (e) {
        console.error('Failed to load global workspaces', e)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [isPlatformAdmin])

  if (!isPlatformAdmin) {
    return (
      <div className="p-12 flex flex-col items-center text-center bg-card border border-destructive/30 rounded-xl shadow-xs">
        <div className="p-3 bg-destructive/10 rounded-full text-destructive mb-4">
          <ShieldAlert className="h-8 w-8" />
        </div>
        <h3 className="font-bold text-lg text-foreground">Access Denied</h3>
        <p className="text-sm text-muted-foreground mt-1 max-w-sm">
          You must possess the <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono text-destructive">PLATFORM_ADMIN</code> role to access global infrastructure controls.
        </p>
      </div>
    )
  }

  const totalMembers = workspaces.reduce((sum, w) => sum + w.member_count, 0)
  const totalQueries = workspaces.reduce((sum, w) => sum + w.total_queries, 0)

  const filteredWorkspaces = workspaces.filter(
    w =>
      w.name.toLowerCase().includes(filterQuery.toLowerCase()) ||
      w.id.toLowerCase().includes(filterQuery.toLowerCase())
  )

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <AdminPageHeader
        eyebrow="GLOBAL SYSTEM CONTROL PLANE"
        title="Platform Administration"
        description="Global system overview, multi-tenant fleet aggregations, and platform infrastructure control."
        badge={
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-2xs font-mono font-bold bg-amber-500/10 text-amber-500 border border-amber-500/25">
            <Shield className="h-3 w-3" />
            GLOBAL SCOPE
          </span>
        }
      />

      {/* Aggregate Platform Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <motion.div
          initial={shouldReduceMotion ? false : { opacity: 0, y: 10 }}
          animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
        >
          <Card className="p-5 border border-border/80 shadow-xs flex flex-col justify-between hover:border-border transition-colors">
            <span className="text-2xs font-semibold text-muted-foreground uppercase tracking-wider font-mono flex items-center gap-2">
              <Database className="h-4 w-4 text-primary" /> Active Workspaces
            </span>
            <div className="mt-3">
              <span className="text-3xl font-bold font-mono text-foreground">{workspaces.length}</span>
              <p className="text-2xs text-muted-foreground mt-1">Tenant partitions provisioned</p>
            </div>
          </Card>
        </motion.div>

        <motion.div
          initial={shouldReduceMotion ? false : { opacity: 0, y: 10 }}
          animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: 0.05 }}
        >
          <Card className="p-5 border border-border/80 shadow-xs flex flex-col justify-between hover:border-border transition-colors">
            <span className="text-2xs font-semibold text-muted-foreground uppercase tracking-wider font-mono flex items-center gap-2">
              <Users className="h-4 w-4 text-indigo-400" /> Global Users
            </span>
            <div className="mt-3">
              <span className="text-3xl font-bold font-mono text-foreground">{totalMembers.toLocaleString()}</span>
              <p className="text-2xs text-muted-foreground mt-1">Active registered user accounts</p>
            </div>
          </Card>
        </motion.div>

        <motion.div
          initial={shouldReduceMotion ? false : { opacity: 0, y: 10 }}
          animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: 0.1 }}
        >
          <Card className="p-5 border border-border/80 shadow-xs flex flex-col justify-between hover:border-border transition-colors">
            <span className="text-2xs font-semibold text-muted-foreground uppercase tracking-wider font-mono flex items-center gap-2">
              <Activity className="h-4 w-4 text-emerald-400" /> Platform Queries
            </span>
            <div className="mt-3">
              <span className="text-3xl font-bold font-mono text-foreground">{totalQueries.toLocaleString()}</span>
              <p className="text-2xs text-muted-foreground mt-1">Total grounded RAG inference calls</p>
            </div>
          </Card>
        </motion.div>
      </div>

      {/* Search Toolbar */}
      <div className="flex items-center gap-3 bg-card p-3 rounded-lg border border-border shadow-xs">
        <div className="relative flex-1">
          <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Filter workspaces by name or tenant ID..."
            value={filterQuery}
            onChange={e => setFilterQuery(e.target.value)}
            className="pl-9 h-9 text-xs bg-background/80"
          />
        </div>
        <span className="text-2xs font-mono text-muted-foreground pr-2">
          {filteredWorkspaces.length} of {workspaces.length} Workspaces
        </span>
      </div>

      {/* Workspaces Fleet Table */}
      <div className="border border-border rounded-xl bg-card text-card-foreground overflow-hidden shadow-xs">
        {loading ? (
          <div className="p-16 flex flex-col items-center justify-center space-y-3">
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <span className="text-xs font-mono text-muted-foreground">Querying global multi-tenant catalog...</span>
          </div>
        ) : filteredWorkspaces.length === 0 ? (
          <div className="p-16 flex flex-col items-center text-center">
            <Building2 className="h-10 w-10 text-muted-foreground mb-3 opacity-30" />
            <h3 className="font-semibold text-base text-foreground">No workspaces found</h3>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm">
              {filterQuery ? 'No tenants match the filter criteria.' : 'No active workspace records.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-muted/40 border-b border-border text-muted-foreground font-semibold text-2xs uppercase font-mono tracking-wider">
                <tr>
                  <th className="px-4 py-3.5">Workspace ID</th>
                  <th className="px-4 py-3.5">Workspace Name</th>
                  <th className="px-4 py-3.5 text-right">Active Seats</th>
                  <th className="px-4 py-3.5 text-right">Queries Executed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60 text-xs">
                {filteredWorkspaces.map(w => (
                  <tr key={w.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-mono text-2xs text-muted-foreground">
                      <span className="px-1.5 py-0.5 rounded bg-muted/60">{w.id}</span>
                    </td>
                    <td className="px-4 py-3 font-semibold text-foreground">
                      <div className="flex items-center gap-2">
                        <Building2 className="h-3.5 w-3.5 text-primary/70" />
                        <span>{w.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums text-foreground">
                      {w.member_count}
                    </td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums text-foreground">
                      {w.total_queries.toLocaleString()}
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
