import { useState, useEffect } from 'react'
import { ShieldAlert, Activity, Users, Database } from 'lucide-react'
import { adminService, WorkspaceSummary } from '@/services/adminService'
import { useAuthStore } from '@/stores/authStore'

export function PlatformAdminPage() {
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([])
  const [loading, setLoading] = useState(true)
  const user = useAuthStore(s => s.user)
  const isPlatformAdmin = user?.role === 'platform_admin'

  useEffect(() => {
    if (!isPlatformAdmin) return

    const fetchData = async () => {
      setLoading(true)
      try {
        const res = await adminService.getGlobalWorkspaces(1, 50)
        setWorkspaces((res as any)?.items || (res as any)?.data || [])
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
      <div className="p-12 flex flex-col items-center text-center bg-card border border-border rounded-lg">
        <ShieldAlert className="h-8 w-8 text-destructive mb-4" />
        <h3 className="font-medium text-lg">Access Denied</h3>
        <p className="text-sm text-muted-foreground mt-1 max-w-sm">
          You must be a Platform Administrator to view this page.
        </p>
      </div>
    )
  }

  const totalMembers = workspaces.reduce((sum, w) => sum + w.member_count, 0)
  const totalQueries = workspaces.reduce((sum, w) => sum + w.total_queries, 0)

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Platform Administration</h2>
        <p className="text-muted-foreground">
          Global system overview, cross-workspace aggregations, and platform maintenance.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-card border border-border rounded-lg p-6 flex flex-col">
          <span className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Database className="h-4 w-4" /> Total Workspaces
          </span>
          <span className="text-3xl font-bold mt-2">{workspaces.length}</span>
        </div>
        <div className="bg-card border border-border rounded-lg p-6 flex flex-col">
          <span className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Users className="h-4 w-4" /> Global Users
          </span>
          <span className="text-3xl font-bold mt-2">{totalMembers}</span>
        </div>
        <div className="bg-card border border-border rounded-lg p-6 flex flex-col">
          <span className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Activity className="h-4 w-4" /> Global Queries
          </span>
          <span className="text-3xl font-bold mt-2">{totalQueries.toLocaleString()}</span>
        </div>
      </div>

      <div className="border border-border rounded-lg bg-card text-card-foreground overflow-hidden mt-6">
        {loading ? (
          <div className="p-8 flex justify-center">
            <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : workspaces.length === 0 ? (
          <div className="p-12 flex flex-col items-center text-center">
            <h3 className="font-medium text-lg">No workspaces found</h3>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-muted/50 border-b border-border text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Workspace ID</th>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium text-right">Members</th>
                  <th className="px-4 py-3 font-medium text-right">Queries Executed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {workspaces.map(w => (
                  <tr key={w.id} className="hover:bg-muted/20 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{w.id}</td>
                    <td className="px-4 py-3 font-medium">{w.name}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{w.member_count}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{w.total_queries.toLocaleString()}</td>
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
